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

'''EC2 Instance Template'''


from jetstream.template import (JetstreamTemplate, TestParameterGroup,
                                TestParameter, TestParameterGroups)
from troposphere import Parameter, Ref, Tags, Template
from troposphere.ec2 import Instance
from troposphere.iam import InstanceProfile, Role, Policy

from test_templates.s3_bucket import S3Bucket


class EC2Instance(JetstreamTemplate):
    '''EC2 Template'''
    def __init__(self):
        self.name = 'ec2.template'
        self.template = Template()

        self.template.add_version("2010-09-09")
        self.test_parameter_groups = TestParameterGroups()
        default_test_params = TestParameterGroup()
        self.test_parameter_groups.add(default_test_params)

        Environment = self.template.add_parameter(Parameter(
            "Environment",
            Default="Development",
            Type="String",
            Description="Application environment",
            AllowedValues=["Development", "Integration",
                           "PreProduction", "Production", "Staging", "Test"],
        ))
        default_test_params.add(TestParameter("Environment", "Integration"))

        Bucket = self.template.add_parameter(Parameter(
            "S3Bucket",
            Type="String",
            Description="S3 Bucket",
        ))
        default_test_params.add(TestParameter("S3Bucket", "Arn", S3Bucket()))
        ImageId = self.template.add_parameter(Parameter(
            "ImageId",
            Type="String",
            Description="Image Id"
        ))
        default_test_params.add(TestParameter("ImageId", "ami-6869aa05"))

        self.template.add_resource(Instance(
            "EC2Instance",
            Tags=Tags(
                Name=Ref("AWS::StackName"),
                ServiceProvider="Rackspace",
                Environment=Ref(Environment),
            ),
            InstanceType="t2.small",
            ImageId=Ref(ImageId),
        ))
        EC2Policy = Policy(
            PolicyName="EC2_S3_Access",
            PolicyDocument={
                "Statement": [{
                    "Effect": "Allow",
                    "Action": "s3:*",
                    "Resource": Ref(Bucket)
                }]
            })

        EC2InstanceRole = self.template.add_resource(Role(
            "EC2InstanceRole",
            AssumeRolePolicyDocument={
                "Statement": [{
                    "Effect": "Allow",
                    "Principal": {
                        "Service": ["ec2.amazonaws.com"]
                    },
                    "Action": ["sts:AssumeRole"]
                }]
            },
            Path="/",
            Policies=[EC2Policy],
        ))
        self.template.add_resource(InstanceProfile(
            "EC2InstanceProfile",
            Path="/",
            Roles=[Ref(EC2InstanceRole)]
        ))
