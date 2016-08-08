dns-server:
    listen: 192.168.33.10

include:
    - dns.zones.test-com
    - dns.zones.kubernetes-default-names
