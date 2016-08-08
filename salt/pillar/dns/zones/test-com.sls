dns-server:
  trusted-nets:
    - 172.16.0.1/24
  forwarders:
    - 8.8.8.8
  zones:
    test.com:
        self_address: 192.168.33.11
        name_servers:
            ns01: 192.168.33.10
        a_records:
            master: 192.168.33.10
            node01: 192.168.33.101
            node02: 192.168.33.102
        cnames:
          test: node01

