
# SSL Termination Proxy

This charm installs an [HTTPS reverse proxy](https://en.wikipedia.org/wiki/TLS_termination_proxy). The proxy secures traffic to a webservice in the private network using a Let's Encrypt HTTPS certificate and routes requests to backend services based on hostname. The proxy can also add basic username/password authentication if the `credentials` config option is set.

<img src="https://raw.githubusercontent.com/tengu-team/layer-ssl-termination-proxy/master/docs/ssl-termination-proxy.png">

This proxy receives an A+ rating on the [Qualis SSL Server Test](https://www.ssllabs.com/ssltest/index.html).

## How to use

This example will create a single https reverse proxy that has two
domain names and sends traffic to two backend services.

- Surfing to `https://jenkins.example.com` gives you Jenkins.
- Surfing to `https://blog.example.com` gives you the blog.

The DNS of both domain names points to the same server: the reverse proxy,
which routes requests based on which hostname the requests use.

```bash
# Deploy the two backend http webservices.
juju deploy jenkins
juju deploy ghost

# Deploy the Proxy and the two FQDN subordinates
juju deploy cs:~tengu-team/ssl-termination-proxy
juju deploy cs:~tengu-team/ssl-termination-fqdn jenkins-fqdn
juju deploy cs:~tengu-team/ssl-termination-fqdn blog-fqdn

# Expose the reverseproxy
juju expose ssl-termination-proxy

# Connect each fqdn to the correct http webservice
juju add-relation jenkins jenkins-fqdn
juju add-relation ghost blog-fqdn

# Configure the fqdn of each backend service with the correct DNS name
juju config jenkins-fqdn fqdns=jenkins.example.com
juju config blog-fqdn fqdns=blog.example.com

#########################################################################
#     IMPORTANT!                                                        #
#                                                                       #
# You need to manually update the DNS records of both domain names so   #
# they point to the public address of the `ssl-termination-proxy`       #
# server.                                                               #
#                                                                       #
# You can use https://www.duckdns.org for free DNS names.               #
#########################################################################

# Connect the fqdns to the ssl termination proxy to start the certificate requests
# Note that you need to do this after the DNS records are set correctly.
juju add-relation jenkins-fqdn:ssl-termination ssl-termination-proxy
juju add-relation blog-fqdn:ssl-termination ssl-termination-proxy

# Now wait for the model to settle. You can check its status with
watch -c juju status --color
# When everything is configured correctly, `ssl-termination-proxy` will show the status
#

# you can surf to
# - https://jenkins.example.com to reach the Jenkins instance
# - https://blog.example.com to reach the ghost blog instance
```

### OpenStack environments***

If you're using an OpenStack private cloud which uses floating IP addresses, you'll need to associate a floating IP address with the ssl-termination-proxy unit before setting the FQDN, and ensure that this FQDN is reachable from the public Internet. This is necessary for the Let's Encrypt registration to complete.

### [Optional] Configure basic auth**

```bash
juju config jenkins-fqdn credentials="<username> <password>"
juju config blog-fqdn credentials="<username> <password>"
```

*Multiple accounts aren't supported for the moment.*

*Note: Authentication is turned off for `OPTIONS` requests because this is required for CORS. As part of CORS preflight, `OPTIONS` will get called without authentication headers. If this call fails (with 401 unauthorized), the actual CORS call will not be initiated.*

## Legacy mode: single fqdn

For backwards compatibility, this charm also supports a single fqdn configured directly in the `ssl-termination-proxy` charm itself.

```bash
# Deploy your http webservice.
juju deploy jenkins

# Deploy the Proxy.
juju deploy cs:~tengu-team/ssl-termination-proxy
# Expose the proxy.
juju expose ssl-termination-proxy
# Configure your DNS server to point to the ssl-termination-proxy's public ip.
# Let the proxy know what its DNS name is.
# (See https://www.duckdns.org for free DNS names)
juju config ssl-termination-proxy fqdn=www.example.com
# The proxy will now request a certificate from lets encrypt.

# Connect the webservice with the proxy.
juju add-relation jenkins ssl-termination-proxy

# Now you can surf to https://<proxy-public-ip> and you wil reach the webservice.
```

## Authors

This software was created in the [IDLab research group](https://www.ugent.be/ea/idlab) of [Ghent University](https://www.ugent.be) in Belgium. This software is used in [Tengu](https://tengu.io), a project that aims to make experimenting with data frameworks and tools as easy as possible.

- Sander Borny <sander.borny@ugent.be>
- Merlijn Sebrechts <merlijn.sebrechts@gmail.com>
- Mathijs Moerman
