## heapster standalone

This state is not official kubernetes state, but rather our own creation, to deploy cluster heapster monitoring in a way we expect. It has integration with salt otk8s module, and put templates into the proper placed so they could be deployed by salt.

it will automatically change the RAM usage according to `node_labels` records in case `num_nodes` is undefined. In case `node_labels` is not defined also, it will set RAM to 200MB. 

it expect following pillar configuration:
```
k8s:
  num_nodes: 10
```

or 

```
node_labels:
  ip-172-16-252-10.k8s.otlabs.fr:
    zone: common
    role: admin
  ip-172-16-252-11.k8s.otlabs.fr:
    zone: common
    role: admin
  ip-172-16-252-12.k8s.otlabs.fr:
    zone: common
    role: admin
```

