## Manage addons from pillars

it allows to manage addons (switch on/off) from pillars. What is considered to be an addon:
  
  - application which should be running within cluster, but is not a daemonset or static pod
  - cluster can work without it, generally, but it useful to have

```
k8s:
  addons:
    - heapster-influxdb
    - grafana
```

this pillar configuration will end up with following workflow:

1. Check for file in `k8s/addons/{addon folder}`
2. If the folder exists, it will copy all files with yaml, yml, json extentions from salt-master to `/etc/kubernetes/addons/{addon folder}`
3. It will run k8s.create to deploy it on k8s. 

Addons does support multiple instances in one application, such as Services and Endpoints in the same file. 

If addon is not enabled from pillars, it will be removed from `/etc/kubernetes/addons` folder, but it will not be removed from k8s yet. 

TODO: Make it remove from k8s as well
