## Kubernetes api-server load balancer

We do not have proper way to balance kube-api server load between nodes because we need some sort of VRRP, which is expensive for time (10-15 seconds between switchover) and the problem in case API server process is dead or load balancer process is dead but IP is still there - we might have problem any way. 

Preventing single point of failure, we decided to have "client" side load balacing. 

kubelet and kube-proxy don't have possibility to do client side load balancing even though kubelet has --api-masters=[ip:port] notation it always choose the first one. 

So in order to fix this, I've built this haproxy module which is run under kubelet, as a normal pod, it is listening to 127.0.0.1:2443 port, and redirect requests to all kube-api servers managed by salt-stack. 

it expects following pillar configuration:
```
k8s:
  api_servers:
    - 172.16.252.10:6443
    - 172.16.252.11:6443
    - 172.16.252.12:6443
```

*Important note!*

it uses tcp load balancing behind scenes, so don't add any http/https etc in there.
