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

import os
import json

from logging import getLogger
from os import path

import boto3
import botocore

LOG = getLogger(__name__)


class S3Publisher(object):
    '''Publishes files to S3'''
    def __init__(self, bucket, public=True):
        self._client = boto3.client('s3')
        self.bucket = bucket
        self.public = public

        if not self._bucket_exists():
            raise Exception('Bucket {} does not exist'.format(
                self.bucket))

    def _bucket_exists(self):
        '''Check if S3 Bucket exists'''
        # TODO: Implement
        return True

    def newer(self, name, latest):
        '''
        Compare existing file with the latest

        - name - name of the file
        - latest - new contents to compare with existing
        '''
        resp = None
        try:
            resp = self._client.get_object(
                Bucket=self.bucket,
                Key=name,
            )

            body = resp.get('Body')
            body_obj = json.load(body)
            latest_obj = json.loads(latest)
            return bool(cmp(latest_obj, body_obj))
        except botocore.exceptions.ClientError as e:
            if 'specified key does not exist' in str(e):
                return True
            else:
                raise e
        except ValueError as e:
            if 'No JSON object could be decoded' not in str(e):
                raise e
        return True

    def publish_file(self, name, contents):
        ''' Publish a file to S3'''
        if not self.newer(name, contents):
            return
        acl = 'private'
        if self.public:
            acl = 'public-read'
        resp = self._client.put_object(
            Body=contents,
            Bucket=self.bucket,
            Key=name,
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
        '''
        file_path = path.join(self.base_path,
                              name)
        try:
            fil = open(file_path, 'r')
            existing = json.load(fil)
            fil.close()
            latest_obj = json.loads(latest)
            return bool(cmp(latest_obj, existing))
        except IOError as e:
            if 'No such file or directory:' not in str(e):
                raise e
        return True

    def publish_file(self, name, contents):
        '''Publish a file locally'''
        file_path = path.join(self.base_path,
                              name)
        if not self.newer(file_path, contents):
            return
        with open(file_path, 'w+') as fil:
            fil.write(contents)
