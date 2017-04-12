# SSL Termination Proxy

This charm provides a reverse proxy with installed certificates via the http interface. This proxy is using NGINX and a let's encrypt certificate.

# How to use

**Basic HTTPS proxy**

```bash
# Deploy your http webservice.
juju deploy cs:~tengu-team/flask-helloworld

# Deploy the Proxy.
juju deploy cs:~tengu-team/ssl-termination-proxy
# Expose the proxy.
juju expose ssl-termination-proxyssl-termination-proxy
# Configure your DNS server to point to the ssl-termination-proxy's public ip.
# Let the proxy know what its DNS name is.
# (See https://www.duckdns.org for free DNS names)
juju config ssl-termination-proxy fqdn=www.example.com
# The proxy will now request a certificate from lets encrypt.

# Connect the webservice with the proxy.
juju add-relation flask-helloworld ssl-termination-proxy

# Now you can surf to https://<proxy-public-ip> and you wil reach the webservice.
```

**[Optional] Configure basic auth**

juju config credentials="<username> <password>"

*Multiple accounts aren't supported for the moment.*

# DHParameters

This charm installs its own pregenerated dhparam.pem file. It was generated using openssl using the following command:
```
sudo openssl dhparam -out dhparam.pem 4096
```
Currently a 4096 bit prime is used (recommended at time of writing), but as time goes by, this should be increased.

## Authors

This software was created in the [IBCN research group](https://www.ibcn.intec.ugent.be/) of [Ghent University](https://www.ugent.be/en) in Belgium. This software is used in [Tengu](https://tengu.intec.ugent.be), a project that aims to make experimenting with data frameworks and tools as easy as possible.

 - Sander Borny <sander.borny@ugent.be>
