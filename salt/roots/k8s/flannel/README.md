## manage flannel from salt

```
k8s:
  etcd_nodes:
    - name: etcd11
      address: 172.16.252.10
      client_port: 4001
      server_port: 7001
    - name: etcd21
      address: 172.16.252.11
      client_port: 4001
      server_port: 7001
  flannel:
    iface: eth1
    ip-masq: false
    etcd-prefix: mega.prefix
```

From this config, you tell salt to:

 - install flannel
 - configure it to use etcd from the etcd_nodes list (most probably this parameters is already defined for etcd cluster for k8s)
 - use interface name: eth1 for inter host comunication
 - do not use masquerading of incomming requests
 - use etcd-prefix 'mega.prefix' which will be defaulted to cluster_domain pillar value, or if it is not stated - to 'ot' value. 

you will need to add following data to etcd:

```
curl -L http://localhost:2379/v2/keys/mega.prefix/network/config -XPUT --data-urlencode value@flannel.json
```

where flannel.json is:
```
{
  "Network": "10.116.128.0/18",
  "SubnetLen": 24,
  "Backend": {
    "Type": "vxlan",
    "VNI": 5
  }
}
```
