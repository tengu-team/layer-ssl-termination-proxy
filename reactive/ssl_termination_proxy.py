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
import shutil
from subprocess import call

from charmhelpers.core import hookenv
from charmhelpers.core.hookenv import status_set, charm_dir

from charms.reactive import when, when_not, set_state, remove_state

from charms.layer import lets_encrypt  # pylint:disable=E0611,E0401
from charms.layer.nginx import configure_site  # pylint:disable=E0611,E0401


config = hookenv.config()
dhparam_dir = os.path.join(os.sep, 'etc', 'nginx', 'dhparam')
dhparam = 'dhparam.pem'


@when(
    'apt.installed.apache2-utils')
@when_not(
    'ssl-termination-proxy.installed')
def install():
    if not os.path.isdir(dhparam_dir):
        os.mkdir(dhparam_dir)
    shutil.copyfile(os.path.join(charm_dir(), 'files', dhparam),
                    os.path.join(dhparam_dir, dhparam))
    set_state('ssl-termination-proxy.installed')


@when(
    'ssl-termination-proxy.installed')
@when_not(
    'lets-encrypt.registered')
def signal_need_fqdn():
    # This check is here to make sure we don't overwrite the "register cert failed" message
    if not config['fqdn']:
        status_set('blocked', 'Please fill in fqdn for ssl certificate.')


@when(
    'ssl-termination-proxy.installed',
    'lets-encrypt.registered')
@when_not(
    'reverseproxy.available')
def signal_need_webservice():
    status_set(
        'blocked',
        'Please relate an HTTP webservice (registered https://{})'.format(config['fqdn']))


@when(
    'ssl-termination-proxy.installed'
    'config.changed.credentials')
def configure_basic_auth():
    print('Config changed credentials')
    if config['credentials']:
        credentials = config['credentials'].split(' ')
        if not os.path.exists('/etc/nginx/.htpasswd'):
            call(['htpasswd', '-c', '-b', '/etc/nginx/.htpasswd', credentials[0], credentials[1]])
        else:
            call(['htpasswd', '-b', '/etc/nginx/.htpasswd', credentials[0], credentials[1]])
    else:
        if os.path.exists('/etc/nginx/.htpasswd'):
            os.remove('/etc/nginx/.htpasswd')
    remove_state('ssl-termination-proxy.running')


@when(
    'ssl-termination-proxy.installed',
    'lets-encrypt.registered',
    'reverseproxy.available')
@when_not(
    'ssl-termination-proxy.running')
def set_up(reverseproxy):
    print('Http relation found')
    services = reverseproxy.services()
    print(services)
    live = lets_encrypt.live()
    template = 'encrypt.nginx.jinja2'
    configure_site(
        'default', template,
        privkey=live['privkey'],
        fullchain=live['fullchain'],
        fqdn=config['fqdn'].rstrip(),
        hostname=services[0]['hosts'][0]['hostname'],
        dhparam=os.path.join(dhparam_dir, dhparam),
        auth_basic=bool(config['credentials']))
    set_state('ssl-termination-proxy.running')
    status_set('active', 'Ready (https://{})'.format(config['fqdn'].rstrip()))


@when(
    'ssl-termination-proxy.running')
@when_not(
    'reverseproxy.available')
def stop_nginx():
    print('Reverseproxy relation broken')
    remove_state('ssl-termination-proxy.running')
