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

'''Code to publish the CloudFormationstemplates'''

import json
import re
import os
from os import path
from logging import getLogger

import boto3
import botocore

LOG = getLogger(__name__)

BUCKET_REGEX = r"^s3://([a-zA-Z0-9\_\-\.]+)/?([a-zA-Z0-9\_\-\.\/]+)?"


class S3Publisher(object):
    '''Publishes files to S3'''
    def __init__(self, bucket_path, public=True):
        self._client = boto3.client('s3')

        res = re.search(BUCKET_REGEX, bucket_path)
        if not res:
            raise AttributeError(
                "Invalid bucket path {}, must match {}".format(
                    bucket_path, BUCKET_REGEX))

        self.bucket = res.group(1)
        self.path = res.group(2)
        self.public = public

    def newer(self, name, latest):
        '''
        Compare existing file with the latest

        - name - name of the file
        - latest - new contents to compare with existing
        '''
        resp = None
        try:
            key = name
            if self.path:
                key = path.join(self.path, key)

            resp = self._client.get_object(
                Bucket=self.bucket,
                Key=key,
            )

            body = resp.get('Body')
            body_obj = json.load(body)
            latest_obj = json.loads(latest)
            return bool(cmp(latest_obj, body_obj))
        except botocore.exceptions.ClientError as excep:
            if 'specified key does not exist' in str(excep):
                return True
            else:
                raise excep
        except ValueError as excep:
            if 'No JSON object could be decoded' not in str(excep):
                raise excep
        return True

    def publish_file(self, name, contents):
        ''' Publish a file to S3'''
        if not self.newer(name, contents):
            return

        acl = 'private'
        if self.public:
            acl = 'public-read'

        key = name
        if self.path:
            key = path.join(self.path, key)

        resp = self._client.put_object(
            Body=contents,
            Bucket=self.bucket,
            Key=key,
            ACL=acl,
        )
        LOG.debug("Response: %s", resp)


class LocalPublisher(object):
    '''Local file Publisher'''
    def __init__(self, base_path):
        self.base_path = base_path

        if not path.isdir(self.base_path):
            os.makedirs(self.base_path)

    def newer(self, name, latest):
        '''
        Compares local file contents with latest
        copy to determine whether anything has changed
        returns False if files are identical, True otherwise
        '''
        file_path = path.join(self.base_path,
                              name)
        try:
            fil = open(file_path, 'r')
            existing = json.load(fil)
            fil.close()
            latest_obj = json.loads(latest)
            return bool(cmp(latest_obj, existing))
        except IOError as excep:
            if 'No such file or directory:' not in str(excep):
                raise excep
        except ValueError as excep:
            if 'No JSON object could be decoded' not in str(excep):
                raise excep

            # parse as string, the JSON parser failed
            with open(file_path, 'r') as fh:
                existing = fh.read()
            return bool(cmp(latest, existing))

        # fall back to saying the files are different
        return True

    def publish_file(self, name, contents):
        '''Publish a file locally'''
        file_path = path.join(self.base_path,
                              name)
        if not self.newer(file_path, contents):
            return
        with open(file_path, 'w+') as fil:
            fil.write(contents)
