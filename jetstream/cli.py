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

'''Jetstream Command Line Interface'''
from __future__ import print_function
from os import path

import sys
import logging

from jetstream import publisher, template, testing
from jetstream import __version__

LOG = logging.getLogger(__name__)


def _execute(args):
    '''Application Execution'''
    publish = None
    if args.publisher == 'local':
        publish = publisher.LocalPublisher(args.path)
    elif args.publisher == 's3':
        publish = publisher.S3Publisher(args.path, args.public)
    else:
        print("Unsupported Publisher {}".format(args.publisher))

    templates = template.load_templates(args.package)
    updated_templates = []
    for name, tmpl in templates.items():
        if publish.newer(tmpl.name, tmpl.generate()):
            updated_templates.append(tmpl)
    if updated_templates:
        print("Updated Templates: " + ', '.join(
            map(lambda n: n.name, updated_templates)))
    else:
        print("No updated templates found")
        return

    # If the test flag is set then run a test
    test_passed = True
    if args.test and updated_templates:
        test = testing.Test(updated_templates)
        test_passed = test.run()

        # If not running in debug mode clean up the test
        if not args.debug and test_passed:
            test.cleanup()

    # Publish latest templates
    if test_passed:
        if args.no_publish:
            print("No publish set ... not publishing")
        else:
            for tmpl in updated_templates:
                publish.publish_file(tmpl.name, tmpl.generate())
                if args.document:
                    publish.publish_file(tmpl.document_name(), tmpl.document())
    else:
        print("Testing Failed :(", file=sys.stderr)
        sys.exit(1)


def main(argv=None):
    '''Main function'''
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--version', '-v',
                        action='version',
                        version='version %s' % __version__)
    parser.add_argument('--publisher', '-P', dest='publisher',
                        help='Where to publish the templates',
                        default='local')
    parser.add_argument('--package', '-m', dest='package',
                        help='CloudFormation Templates Package',
                        required=True)
    parser.add_argument('--path', '-p', dest='path',
                        help='Path to publish the templates to',
                        default=path.abspath('./artifacts'))
    parser.add_argument('--debug', '-D', dest='debug',
                        action='store_true',
                        help='Whether to run in Debug mode',
                        default=False)
    parser.add_argument('--test', '-t', dest='test',
                        action='store_true',
                        help='Whether to run tests',
                        default=False)
    parser.add_argument('--documentation', '-d',
                        dest='document',
                        action='store_true',
                        help='Publish Documentation',
                        default=False)
    parser.add_argument('--no-publish', '-n',
                        dest='no_publish',
                        help='Do not publish CloudFormation results',
                        action='store_true',
                        default=False)
    parser.add_argument('--public', action='store_true',
                        help='Whether S3 Published documents should be public',
                        default=False)

    verbose = parser.add_mutually_exclusive_group()
    verbose.add_argument('-V', dest='loglevel', action='store_const',
                         const=logging.INFO,
                         help='Set log-level to INFO')
    verbose.add_argument('-VV', dest='loglevel', action='store_const',
                         const=logging.DEBUG,
                         help='Set log-level to DEBUG.')
    parser.set_defaults(loglevel=logging.WARNING)

    args = parser.parse_args()
    logging.basicConfig(level=args.loglevel)

    _execute(args)
