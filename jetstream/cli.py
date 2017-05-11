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
        raise Exception("Unsupported publisher {}".format(args.publisher))

    templates = template.load_templates(args.package)
    updated_templates = []
    updated_documentation = []
    for _, tmpl in templates.items():
        if publish.newer(tmpl.name, tmpl.generate(fmt=args.format)):
            updated_templates.append(tmpl)

        if args.document:
            if publish.newer(tmpl.document_name(), tmpl.document()):
                updated_documentation.append(tmpl)
    if updated_templates:
        print("Updated Templates: " + ', '.join(
            [t.name for t in updated_templates]))
    if updated_documentation:
        print("Updated Documentation: " + ', '.join(
            [t.name for t in updated_documentation]))

    if not updated_templates and not updated_documentation:
        print("No updated templates or documents found")
        return

    # If the test flag is set and templates have been updated, run a test
    test_passed = True
    if args.test and updated_templates:
        test = testing.Test(updated_templates, dry_run=args.dry_test)
        try:
            test_passed = test.run()
        except (KeyboardInterrupt, SystemExit):
            print("Interrupt caught... cleaning up the test")
            test.cleanup()
            sys.exit(1)

        if not args.debug:
            if args.cleanup == 'pass' or args.cleanup == 'failure' and \
                    test_passed:
                test.cleanup()
            elif args.cleanup == 'failure' and not test_passed:
                test.cleanup()

    # Publish latest templates
    if test_passed:
        if args.no_publish:
            print("No publish set ... not publishing")
        else:
            for tmpl in updated_templates:
                publish.publish_file(
                    tmpl.name,
                    tmpl.generate(fmt=args.format)
                )

            if args.document:
                for tmpl in updated_documentation:
                    publish.publish_file(tmpl.document_name(), tmpl.document())
    else:
        print("Testing Failed :(", file=sys.stderr)
        sys.exit(1)


def signal_term_handler(_signal, _frame):
    '''Exit, throwing SystemExit automatically causing cleanup'''
    sys.exit(1)


def main():
    '''Main function'''
    import signal
    signal.signal(signal.SIGTERM, signal_term_handler)

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
    parser.add_argument('--dry-test', '-T', dest='dry_test',
                        action='store_true',
                        help='Generate test templates locally',
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
    parser.add_argument('--format', '-f', dest='format',
                        help='json or yaml format',
                        choices=['json', 'yaml'],
                        default='json')

    test_conditions = ['never', 'failure', 'pass']
    cleanup_help = "Test condition to cleanup ({}) defaults to pass".format(
        ', '.join(test_conditions))
    parser.add_argument('--clean-on', dest='cleanup',
                        help=cleanup_help,
                        default='pass')

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
