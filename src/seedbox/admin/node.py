from flask import request, Response, flash, redirect
from flask_admin import expose
from flask_admin.form import rules
from flask_admin.helpers import get_redirect_target
from flask_admin.model.template import macro

from seedbox import pki, models, config_renderer
from .base import ModelView


class NodeView(ModelView):
    column_list = [
        'cluster',
        'fqdn',
        'ip',
        'maintenance_mode',
        'credentials',
        'config',
    ]
    list_template = 'admin/node_list.html'
    details_template = 'admin/node_details.html'
    form_excluded_columns = [
        'credentials',
        'target_config_version',
        'active_config_version',
        'provisions',
        'disks',
    ]
    column_formatters = {
        'credentials': macro('render_credentials'),
        'config': macro('render_config'),
    }
    column_labels = {
        'ip': "Public IP",
        'fqdn': "Fully Qualified Domain Name",
        'maintenance_mode': "Maintenance mode",
        'debug_boot': "Debug boot",
        'coreos_autologin': "Enable terminal autologin",
        'linux_consoles': "Linux console devices",
        'disable_ipv6': "Disable IPv6 in Linux kernel",
        'is_etcd_server': "etcd server",
        'is_k8s_schedulable': "Kubernetes schedulable",
        'is_k8s_master': "Kubernetes master",
        'mountpoints': 'Additional mountpoints',
        'addresses': 'Additional IP addresses',
    }
    column_descriptions = {
        'maintenance_mode': "If this is enabled, node will be booted in minimal CoreOS environment without "
                            "touching root partition.",
        'debug_boot': "Forward all system journal messages to kmsg for troubleshooting.",
        'coreos_autologin': "If this is set, main terminal will be logged-in with `core` user after boot. Useful "
                            "for debugging. Don't enable in production.",
        'linux_consoles': "Passed to kernel as `console` arguments. (Separate by comma.)",
        'disable_ipv6': "Passed to kernel as `ipv6.disable=1` argument.",
        'is_etcd_server': "Run etcd server on this node and connect other nodes to it.",
        'is_k8s_schedulable': "Run kubelet on this node and register it as schedulable.",
        'is_k8s_master': "Run kubelet on this node and add persistent kube-apiserver, kube-controller-manager, "
                         "kube-scheduler pods to it.",
    }
    inline_models = [
        (models.Mountpoint, {
            'column_descriptions': {
                'what': 'Device to mount.',
                'where': 'Mount path.',
                'wanted_by': 'WantedBy systemd unit.',
                'is_persistent': 'Use this partition to store critical data that should survive reboots.',
            }
        }),
        (models.Address, {
            'column_descriptions': {
                'interface': 'Network interface.',
                'ip': 'IP address.',
            }
        }),
    ]
    form_rules = [
        rules.Field('cluster'),
        rules.Field('ip'),
        rules.Field('fqdn'),
        rules.FieldSet([
            'maintenance_mode',
            'debug_boot',
            'coreos_autologin',
            'linux_consoles',
            'disable_ipv6',
            'mountpoints',
            'addresses',
            'additional_kernel_cmdline',
        ], 'Boot'),
        rules.FieldSet([
            'is_etcd_server',
            'is_k8s_schedulable',
            'is_k8s_master',
        ], 'Components'),
    ]

    # without this, Node is saved to database before on_model_change() gets called
    # and this happens only when there is inline_models
    def create_model(self, *args, **kwargs):
        with self.session.no_autoflush:
            return super().create_model(*args, **kwargs)

    def _issue_creds(self, model):
        with self.session.no_autoflush:
            ca_creds = model.cluster.ca_credentials
        creds = models.CredentialsData()

        creds.cert, creds.key = pki.issue_certificate('system:node:' + model.fqdn,
                                                      ca_cert=ca_creds.cert,
                                                      ca_key=ca_creds.key,
                                                      organizations=['system:nodes'],
                                                      san_dns=model.certificate_alternative_dns_names,
                                                      san_ips=model.certificate_alternative_ips,
                                                      certify_days=10000,
                                                      is_web_server=True,
                                                      is_web_client=True)
        self.session.add(creds)
        model.credentials = creds

    def on_model_change(self, form, model, is_created):
        if is_created:
            self._issue_creds(model)
        else:
            model.target_config_version += 1

    def on_model_delete(self, model):
        model.mountpoints.delete()
        model.addresses.delete()

    def after_model_delete(self, model):
        models.CredentialsData.query.filter_by(id=model.credentials_id).delete()

    @expose('/reissue-credentials', methods=['POST'])
    def reissue_creds_view(self):
        model = self.get_one(request.args.get('id'))
        model.target_config_version += 1
        self._issue_creds(model)
        self.session.add(model)
        self.session.commit()
        return_url = get_redirect_target() or self.get_url('.index_view')
        flash('The credentials successfully reissued', 'success')
        return redirect(return_url)

    @expose('/target-ignition.json')
    def target_ignition_config_view(self):
        node = self.get_one(request.args.get('id'))
        response = config_renderer.ignition.render(node, indent=True)
        return Response(response, mimetype='application/json')

    @expose('/target.ipxe')
    def target_ipxe_config_view(self):
        node = self.get_one(request.args.get('id'))
        response = config_renderer.ipxe.render(node, request.url_root)
        return Response(response, mimetype='text/plain')
