{% if salt["pillar.get"]("k8s:flannel") %}
/usr/local/bin/flanneld:
  file.managed:
    - source: salt://kube-bins/flanneld_{{salt["pillar.get"]("k8s:flannel_version", "0.5.5")}}
    - user: root
    - group: root
    - mode: 755


/lib/systemd/system/flanneld.service:
  file.managed:
    - source: salt://k8s/flannel/files/flanneld.service
    - template: jinja
    - user: root
    - group: root
    - mode: 644
    - require:
      - file: /usr/local/bin/flanneld

{% if 'kubernetes-master' in grains.get("roles") %}

{% set provisioning_data = '{"Network": "' ~ salt["pillar.get"]("k8s:cluster_cidr") ~ '", "SubnetLen": ' ~ salt["pillar.get"]("k8s:flannel:subnet_len", 24) ~ ', "Backend": { "Type": "vxlan", "VNI": ' ~ salt["pillar.get"]("k8s:flannel:vni", 1) ~ ' }}' %}

flannel-provisioning-requirement:
  pkg.installed:
    - pkgs:
      - curl

/usr/local/bin/flannel_provisioning:
  file.managed:
    - source: salt://k8s/flannel/files/provisioning.sh
    - mode: 0755
    - makedirs: true
    - user: root
    - group: root

/etc/kubernetes/flannel_etcd:
  file.managed:
    - source: salt://k8s/flannel/files/flannel_etcd
    - template: jinja
    - mode: 0755
    - makedirs: true
    - user: root
    - group: root

/etc/kubernetes/flannel.json:
  file.managed:
    - makedirs: true
    - contents: {{provisioning_data|json}}

{% endif %}

flanneld:
  service.running:
    - enable: True
    - watch:
      - file: /usr/local/bin/flanneld
      - file: /lib/systemd/system/flanneld.service
    - require:
      - file: /usr/local/bin/flanneld
      - file: /lib/systemd/system/flanneld.service
  module.wait:
    - name: service.systemctl_reload
    - watch:
      - file: /lib/systemd/system/flanneld.service
{% endif %}
