# Jetstream

Jetstream is a wrapper project around Troposphere to create and maintain
CloudFormation templates for AWS. This tools uses the awesome project
Troposphere to allow us to write out CF templates in Python and provides
and testing on top.

Features that are available with Jetstream and Troposphere:

- Uses Python to build CloudFormation templates (Troposphere)
- Uses Troposphere native Validations (Troposphere)
- Builds out full tests only on changed templates and dependencies (Jetstream)
- Is able to publish to S3 and to a Local File System (Jetstream)

## Setup

To install Jetstream from git you need to clone down the repository and
pip install.

```shell
git clone git@github.com:rackerlabs/jetstream
cd jetstream && pip install -e .
```

## Building

To build templates from a Python Package of templates
run `jetstream -m <python_package>`.

This will put the resulting templates in a directory named artifacts
in your CWD.

```shell
jetstream -m 'my_templates_package'
```

If you would like the templates to be tested before being generated.

```shell
jetstream -t
```

## Templates

Every template starts out as a new Object inherited from the JetstreamTemplate
class.

Example S3 Template

```python
import time

from jetsream.template import JetstreamTemplate, TestParameters
from troposphere import Parameter, Ref, Template, Join

class S3Bucket(JetstreamTemplate):
    '''S3 Bucket Template'''
    def __ini__(self):
        self.name = 's3_bucket.template'
        self.template = Template()
        self.test_params = TestParameters()

        self.template.add_version('2010-09-09')

        environment = self.template.add_parameter(Parameter(
            'Environment',
            Default='Development',
            Type='String',
            Description='Application environment'
            AllowedValues=['Development', 'Integration', 'PreProduction',
                           'Production', 'Staging', 'Test']
        ))

        bucket_name = self.template.add_parameter(Parameter(
            'BucketName',
            Type='String',
            Description='S3 Bucket name'
        ))

        s3_bucket = self.template.add_resource(Bucket(
            'S3Bucket',
            Tags=Tags(Environment=Ref(environment))
            BucketName=Ref(bucket_name)
        ))

        self.template.add_output(Ouput(
            'Arn',
            Value=Join('', ['arn:aws:s3:::', Ref(s3_bucket)])
        )))
```

## Testing

Templates provide you with options when it comes to what to set
during creation of a test stack using the test_params attribute.

For example to create a unique bucket name for a test of an
S3 Bucket:

```python
bucket_name = self.template.add_parameter(Parameter(
    'BucketName',
    Type='String',
    Description='S3 Bucket name'
))
test_bucket_name = "test-bucket-{}".format(int(time.time()))
test_params.add(TestParameter('BucketName', test_bucket_name))
```

Test Parameters also allow you to specify output from a
different stack by providing a template as the source.

```python
from s3_bucket import S3Bucket

s3_bucket = self.template.add_parameter(Parameter(
    'S3Bucket',
    Type='String',
    Description='S3 Bucket Arn'
))
test_params.add(TestParameter('S3Bucket', 'Arn', S3Bucket()))
```

Jetstream can handle multi-level template dependencies so the following
a legal dependency chain. Circular dependencies however will not work
and will cause the test to fail during CloudFormation creation.

A depends on B which depends on C which depends on D, B also depends on D.

```text
A --> B -> C
      |    |
      |    |
      | ----> D
```

If you extend the Jetstream template class, you can implement the following
methods to hook into jetstream's behavior from your subclass:

- `def prepare_document(self):` run before template documentation is generated
- `def prepare_generate(self):` run before template is generated
- `def prepare_test(self):` run before template is tested
