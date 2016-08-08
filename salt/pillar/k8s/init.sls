include:
  - k8s.kubeclients
  - k8s.certs

dns_domain: "test.com"

k8s:
  api_servers:
    - 192.168.33.10:6443
  cluster_cidr: "10.74.0.0/16"
  service_cluster_ip_range: "10.116.0.0/23"
  log_level: "--v=2"
  network_provider: flannel

  etcd_version: v3.0.3
  flannel_version: v0.5.5
  cluster_version: v1.3.4

  flannel:
    iface: eth1

  etcd:
    data_dir: /srv/data/etcd
    nodes:
    - name: etcd11
      address: 192.168.33.10
      client_port: 4001
      server_port: 7001
