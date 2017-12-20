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
from subprocess import check_call

from charmhelpers.core import hookenv
from charmhelpers.core.hookenv import status_set

from charms.reactive import when, when_not, set_state, remove_state

from charms.layer import lets_encrypt  # pylint:disable=E0611,E0401
from charms.layer.nginx import configure_site  # pylint:disable=E0611,E0401


config = hookenv.config()


@when(
    'apt.installed.apache2-utils')
@when_not(
    'ssl-termination-proxy.installed')
def install():
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
        'Please relate an HTTP webservice (registered {})'.format(config['fqdn']))


@when(
    'ssl-termination-proxy.running',
    'config.changed.credentials')
def configure_basic_auth():
    print('Credentials changed, re-triggering setup.')
    remove_state('ssl-termination-proxy.running')
    # To make sure we don't trigger an infinite loop.
    remove_state('config.changed.credentials')


@when(
    'ssl-termination-proxy.installed',
    'lets-encrypt.registered',
    'reverseproxy.available')
@when_not(
    'ssl-termination-proxy.running')
def set_up(reverseproxy):
    print('Http relation found, configuring proxy.')
    credentials = config.get('credentials', '').split()
    # Did we get a valid value? If not, blocked!
    if len(credentials) not in (0, 2):
        status_set(
            'blocked',
            'authentication config wrong! '
            'I expect 2 space-separated strings. I got {}.'.format(len(credentials)))
        return
    # We got a valid value, signal to regenerate config.
    try:
        os.remove('/etc/nginx/.htpasswd')
    except OSError:
        pass
    # Did we get credentials? If so, configure them.
    if len(credentials) == 2:
        check_call([
            'htpasswd', '-c', '-b', '/etc/nginx/.htpasswd',
            credentials[0], credentials[1]])
    services = reverseproxy.services()
    live = lets_encrypt.live()
    template = 'encrypt.nginx.jinja2'
    configure_site(
        'default', template,
        privkey=live['privkey'],
        fullchain=live['fullchain'],
        fqdn=config['fqdn'].rstrip(),
        hostname=services[0]['hosts'][0]['hostname'],
        port=services[0]['hosts'][0]['port'],
        dhparam=live['dhparam'],
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
