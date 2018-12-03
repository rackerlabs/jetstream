# Copyright 2017 Rackspace US, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

'''Testing module'''

import time
import string
import random

from os import path, getcwd, environ
from logging import getLogger
from troposphere import Template
from troposphere.cloudformation import Stack

import boto3

from jetstream.publisher import S3Publisher, LocalPublisher


LOG = getLogger(__name__)


class Test(object):
    '''
    Test Object

    CRUD for CloudFormation testing
    '''
    def __init__(self, templates, dry_run=False):
        self.templates = _flatten_templates(templates)

        # S3 bucket names have to be globally unique. This helps ensure as much
        # randomness as possible by mixing the current time in detail with an
        # additional random string
        timestamp = time.strftime('%Y%m%d%H%M%S', time.gmtime())
        suffix = ''.join(
            random.SystemRandom().choice(
                string.ascii_lowercase + string.digits) for _ in range(10))
        self._bucket = "jetstream-test-{}-{}".format(timestamp, suffix)
        self._stack_name = "JetstreamTest{}".format(timestamp)
        self._bucket_url = "https://s3.amazonaws.com/{}".format(self._bucket)
        self._dry_run = dry_run

        if self._dry_run:
            self.publisher = LocalPublisher(
                path.join(getcwd(), self._bucket))
        else:
            self._client = boto3.client('cloudformation')
            self.publisher = S3Publisher("s3://" + self._bucket, public=False)

    def __get_region_from_env(self):
        """
        Retrieve region from a few reasonable environment variables. Mainly
        used with S3 to set the LocationConstraint when creating buckets

        :return: Either the region defined in the environment variable or False
        """
        for region_env in ["AWS_DEFAULT_REGION", "DEFAULT_REGION", "REGION"]:
            region = environ.get(region_env)
            if region:
                return region

        return False

    def run(self):
        '''Run the test'''
        if not self._dry_run:
            LOG.info("Creating bucket %s", self._bucket)
            region = self.__get_region_from_env()
            if region:
                boto3.client('s3').create_bucket(
                    Bucket=self._bucket,
                    CreateBucketConfiguration={'LocationConstraint': region})
            else:
                boto3.client('s3').create_bucket(Bucket=self._bucket)
            LOG.info("Bucket %s created", self._bucket)

        LOG.info("Uploading files")
        self.publisher.publish_file('master.template',
                                    self.parent_template())
        for templ in self.templates:
            LOG.info("Uploading file: %s", templ.name)
            self.publisher.publish_file(templ.name,
                                        templ.generate(testing=True))

        if self._dry_run:
            return True

        LOG.info("Creating stack %s...", self._stack_name)
        self._build_stack()
        return self._wait_results(self._stack_name)

    def cleanup(self):
        '''Clean up the testing stack and bucket'''
        if self._dry_run:
            return
        s3_client = boto3.client('s3')
        resp = s3_client.list_objects(Bucket=self._bucket)
        contents = resp.get('Contents')
        bucket_objects = []
        if contents:
            for item in contents:
                bucket_objects.append({'Key': item.get('Key')})

        s3_client.delete_objects(Bucket=self._bucket,
                                 Delete={'Objects': bucket_objects})
        s3_client.delete_bucket(Bucket=self._bucket)

        cf_client = boto3.client('cloudformation')
        cf_client.delete_stack(StackName=self._stack_name)

    def _wait_results(self, stack_name):
        '''Wait for a stack to pass or fail'''
        stack_failure = False
        while True:
            resp = self._client.describe_stacks(StackName=stack_name)
            stack_info = resp['Stacks'][0]
            stack_status = stack_info['StackStatus']

            LOG.info("Stack status is %s", stack_status)
            if 'COMPLETE' in stack_status:
                break

            if 'ROLLBACK' in stack_status and not stack_failure:
                stack_failure = True

                # log at the time of failure, so we get all the data
                self._log_failed_stacks(stack_name)

            # stack rollback failed, will never be COMPLETE
            if 'ROLLBACK_FAILED' in stack_status:
                LOG.error("Stack %s rollback failed, fix manually",
                          stack_name)
                break

            LOG.info("Stack %s is not COMPLETE", stack_name)
            time.sleep(10)
        return not stack_failure

    def _build_stack(self):
        '''Build the Test Stack'''
        parent_templ = "{}/{}".format(self._bucket_url, 'master.template')
        self._client.create_stack(
            StackName=self._stack_name,
            TemplateURL=parent_templ,
            Capabilities=['CAPABILITY_IAM'])

    def parent_template(self):
        '''
        Generate the parent template for the test
        '''
        master_templ = Template()
        for templ in self.templates:
            template_url = "{}/{}".format(self._bucket_url,
                                          templ.name)
            # Create a test template for every set of test parameters
            if not templ.get_test_parameter_groups():
                stack_params = {}
                stack_params['TemplateURL'] = template_url
                stack_name = templ.resource_name() + 'Default'
                master_templ.add_resource(Stack(stack_name, **stack_params))
                continue

            for set_name, p_set in templ.get_test_parameter_groups().items():
                stack_params = {}
                stack_params['TemplateURL'] = template_url
                stack_name = templ.resource_name() + set_name.capitalize()
                params = p_set.dict()

                if params:
                    stack_params['Parameters'] = params
                master_templ.add_resource(Stack(stack_name, **stack_params))

        return master_templ.to_json()

    def _log_failed_stacks(self, stack_name):
        """Log stack events that have FAILED status"""

        # log parent stack failures
        self._log_failed_stack(stack_name)

        # if any child stacks with same prefix, log errors on those too
        child_stack_resp = self._client.list_stacks()
        for child_stack_summary in child_stack_resp.get('StackSummaries', []):
            found_stack_id = child_stack_summary.get('StackId', None)

            if stack_name in found_stack_id:
                self._log_failed_stack(found_stack_id)

    def _log_failed_stack(self, stack_id):
        """
        Log stack events that have FAILED somehow
        stack_id: name or stack_id of a failed stack

        boto3's describe_stacks() call actually accepts stack name or stack id,
        depending on the current state of the stack
        """

        stack_resp = self._client.describe_stacks(StackName=stack_id)
        stack_data = stack_resp['Stacks'][0]

        optional_reason = 'No reason found'
        if 'StackStatusReason' in stack_data:
            optional_reason = stack_data['StackStatusReason']

        # log the high level stack data
        LOG.error("Stack %s failure %s occurred: %s",
                  stack_data['StackName'],
                  stack_data['StackStatus'],
                  optional_reason)
        LOG.debug("Full trace: %s", str(stack_data))

        stack_events_resp = self._client.describe_stack_events(
            StackName=stack_id)

        for e in stack_events_resp['StackEvents']:
            if 'ResourceStatus' in e and 'FAILED' in e['ResourceStatus']:
                LOG.error("%s - %s: %s",
                          stack_id,
                          e['EventId'],
                          e['ResourceStatusReason'])


def _flatten_templates(templates):
    '''Gets a list of all the templates including dependencies'''
    return _recurse_dependencies(templates).values()


def _recurse_dependencies(templates):
    '''Flattens templates by recursively going through templates'''
    flattened_templ = {}
    for templ in templates:
        templ.prepare_test()  # testing hook may add dependencies

        if not flattened_templ.get(templ.name):
            flattened_templ[templ.name] = templ

        for _, test_param_group in templ.get_test_parameter_groups().items():
            if test_param_group.dependencies():
                flattened_templ.update(
                    _recurse_dependencies(test_param_group.dependencies()))
    return flattened_templ
