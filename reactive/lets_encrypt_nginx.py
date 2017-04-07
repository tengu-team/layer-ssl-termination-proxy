# !/usr/bin/env python3
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
import charms.apt
from charms.reactive import when, when_not, set_state, remove_state
from charmhelpers.core import hookenv, host
from charms.layer.nginx import configure_site
from charmhelpers.core.hookenv import status_set, charm_dir
from charmhelpers.contrib.python.packages import pip_install
from charms.layer import lets_encrypt
from subprocess import call


config = hookenv.config()


@when_not('apt.installed.apache2-utils')
def install_utils():
    charms.apt.queue_install(['apache2-utils'])
    charms.apt.install_queued()


@when('apt.installed.apache2-utils')
@when_not('lets-encrypt-nginx.installed')
def install():
    if not os.path.isdir(config['dhparam'].rsplit('/',1)[0]):
        os.mkdir(config['dhparam'].rsplit('/',1)[0])
    shutil.copyfile(hookenv.resource_get('dhparam') ,config['dhparam'])
    set_state('lets-encrypt-nginx.installed')


@when('reverseproxy.available', 'nginx.available', 'lets-encrypt.registered', 'lets-encrypt-nginx.installed')
@when_not('lets-encrypt-nginx.running')
def set_up(reverseproxy):
    hookenv.log('Http relation found')
    services = reverseproxy.services()
    hookenv.log(services)
    live = lets_encrypt.live()
    template = 'encrypt.nginx.tmpl'
    if config['credentials']:
        template = 'encrypt.nginx.auth.tmpl'
    configure_site('default', template, privkey=live['privkey']
                                                  , fullchain=live['fullchain']
                                                  , fqdn=config['fqdn']
                                                  , hostname=services[0]['hosts'][0]['hostname']
                                                  , dhparam=config['dhparam'])
    status_set('active', 'Ready')
    set_state('lets-encrypt-nginx.running')


@when('lets-encrypt-nginx.running')
@when_not('reverseproxy.available')
def stop_nginx():
    hookenv.log('Reverseproxy relation broken')
    if host.service_running('nginx'):
        host.service_stop('nginx')
    remove_state('lets-encrypt-nginx.running')


@when('config.changed.credentials', 'lets-encrypt-nginx.installed')
def config_changed_credentials():
    hookenv.log('Config changed credentials')
    if config['credentials']:
        credentials = config['credentials'].split(' ')
        if not os.path.exists('/etc/nginx/.htpasswd'):
            call(['htpasswd', '-c', '-b', '/etc/nginx/.htpasswd', credentials[0], credentials[1]])
        else:
            call(['htpasswd', '-b', '/etc/nginx/.htpasswd', credentials[0], credentials[1]])
    else:
        if os.path.exists('/etc/nginx/.htpasswd'):
            os.remove('/etc/nginx/.htpasswd')
    remove_state('lets-encrypt-nginx.running')
