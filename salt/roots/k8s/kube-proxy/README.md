## kube-proxy management

if there is pillar value: `kube-proxy_docker_tag` we will switch to dockerized version of kube-proxy. Otherwise we use kube-proxy as a systemd service. 

### Important!!
In case you enable dockerized kube-proxy, make sure `allow_privileged` pillar is set to true

So the dockerized pillars for v1.2.1 release, must look like:

```
allow_privileged: true
kube-proxy_docker_tag: v1.2.1
```

