#!/usr/bin/env python3
# Copyright (C) 2017  Ghent University
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
from shutil import rmtree
from subprocess import check_call, run, CalledProcessError

from charms.reactive import (
    set_flag,
    clear_flag,
    when_not,
    when,
    when_any,
    is_flag_set,
)
from charms.reactive.relations import endpoint_from_flag
from charms.reactive.helpers import data_changed

from charmhelpers.core.hookenv import log, config
from charmhelpers.core import templating, unitdata

from charms.layer import status
from charms.layer import lets_encrypt
from charms.layer.nginx_config_helper import (
    NginxConfig,
    NginxConfigError,
    NginxModule,
)


config = config()


########################################################################
# Install
########################################################################

@when('apt.installed.apache2-utils',
      'nginx.available',
      'nginx-config.installed')
@when_not('ssl-termination.installed')
def install_ssl_termination():
    nginxcfg = NginxConfig()
    http_path = os.path.join(nginxcfg.http_available_path, 'http')
    ssl_term_path = os.path.join(nginxcfg.http_available_path, 'ssl-termination')
    os.makedirs(http_path, exist_ok=True)
    os.makedirs(ssl_term_path, exist_ok=True)
    set_flag('ssl-termination.installed')
    status.blocked('Waiting for fqdn subordinates or http relation')


########################################################################
# SSL-termination interface
########################################################################

@when('ssl-termination.installed',
      'endpoint.ssl-termination.update')
@when_not('endpoint.ssl-termination.joined')
def no_ssl_term_relations():
    NginxConfig().delete_all_config(NginxModule.HTTP, 'ssl-termination')
    NginxConfig().delete_all_config(NginxModule.STREAM)
    unitdata.kv().set('sslterm.cert-requests', [])
    clear_flag('endpoint.ssl-termination.update')
    set_flag('ssl-termination.report')

@when('ssl-termination.installed',
      'endpoint.ssl-termination.joined')
@when_any('endpoint.ssl-termination.update')
def get_certificate_requests():
    endpoint = endpoint_from_flag('endpoint.ssl-termination.update')
    clear_flag('endpoint.ssl-termination.update')
    cert_requests = endpoint.get_cert_requests()
    if data_changed('sslterm.requests', cert_requests) and cert_requests:
        old_requests = unitdata.kv().get('sslterm.cert-requests', [])
        delete_old_certs(old_requests, cert_requests)
        unitdata.kv().set('sslterm.cert-requests', cert_requests)
        lets_encrypt.set_requested_certificates(cert_requests)
        NginxConfig().delete_all_config(NginxModule.HTTP, 'ssl-termination')
        NginxConfig().delete_all_config(NginxModule.STREAM)
        set_flag('ssl-termination.waiting')
    elif not cert_requests:  # If no more cert_requests remove all configs
        unitdata.kv().set('sslterm.cert-requests', [])
        NginxConfig().delete_all_config(NginxModule.HTTP, 'ssl-termination')
        NginxConfig().delete_all_config(NginxModule.STREAM)
        set_flag('ssl-termination.report')


@when('ssl-termination.waiting',
      'lets-encrypt.registered',
      'endpoint.ssl-termination.available')
def configure_nginx():
    clear_flag('ssl-termination.waiting')
    endpoint = endpoint_from_flag('endpoint.ssl-termination.available')
    certs = lets_encrypt.live_all()
    cert_requests = endpoint.get_cert_requests()
    # Find the correct fqdn / certificate info
    for request in cert_requests:
        for fqdn in request['fqdn']:
            if fqdn in certs:
                correct_fqdn = fqdn
        juju_unit_name = request['juju_unit'].split('/')[0]
        if 'upstreams' in request and request['upstreams']:
            create_nginx_config(juju_unit_name,
                                request['fqdn'],
                                request['upstreams'],
                                certs[correct_fqdn],
                                request['credentials'],
                                'htaccess_' + juju_unit_name,
                                'ssl-termination')
        if 'tcp' in request and request['tcp']:
            if not create_tcp_nginx_config(request['tcp'],
                                           certs[correct_fqdn],
                                           juju_unit_name):
                return
    endpoint.send_status(list(certs.keys()))
    set_flag('ssl-termination.report')



########################################################################
# HTTP interface
########################################################################

@when(
    'ssl-termination.installed',
    'lets-encrypt.registered',
    'reverseproxy.available')
@when_not('ssl-termination.http-setup')
def http_set_up():
    if not config.get('fqdn'):
        status.blocked("Found http relation, waiting for fqdn config.")
        return
    reverseproxy = endpoint_from_flag('reverseproxy.available')
    services = reverseproxy.services()
    if not data_changed('sslterm.http', services) and \
       not config.changed('credentials'):
        return
    print('New http relation found, configuring proxy.')
    NginxConfig().delete_all_config(NginxModule.HTTP, 'http')
    cert = lets_encrypt.live()

    # There is only support for 1 http service, block if there are more
    if len(services) > 1:
        status.blocked('More than 1 http relation found,' +
        ' please remove one or use ssl-termination-fqdn subordinates.')

    create_nginx_config(services[0]['service_name'],
                        [config.get("fqdn")],
                        services[0]['hosts'],
                        cert,
                        config.get("credentials", ""),
                        'htaccess_http',
                        'http')
    set_flag('ssl-termination.http-setup')
    set_flag('ssl-termination.report')


@when(
    'ssl-termination.installed',
    'ssl-termination.http-setup'
)
@when_not(
    'reverseproxy.available'
)
def remove_http_setup():
    data_changed('sslterm.http', [])
    NginxConfig().delete_all_config(NginxModule.HTTP, 'http') \
                 .validate_nginx() \
                 .reload_nginx()
    clear_flag('ssl-termination.http-setup')
    set_flag('ssl-termination.report')


########################################################################
# JuJu status handlers
########################################################################

@when('ssl-termination.report')
def report_ssl_status():
    registered_fqdns = []  
    cert_requests = unitdata.kv().get('sslterm.cert-requests', [])
    for cert_request in cert_requests:
        registered_fqdns.extend(cert_request['fqdn'])
    if config.get('fqdn') and is_flag_set('reverseproxy.available'):
        registered_fqdns.append(config.get('fqdn'))
    if registered_fqdns:
        status.active('Ready ({})'.format(",".join(registered_fqdns)))
    else:
        status.active('Ready')
    clear_flag('ssl-termination.report')

########################################################################
# Helper methods
########################################################################

def delete_old_certs(old_requests, new_requests):
    if not old_requests:
        return
    for request in new_requests:
        if request not in old_requests:
            for fqdn in request['fqdn']:
                if os.path.exists('/etc/letsencrypt/live/' + fqdn):
                    rmtree('/etc/letsencrypt/live/' + fqdn)
                    rmtree('/etc/letsencrypt/archive/' + fqdn)
                    os.remove('/etc/letsencrypt/renewal/' + fqdn + '.conf')


def create_nginx_config(filename, fqdn, upstreams, cert, credentials, htaccess_name, subdir):
    # fqdn has to be a list
    credentials = credentials.split()
    # Did we get a valid value? If not, blocked!
    if len(credentials) not in (0, 2):
        status.blocked('authentication config wrong! ' 
                       'I expect 2 space-separated string. I got {}.'.format(len(credentials)))
        return
    # We got a valid value, signal to regenerate config.
    #try:
    #    os.remove('/etc/nginx/.' + htaccess_name)
    #except OSError:
    #    pass
    if os.path.exists('/etc/nginx/.' + htaccess_name):
        os.remove('/etc/nginx/.' + htaccess_name)

    nginx_context = {
        'privkey': cert['privkey'],
        'fullchain': cert['fullchain'],
        'fqdn': " ".join(fqdn),
        'upstreams': upstreams,
        'upstream_name': filename, 
        'dhparam': cert['dhparam'],
        'auth_basic': bool(credentials),
    }

    # Did we get credentials? If so, configure them.
    if len(credentials) == 2:
        check_call([
            'htpasswd', '-c', '-b', '/etc/nginx/.' + htaccess_name,
            credentials[0], credentials[1]])
        nginx_context['htpasswd'] = '/etc/nginx/.' + htaccess_name

    cfg = templating.render(source="encrypt.nginx.jinja2",
                      target=None,
                      context=nginx_context)
    nginxcfg = NginxConfig()
    try:
        nginxcfg.write_config(NginxModule.HTTP, cfg, filename, subdir=subdir)
        nginxcfg.enable_all_config(NginxModule.HTTP, subdir=subdir) \
                .validate_nginx() \
                .reload_nginx()
    except NginxConfigError as e:
        log(e)
        status.blocked('{}'.format(e))

def create_tcp_nginx_config(tcp_request, cert, juju_unit):
    """
    tcp_request: [{
                    'port': xxxx,
                    'hosts': ['x.x.x.x', 'x.x.x.x'],
                  }]
    """
    nginxcfg = NginxConfig()
    count = 0
    try:
        for tcp in tcp_request:
            name = "{}-{}".format(juju_unit, count)
            tcp_context = {
                'port': tcp['port'],
                'fullchain': cert['fullchain'],
                'privkey': cert['privkey'],
                'upstream_name': name,
                'upstreams': tcp['hosts'],
            }
            count += 1
            tcp_config = templating.render(source='streams.nginx.jinja2',
                                        target=None,
                                        context=tcp_context)
            nginxcfg.write_config(NginxModule.STREAM, tcp_config, name)
        nginxcfg.enable_all_config(NginxModule.STREAM) \
                .validate_nginx() \
                .reload_nginx()
    except NginxConfigError as e:
        log(e)
        status.blocked('{}'.format(e))
        return False
    return True
