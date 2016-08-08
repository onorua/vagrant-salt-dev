# install docker daemon on the machine 

Make sure we have docker daemon installed. There are following configuration parameters available:

In order to install specific docker version, there is pillar configuration:
```
override_docker_ver: 1.8.3
```

In case `docker_http_proxy` is defined in pillars, docker will use this proxy for image downloads. 

`docker_auth` is used to configure registry authentication, example:
```
docker_auth:
  - url: https://dev-registry.otlabs.fr
    auth: b3Q6S1dQU=
    email: dev-registry@otlabs.fr   
  - url: https://registry.otlabs.fr
    auth: b3RsYWJzOnBlOG==
    email: registry@otlabs.fr
```
