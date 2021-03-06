import os
import base64
import inspect
import urllib.parse

from flask.helpers import locked_cached_property
from jinja2 import Environment, ChoiceLoader, FileSystemLoader

from seedbox import config


class BaseIgnitionPackage(object):
    name = None
    template_context = {}

    def __init__(self, node, url_root):
        self.node = node
        self.cluster = node.cluster
        self.url_root = url_root

    def get_files(self):
        return ()

    def get_units(self):
        return ()

    def get_networkd_units(self):
        return ()

    def enable_unit(self, name):
        return {
            'name': name,
            'enable': True,
        }

    def get_unit(self, name, enable=False, template_name=None, additional_context=None):
        if template_name is None:
            template_name = name
        unit = {
            'name': name,
            'contents': self.render_template(template_name, additional_context),
        }
        if enable:
            unit['enable'] = True
        return unit

    def get_unit_dropins(self, unitname, dropins, enableunit=False):
        dropin = {
            'name': unitname,
            'dropins': [{
                'name': dropin,
                'contents': self.render_template('{}.d/{}'.format(unitname, dropin)),
            } for dropin in dropins],
        }
        if enableunit:
            dropin['enable'] = True
        return dropin

    def get_full_template_context(self, additional_context=None):
        context = {
            'config': config,
            'node': self.node,
            'cluster': self.cluster,
            'url_root': self.url_root,
        }

        context.update(self.get_template_context())

        if additional_context:
            context.update(additional_context)

        return context

    def get_template_context(self):
        return self.template_context

    def render_template(self, name, additional_context=None):
        return self.jinja_env.get_template(name).render(self.get_full_template_context(additional_context))

    @locked_cached_property
    def jinja_env(self):
        return Environment(loader=self.create_template_loader(),
                           keep_trailing_newline=True,
                           autoescape=False)

    def create_template_loader(self):
        template_roots = []

        cls = self.__class__
        while True:
            template_roots.append(os.path.dirname(inspect.getfile(cls)))
            cls = get_base_class(cls)
            if cls in (BaseIgnitionPackage, None):
                break

        return ChoiceLoader([FileSystemLoader(root) for root in template_roots])

    @staticmethod
    def to_data_url(data, mediatype='', b64=False):
        if b64:
            if not isinstance(data, bytes):
                data = data.encode('utf-8')
            return 'data:{};base64,{}'.format(mediatype, base64.b64encode(data).decode('ascii'))
        else:
            return 'data:{},{}'.format(mediatype, urllib.parse.quote(data))


def get_base_class(cls):
    for base in cls.__bases__:
        if issubclass(base, BaseIgnitionPackage):
            return base
    return None
