## manage /etc/resolv.conf from pillars 

example pillar

```
resolver:
  searchpaths:
    - example.com
    - example.org
  nameservers:
    - 8.8.8.8
    - 4.4.4.4
  options:
    - "ndots:5"
```
