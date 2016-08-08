# DNS server configuration state

it installs bind9 and configure it in accordance to pillar config. Full pillar configuration may look like:

NOTE: disregard that SRV records are stated here as example for etcd, etcd server configuration is done automatically based on k8s:etcd_nodes value, please refet to k8s.etcd documentaion. 

```
dns-server:
    ----------
    forwarders:
        - 8.8.8.8
    trusted-nets:
        - 172.16.0.1/24
    zones:
        ----------
        k8s.otlabs.fr:
            ----------
            srv_records:
              "_etcd-server._tcp": 
                - "0 0 7001 ip-172-16-252-10"
                - "0 0 7001 ip-172-16-252-11"
                - "0 0 7001 ip-172-16-252-12"
            a_records:
                ----------
                master:
                    192.168.33.10
                node01:
                    - 192.168.33.101
                    - 192.168.33.103
                node02:
                    192.168.33.102
            cnames:
                ----------
                test:
                    node01
            name_servers:
                ----------
                ns01:
                    192.168.33.10
            self_address:
                192.168.33.10
        kubernetes.default.cluster.local:
            ----------
            name_servers:
                ----------
                ns01:
                    192.168.33.10
            self_address:
                10.116.0.1
        kubernetes.default.svc.cluster.local:
            ----------
            name_servers:
                ----------
                ns01:
                    192.168.33.10
            self_address:
                10.116.0.1
```
