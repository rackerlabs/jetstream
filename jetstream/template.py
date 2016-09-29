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

'''Template Class to be overridden by Template'''

import sys
import traceback
import collections
import json
import copy

from datetime import datetime
from importlib import import_module
from troposphere import GetAtt


def load_template(package, template):
    '''
    Loads a single template
    '''
    try:
        module, template_class = template.split('.')
        imported_module = import_module("{}.{}".format(package, module))
        template_object = getattr(imported_module, template_class)()
        return template_object
    except:
        extype, ex, tb = sys.exc_info()
        traceback.format_exception_only(extype, ex)[-1]
        message = "Failed to load template %s: %s" % (template, str(ex))
        raise RuntimeError, message, tb


def load_templates(package):
    '''
    Loads templates from a given module and
    returns a map of loaded template objects
    '''
    template_objects = {}
    imported_module = import_module(package)

    for template in imported_module.templates:
        template_object = load_template(package, template)
        template_objects[template_object.name] = template_object

    return template_objects


class TestParameter(object):
    '''Test Parameter'''
    def __init__(self, name, value, source=None):
        self._name = name
        self._value = value
        self._source = source

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

        return GetAtt(self._source.resource_name(), "Outputs." + self._value)


class TestParameters(object):
    '''Test Parameters object'''
    def __init__(self):
        self._parameters = []

    def add(self, parameter):
        '''Add a Parameter'''
        if not isinstance(parameter, TestParameter):
            raise ValueError("Parameter must be of type TestParameter")
        self._parameters.append(parameter)

    def dict(self):
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

        return deps.values()


class JetstreamTemplate(object):
    '''Template class'''
    def __init__(self):
        '''Initialize class instance variables'''
        self.template = None
        self.name = None
        self._resource_name = None
        self.test_params = None

    def _required_attrs(self, attrs):
        '''Validate that required attrs were set in a template'''
        for attr in attrs:
            if not hasattr(self, attr) or getattr(self, attr) is None:
                raise Exception("Missing required template attribute " + attr)

    def _default_attr(self, name, default):
        '''Set default attrs if they dont exist'''
        if not hasattr(self, name):
            setattr(self, name, default)

    def document_name(self):
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
        self._required_attrs(['template', 'name'])
        doc = []
        header_text = "{} FAWS Template".format(self.resource_name())
        doc.append(header_text + "\n" + ('=' * len(header_text)))
        doc.append(self.template.description)
        doc.append("Last updated on `{}`\n".format(datetime.now()))
        # Parameters
        doc.append('###Parameters')
        for name, param in self.template.parameters.items():
            doc.append('####' + name)
            for prop, value in param.properties.items():
                doc.append("- {}: `{}`".format(prop, value))

        # Outputs
        doc.append('###Outputs')
        for name in self.template.outputs.keys():
            doc.append("- `{}`".format(name))

        return "\n".join(doc)

    def generate(self, testing=False):
        '''Returns the generated cf template'''

        # validation steps and proper resource name
        self._required_attrs(['template', 'name'])

        tmpl = self.template
        # Remove DeletionPolicies for templates during testing
        if testing:
            # We are going to modify this template during testing
            # but do not want to affect the original.
            tmpl = copy.deepcopy(self.template)
            for _, resource in tmpl.resources.items():
                try:
                    resource.resource.pop('DeletionPolicy')
                except KeyError:
                    pass

        original_template = tmpl.to_json(sort_keys=False)
        parsed_template = json.loads(original_template)
        encoded_template = json.dumps(
            parsed_template,
            sort_keys=False, indent=4,
            cls=JetstreamEncoder)

        return encoded_template

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
            d = collections.OrderedDict()
            for k in TOP_LEVEL_DICT_ORDER:
                if k in obj:
                    d[k] = obj[k]

            return json.JSONEncoder.encode(self, d)
        return json.JSONEncoder.encode(self, obj)


def _reformat_name(name):
    '''Reformat Template name to be used as a resource name'''
    lst = name.split('_')
    for index in range(0, len(lst)):
        lst[index] = lst[index].capitalize()
    return ''.join(lst)
