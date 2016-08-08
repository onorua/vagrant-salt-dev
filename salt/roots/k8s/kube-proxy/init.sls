{% if grains['os_family'] == 'RedHat' %}
{% set environment_file = '/etc/sysconfig/kube-proxy' %}
{% else %}
{% set environment_file = '/etc/default/kube-proxy' %}
{% endif %}

/var/lib/kube-proxy/kubeconfig:
  file.managed:
    - source: salt://k8s/kube-proxy/files/kubeconfig
    - template: jinja
    - user: root
    - group: root
    - mode: 400
    - makedirs: true
    - defaults:
      kube_auth: {{pillar.get("kubelet_auth")}}

{% if salt["pillar.get"]("dockerized_kube_proxy") %}
{# dockerized version #}

/etc/kubernetes/manifests/kube-proxy.manifest:
  file.managed:
    - source: salt://k8s/kube-proxy/files/kube-proxy.manifest
    - template: jinja
    - user: root
    - group: root
    - mode: 644
    - makedirs: true
    - dir_mode: 755
    - context:
        # 20m might cause kube-proxy CPU starvation on full nodes, resulting in
        # delayed service updates. But, giving it more would be a breaking change 
        # to the overhead requirements for existing clusters.
        # Any change here should be accompanied by a proportional change in CPU
        # requests of other per-node add-ons (e.g. fluentd).
        cpurequest: '20m'

#stop legacy kube-proxy service
stop_kube-proxy:
  service.dead:
    - name: kube-proxy
    - enable: false

{% else %}
{# systemd service version #}

/etc/kubernetes/manifests/kube-proxy.manifest:
  file.absent

/usr/local/bin/kube-proxy:
  file.managed:
    - source: salt://kube-bins/kube-proxy_{{salt["pillar.get"]("k8s:cluster_version")}}
    - user: root
    - group: root
    - mode: 755
  k8s.maintenance_mode:
    - name: {{grains.get('fqdn')}}
    - kubeconfig: /var/lib/kube-proxy/kubeconfig
    - onchanges: 
      - file: /usr/local/bin/kube-proxy
    - watch:
      - file: /usr/local/bin/kube-proxy

/lib/systemd/system/kube-proxy.service:
  file.managed:
    - source: salt://k8s/kube-proxy/files/kube-proxy.service
    - template: jinja
    - user: root
    - group: root
    - require:
      - file: /usr/local/bin/kube-proxy
  module.wait:                                                                  
    - name: service.systemctl_reload                                            
    - watch:                                                                    
      - file: /lib/systemd/system/kube-proxy.service

/etc/init.d/kube-proxy:
  file.absent

{{ environment_file }}:
  file.managed:
    - source: salt://k8s/kube-proxy/files/default
    - template: jinja
    - user: root
    - group: root
    - mode: 644
    - require:
      - file: /usr/local/bin/kube-proxy

kube-proxy:
  group.present:
    - system: True
  user.present:
    - system: True
    - gid_from_name: True
    - shell: /sbin/nologin
    - home: /var/kube-proxy
    - require:
      - file: /usr/local/bin/kube-proxy
      - group: kube-proxy
  service.running:
    - enable: True
    - watch:
      - file: {{ environment_file }}
      - file: /var/lib/kube-proxy/kubeconfig
      - file: /usr/local/bin/kube-proxy
      - file: /lib/systemd/system/kube-proxy.service

{% endif %}
{# end of dockerized vs service kube-proxy #}

enable scheduling to the node:
  k8s.uncordon:
    - name: {{grains.get('fqdn')}}
    - kubeconfig: /var/lib/kube-proxy/kubeconfig
    - watch:
      - file: /usr/local/bin/kube-proxy
