import json
import base64
import urllib.parse
from flask import request

import config
import models


def render(node, indent=False):
    from . import render_template

    def render_tpl(template_name):
        return render_template(template_name, node)

    def get_unit(name, enable=False, dropins=None):
        if dropins:
            return {
                'name': name,
                'enable': enable,
                'dropins': [{
                    'name': dropin,
                    'contents': render_tpl('dropins/' + name + '/' + dropin),
                } for dropin in dropins],
            }
        else:
            return {
                'name': name,
                'enable': enable,
                'contents': render_tpl('units/' + name),
            }

    ssh_keys = [user.ssh_key for user in node.cluster.users.filter(models.User.ssh_key != '')]

    files = [
        {
            'filesystem': 'root',
            'path': config.ca_cert_path,
            'mode': 0o444,
            'contents': {
                'source': request.url_root + 'credentials/ca.pem',
            },
        },
        {
            'filesystem': 'root',
            'path': config.node_cert_path,
            'mode': 0o444,
            'contents': {
                'source': request.url_root + 'credentials/node.pem',
            },
        },
        {
            'filesystem': 'root',
            'path': config.node_key_path,
            'mode': 0o400,
            'contents': {
                'source': request.url_root + 'credentials/node-key.pem',
            },
        }
    ]

    if config.install_etc_hosts:
        files.append({
            'filesystem': 'root',
            'path': '/etc/hosts',
            'mode': 0o644,
            'contents': {
                'source': to_data_url(render_tpl('hosts')),
            },
        })

    units = [
        get_unit('provision-report.service', enable=True),
        get_unit('flanneld.service', dropins=['40-ExecStartPre-symlink.conf']),
        get_unit('docker.service', dropins=['40-flannel.conf']),
        get_unit('kubelet.service', enable=True),
        get_unit('k8s-addons.service', enable=True),
    ]

    if config.k8s_runtime == 'rkt':
        units += [
            get_unit('rkt-api.service', enable=True),
            get_unit('load-rkt-stage1.service', enable=True),
        ]

    if node.is_etcd_server:
        etcd_version = node.cluster.etcd_version
        if etcd_version == 2:
            unit_name = 'etcd2.service'
        elif etcd_version == 3:
            unit_name = 'etcd-member.service'
        else:
            raise Exception('Unknown etcd version', etcd_version)
        units.append(get_unit(unit_name, enable=True, dropins=['40-etcd-cluster.conf']))
        units.append(get_unit('locksmithd.service', dropins=['40-etcd-lock.conf']))

    cfg = {
        'ignition': {
            'version': '2.0.0',
            'config': {},
        },
        'storage': {
            'files': files,
        },
        'networkd': {},
        'passwd': {
            'users': [{
                'name': 'core',
                'sshAuthorizedKeys': ssh_keys,
            }],
        },
        'systemd': {
            'units': units,
        },
    }

    if indent:
        return json.dumps(cfg, indent=2)
    else:
        return json.dumps(cfg, separators=(',', ':'))


def to_data_url(data, mediatype='', b64=False):
    if b64:
        if not isinstance(data, bytes):
            data = data.encode('utf-8')
        return 'data:{};base64,{}'.format(mediatype, base64.b64encode(data).decode('ascii'))
    else:
        return 'data:{},{}'.format(mediatype, urllib.parse.quote(data))
