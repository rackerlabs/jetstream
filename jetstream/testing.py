# Copyright 2016 Rackspace US, Inc.
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

from logging import getLogger
from troposphere import Template
from troposphere.cloudformation import Stack
from jetstream.publisher import S3Publisher

import boto3

LOG = getLogger(__name__)


class Test(object):
    '''
    Test Object

    CRUD for CloudFormation testing
    '''
    def __init__(self, templates):
        self.templates = _flatten_templates(templates)
        timestamp = int(time.time())
        self._bucket = "jetstream-test-{}".format(timestamp)
        self._stack_name = "JetstreamTest{}".format(timestamp)
        self._bucket_url = "https://s3.amazonaws.com/{}".format(self._bucket)
        self._client = boto3.client('cloudformation')
        self.s3_publisher = S3Publisher(self._bucket, public=False)

    def run(self):
        '''Run the test'''
        LOG.info("Creating bucket %s", self._bucket)
        boto3.client('s3').create_bucket(Bucket=self._bucket)
        LOG.info("Bucket %s created", self._bucket)

        LOG.info("Uploading files")
        self.s3_publisher.publish_file('master.template',
                                       self._parent_template())
        for templ in self.templates:
            LOG.info("Uploading file: %s", templ.name)
            self.s3_publisher.publish_file(templ.name,
                                           templ.generate(testing=True))

        LOG.info("Creating stack %s...", self._stack_name)
        self._build_stack()
        return self._wait_results(self._stack_name)

    def cleanup(self):
        '''Clean up the testing stack and bucket'''
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
                LOG.error("Stack %s failure occurred: %s",
                          stack_name, stack_status)
                LOG.error("Reason: %s", str(stack_info))
                stack_status_reason = stack_info['StackStatusReason']
                LOG.error("Reason: %s", stack_status_reason)

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

    def _parent_template(self):
        '''
        Generate the parent template for the test
        '''
        master_templ = Template()
        for templ in self.templates:
            stack_name = templ.resource_name()
            templ_url = "{}/{}".format(self._bucket_url, templ.name)
            master_templ.add_resource(Stack(stack_name,
                                      TemplateURL=templ_url,
                                      Parameters=templ.test_params.dict()))

        return master_templ.to_json()


def _flatten_templates(templates):
    '''Gets a list of all the templates including dependencies'''
    return _recurse_dependencies(templates).values()


def _recurse_dependencies(templates):
    '''Flattens templates by recursively going through templates'''
    flattened_templ = {}
    for templ in templates:
        if not flattened_templ.get(templ.name):
            flattened_templ[templ.name] = templ
        if templ.test_params.dependencies():
            flattened_templ.update(
                _recurse_dependencies(templ.test_params.dependencies()))
    return flattened_templ
