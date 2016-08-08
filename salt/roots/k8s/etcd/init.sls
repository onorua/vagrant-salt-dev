{% for etcd in salt["pillar.get"]('k8s:etcd:nodes', []) %}
{% if etcd.address in grains.ipv4 or etcd.address in grains.ipv6 %}

/usr/local/bin/etcd:
  file.managed:
    - source: salt://kube-bins/etcd_{{salt["pillar.get"]("k8s:etcd_version", "v2.3.0")}}
    - user: root
    - group: root
    - mode: 755

etcd-user:
  user.present:
    - name: etcd
    - system: true
    - shell: /bin/false

{{salt["pillar.get"]("k8s:etcd:data_dir", "/srv/data/etcd")}}/{{etcd.name}}:
  file.directory:
    - makedirs: true
    - user: etcd
    - group: etcd
    - mode: 700
    - require:
      - user: etcd-user

/lib/systemd/system/etcd.service:
  file.managed:
    - source: salt://k8s/etcd/files/etcd.service
    - template: jinja
    - user: root
    - group: root
    - mode: 644
    - makedirs: true
    - defaults:
        etcd: {{ etcd }}

etcd:
  service.running:
    - enable: True
    - watch:
      - file: /usr/local/bin/etcd
      - file: /lib/systemd/system/etcd.service
    - require:
      - file: /usr/local/bin/etcd
      - file: /lib/systemd/system/etcd.service
  module.wait:
    - name: service.systemctl_reload
    - watch:
      - file: /lib/systemd/system/etcd.service

{% endif %} {# end of IP match if #}
{% endfor %}
