# SSL Termination Proxy

This charm provides a reverse proxy with installed certificates via the http interface. This charm uses the [lets-encrypt](https://github.com/cmars/layer-lets-encrypt) and [nginx](https://github.com/battlemidget/juju-layer-nginx) layers.

# DHParameters

This charm installs its own pregenerated dhparam.pem file. It was generated using openssl using the following command:
```
sudo openssl dhparam -out dhparam.pem 4096
```
Currently a 4096 bit prime is used (recommended at time of writing), but as time goes by, this should be increased.

## Authors

This software was created in the [IBCN research group](https://www.ibcn.intec.ugent.be/) of [Ghent University](https://www.ugent.be/en) in Belgium. This software is used in [Tengu](https://tengu.intec.ugent.be), a project that aims to make experimenting with data frameworks and tools as easy as possible.

 - Sander Borny <sander.borny@ugent.be>
