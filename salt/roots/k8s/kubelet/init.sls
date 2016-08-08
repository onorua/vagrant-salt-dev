{% if grains['os_family'] == 'RedHat' %}
{% set environment_file = '/etc/sysconfig/kubelet' %}
{% else %}
{% set environment_file = '/etc/default/kubelet' %}
{% endif %}

/usr/local/bin/kubelet:
  file.managed:
    - source: salt://kube-bins/kubelet_{{salt["pillar.get"]("k8s:cluster_version")}}
    - user: root
    - group: root
    - mode: 755

{{ environment_file}}:
  file.managed:
    - source: salt://k8s/kubelet/default
    - template: jinja
    - user: root
    - group: root
    - mode: 644
    - require:
      - file: /usr/local/bin/kubelet

/lib/systemd/system/kubelet.service:
  file.managed:
    - source: salt://k8s/kubelet/kubelet.service
    - template: jinja
    - user: root
    - group: root
    - require:
      - file: /usr/local/bin/kubelet
  module.wait:                                                                  
    - name: service.systemctl_reload                                            
    - watch:                                                                    
      - file: /lib/systemd/system/kubelet.service

/etc/init.d/kubelet:
  file.absent

# The default here is that this file is blank.  If this is the case, the kubelet
# won't be able to parse it as JSON and will try to use the kubernetes_auth file
# instead.  You'll see a single error line in the kubelet start up file
# about this.
/var/lib/kubelet/kubeconfig:
  file.managed:
    - source: salt://k8s/kubelet/kubeconfig
    - template: jinja
    - user: root
    - group: root
    - mode: 400
    - makedirs: true
    - require:
      - file: /usr/local/bin/kubelet
    - defaults:
      kube_auth: {{pillar.get("kubelet_auth")}}

kubelet:
  service.running:
    - enable: True
    - watch:
      - file: {{ environment_file}}
      - file: /usr/local/bin/kubelet
      - file: /var/lib/kubelet/kubeconfig
    - require:
      - file: /usr/local/bin/kubelet
