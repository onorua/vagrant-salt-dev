{% if pillar.get('dns-server', {}) %}
bind9:
  pkg.installed


{% set myipv4 = "127.0.0.1" %}
{% if grains.get('fqdn_ip4') is sequence and grains.get('fqdn_ip4')|length > 0 %}
{% set myipv4 =  salt["pillar.get"]("dns-server:listen", grains.get('fqdn_ip4')|first) %}
{% else %}
{% set myipv4 = salt["pillar.get"]("dns-server:listen", grains.get('ipv4')|first) %}
{% endif %}

{% if grains.init == 'systemd' %}

/etc/systemd/system/bind9.service.d/local.conf:
  file.managed:
    - source: salt://deploy/dns/files/bind9.dropin
    - makedirs: true
    - require:
      - pkg: bind9
{% endif %}

{% set dns = pillar.get("dns-server", {}) %}

/etc/bind/named.conf.options:
  file.managed:
    - source: salt://deploy/dns/files/named.conf.options
    - template: jinja
    - user: root
    - group: bind
    - mode: 644
    - makedirs: true
    - dir_mode: 755
    - require:
      - pkg: bind9
    - defaults:
      myipv4: {{ myipv4 }}
      allowed_networks: {{ dns.get("trusted-nets", []) }}
      forwarders: {{ dns.get("forwarders", []) }}

{% set domains = dns.get("zones", {}) %}

/etc/bind/named.conf.local:
  file.managed:
    - source: salt://deploy/dns/files/local.template
    - template: jinja
    - user: root
    - group: bind
    - mode: 644
    - makedirs: true
    - dir_mode: 755
    - require:
      - pkg: bind9
    - defaults:
      domains: {{ domains.keys() }}


{% for domain, values in domains.iteritems() %}
/etc/bind/db.{{domain}}:
  file.managed:
    - source: salt://deploy/dns/files/db.template
    - template: jinja
    - user: root
    - group: bind
    - mode: 644
    - makedirs: true
    - dir_mode: 755
    - require:
      - pkg: bind9
    - defaults:
      myipv4: {{ values.get("self_address", myipv4) }}
      domain: {{ domain }}
      nsservers: {{ values.get("name_servers", {}) }}
      arecords: {{ values.get("a_records", {}) }}
      cnames: {{ values.get("cnames", {}) }}
      ttl: {{ values.get("ttl", "1800") }}
      srv_records: {{ values.get("srv_records", {}) }}
{% endfor %}

bind9_running:
  service.running:
    - name: bind9
    - enable: True
    - require:
      - pkg: bind9
    - watch:
      - file: /etc/bind/named.conf.local
      - file: /etc/bind/named.conf.options
{% for i in domains.keys() %}
      - file: /etc/bind/db.{{i}}
{% endfor %}

{% endif %}
