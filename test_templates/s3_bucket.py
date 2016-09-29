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

'''S3 Bucket Template'''


import time

from jetstream.template import JetstreamTemplate, TestParameters, TestParameter
from troposphere import Parameter, Ref, Tags, Template, Output, Join
from troposphere.s3 import Bucket


class S3Bucket(JetstreamTemplate):
    '''S3 Bucket Template'''
    def __init__(self):
        self.name = 's3.template'
        self.template = Template()
        self.test_params = TestParameters()

        self.template.add_version("2010-09-09")

        AccessControl = self.template.add_parameter(Parameter(
            "AccessControl",
            Default="BucketOwnerFullControl",
            Type="String",
            Description="Define ACL for Bucket",
            AllowedValues=["AuthenticatedRead", "AwsExecRead",
                           "BucketOwnerRead", "BucketOwnerFullControl",
                           "LogDeliveryWrite", "Private",
                           "PublicRead", "PublicReadWrite"],
        ))
        self.test_params.add(TestParameter("AccessControl", "Private"))

        Environment = self.template.add_parameter(Parameter(
            "Environment",
            Default="Development",
            Type="String",
            Description="Application environment",
            AllowedValues=["Development", "Integration",
                           "PreProduction", "Production", "Staging", "Test"],
        ))
        self.test_params.add(TestParameter("Environment", "Integration"))

        BucketName = self.template.add_parameter(Parameter(
            "BucketName",
            AllowedPattern="([a-z0-9\\.-]+)",
            ConstraintDescription="""
    Must contain only lowercase letters, numbers, periods (.), and dashes (-).
    """,
            Type="String",
            Description="The name of the bucket to use. Must be unique.",
        ))
        bucket_name = "test-bucket-{}".format(int(time.time()))
        self.test_params.add(TestParameter("BucketName", bucket_name))

        self.template.add_resource(Bucket(
            "S3Bucket",
            AccessControl=Ref(AccessControl),
            Tags=Tags(
                Name=Ref("AWS::StackName"),
                ServiceProvider="Rackspace",
                Environment=Ref(Environment),
            ),
            BucketName=Ref(BucketName),
        ))

        self.template.add_output(Output(
            "Arn",
            Value=Join('', ['arn:aws:s3:::', Ref(BucketName)])
        ))
