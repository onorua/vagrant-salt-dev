# dashboard deployment

This state is not official kubernetes state, but rather our own creation, to deploy cluster dashboard in a way we expect. It has integration with salt otk8s module, and put templates into the proper placed so they could be deployed by salt.

it expects following pillar configuration:
```
k8s:
  dashboard:
    port: 80
    external_ips:
      - 172.16.252.10
      - 172.16.252.11
```

Example above will configure dashboard to listen to external_ips and on port defined as `port`. 
