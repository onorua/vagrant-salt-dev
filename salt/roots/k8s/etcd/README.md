## manage etcd cluster from pillars

expects following pillar entries:
```
k8s:
  etcd_version: "v2.2.5"
  etcd_nodes:
    - name: etcd11
      address: 172.16.252.10
      client_port: 4001
      server_port: 7001
    - name: etcd21
      address: 172.16.252.11
      client_port: 4001
      server_port: 7001
    - name: etcd32
      address: 172.16.252.12
      client_port: 4001
      server_port: 7001
```

with a flannel network, we come to the conclusion that etcd must be started outside the docker container. 
