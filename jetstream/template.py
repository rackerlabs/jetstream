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

'''Template Class to be overridden by Template'''

import sys
import os
import collections
import json
import copy

from importlib import import_module
from troposphere import GetAtt, BaseAWSObject
import cfn_flip
from . import TOPLEVEL_METADATA_KEY


def load_template(package, template):
    '''
    Loads a single template
    '''
    try:
        module, template_class = template.split('.')
        imported_module = import_module("{}.{}".format(package, module))
        template_object = getattr(imported_module, template_class)()
        return template_object
    except:  # noqa
        _, excep, trace = sys.exc_info()
        message = "Failed to load template %s: %s" % (template, str(excep))
        raise RuntimeError(message).with_traceback(trace)


def load_templates(package):
    '''
    Loads templates from a given module and
    returns a map of loaded template objects
    '''
    template_objects = {}

    saved_path = sys.path
    sys.path.insert(0, os.getcwd())

    imported_module = import_module(package)

    for template in imported_module.templates:
        template_object = load_template(package, template)
        template_objects[template_object.name] = template_object

    sys.path = saved_path

    return template_objects


class TestParameter(object):
    '''Test Parameter'''
    def __init__(self, name, value, source=None, source_set_name=None):
        # If the name passed in was an AWSObject then
        # set the _name to the title of the object.
        if isinstance(name, BaseAWSObject):
            self._name = name.title
        else:
            self._name = name

        if not isinstance(value, str):
            s = "TestParameter value must be of type string, not {}".format(
                str(type(value))
            )
            raise TypeError(s)

        self._value = value
        self._source = source

        self._source_set_name = source_set_name
        if not self._source_set_name:
            self._source_set_name = 'default'

    def source(self):
        '''Returns template the value comes from'''
        return self._source

    def name(self):
        '''Returns the name of the test parameter'''
        return self._name

    def value(self):
        '''Returns the value of the test parameter'''
        if not self._source:
            return self._value

        return GetAtt(
            self._source.resource_name() + self._source_set_name.capitalize(),
            "Outputs." + self._value)


class TestParameterGroup(object):
    '''Test Parameters object'''
    def __init__(self):
        self._parameters = []

    def add(self, parameter):
        '''Add a Parameter'''
        if not isinstance(parameter, TestParameter):
            raise ValueError("Parameter must be of type TestParameter")
        self._parameters.append(parameter)

    def dict(self):
        '''Returns the Test Parameters as a dictionary'''
        params = {}
        for param in self._parameters:
            params[param.name()] = param.value()

        return params

    def all(self):
        '''Return all parameters'''
        return self._parameters

    def dependencies(self):
        '''Return all dependencies listed in the parameters'''
        deps = {}
        for param in self._parameters:
            source = param.source()
            if source:
                deps[source.name] = source

        return list(deps.values())


class TestParameterGroups(object):
    '''Test ParameterGroups object'''
    def __init__(self):
        self._groups = {}

    def groups(self):
        '''return the test parameter groups'''
        return self._groups

    def add(self, group, name=None):
        '''Method to add a new TestParameterGroup'''
        if not name:
            self._groups['default'] = group
        else:
            self._groups[name] = group

    def remove(self, name):
        '''Removes a group by name'''
        if not self._groups.get(name):
            raise AttributeError(
                'No TestParameterGroup named {} found'.format(name))
        del self._groups[name]


class JetstreamTemplate(object):
    '''Template class'''
    def __init__(self):
        '''Initialize class instance variables'''
        self.template = None
        self.name = None
        self._resource_name = None
        self.test_parameter_groups = None

    def get_test_parameter_groups(self):
        ''' Returns all Test Parameter Groups Associated with the template'''
        if (hasattr(self, 'test_parameter_groups') and
                self.test_parameter_groups):
            return self.test_parameter_groups.groups()

        return {}

    def prepare_document(self):
        '''Lifecycle hook in case template wants to do any additional work'''
        # override this method to run anything
        pass

    def prepare_generate(self):
        '''Lifecycle hook in case template wants to do any additional work'''
        # override this method to run anything
        pass

    def prepare_test(self):
        '''Lifecycle hook in case template wants to do any additional work'''
        # override this method to run anything
        pass

    def _required_attrs(self, attrs):
        '''Validate that required attrs were set in a template'''
        for attr in attrs:
            if not hasattr(self, attr) or getattr(self, attr) is None:
                raise Exception("Missing required template attribute %s for %s"
                                % (attr, type(self).__name__))

    def _default_attr(self, name, default):
        '''Set default attrs if they dont exist'''
        if not hasattr(self, name):
            setattr(self, name, default)

    def document_name(self):
        '''Returns the Markdown Document name'''
        return self.name.split('.')[0] + '.md'

    def resource_name(self):
        '''Return a name to be used as a stack name in testing'''
        if hasattr(self, '_resource_name') and self._resource_name:
            return self._resource_name

        if not self.name:
            raise ValueError("name attribute must be set")

        self._resource_name = _reformat_name(self.name.split('.')[0])
        return self._resource_name

    def document(self):
        '''Returns documentation for the template'''
        self.prepare_document()  # prepare template

        self._required_attrs(['template', 'name'])
        doc = []
        header_text = "{} FAWS Template".format(self.resource_name())
        doc.append(header_text + "\n" + ('=' * len(header_text)))
        doc.append(self.template.description)

        # Parameters
        doc.append('### Parameters')
        for name, param in self.template.parameters.items():
            doc.append('\n#### ' + name)
            for prop, value in param.properties.items():
                doc.append("- {}: `{}`".format(prop, value))

        # Outputs
        doc.append('\n### Outputs')
        for name in self.template.outputs.keys():
            doc.append("- `{}`".format(name))

        return "\n".join(doc)

    @staticmethod
    def __generate_metadata(additional_metadata=None):
        """Add additional template metadata provided by CLI args"""
        jetstream_metadata = {}
        if additional_metadata:
            for kv_pair in additional_metadata:
                k, v = kv_pair.split('=')
                jetstream_metadata[k] = v

        return jetstream_metadata

    def generate(self, testing=False, fmt='json', additional_metadata=None):
        '''Returns the generated cf template'''
        self.prepare_generate()  # prepare template

        # validation steps and proper resource name
        self._required_attrs(['template', 'name'])

        tmpl = self.template
        # Remove DeletionPolicies for templates during testing
        if testing:
            # We are going to modify this template during testing
            # but do not want to affect the original.
            tmpl = copy.deepcopy(self.template)
            for _, resource in tmpl.resources.items():
                resource.resource['DeletionPolicy'] = 'Delete'

        try:
            if additional_metadata:
                jetstream_metadata = self.__generate_metadata(
                    additional_metadata)

                if jetstream_metadata:
                    tmpl.metadata[TOPLEVEL_METADATA_KEY] = jetstream_metadata

            # Handle JSON.dumps failing
            encoded_template = json.dumps(
                tmpl.to_dict(),
                sort_keys=False, indent=2,
                separators=(',', ': '),
                cls=JetstreamEncoder)

            if fmt == 'yaml':
                encoded_template = cfn_flip.to_yaml(encoded_template)

            return encoded_template
        except: # noqa
            _, excep, trace = sys.exc_info()
            class_name = type(self).__name__
            message = "Failed to build JSON for template %s: %s" \
                % (class_name, str(excep))
            raise RuntimeError(message).with_traceback(trace)


TOP_LEVEL_DICT_ORDER = [
    'AWSTemplateFormatVersion', 'Description', 'Metadata',
    'Parameters', 'Conditions', 'Mappings', 'Resources', 'Outputs'
]


class JetstreamEncoder(json.JSONEncoder):
    '''Extend regular JSON encoder class our own formats, when needed'''

    def encode(self, obj):
        '''Wrap calls to encode JSON, re-ordering the top level object if we
        see it passed through.'''

        # if it's the top level dict, do a reasonable order
        if isinstance(obj, (dict)) and 'Resources' in obj:
            dikt = collections.OrderedDict()
            for k in TOP_LEVEL_DICT_ORDER:
                if k in obj:
                    dikt[k] = obj[k]

            return json.JSONEncoder.encode(self, dikt)
        return json.JSONEncoder.encode(self, obj)


def _reformat_name(name):
    '''Reformat Template name to be used as a resource name'''
    lst = name.split('_')
    for index in range(0, len(lst)):
        lst[index] = lst[index].capitalize()
    return ''.join(lst)
