{% if 'kubernetes-master' in grains.get('roles', {}) %}
/srv/kubernetes/known_tokens.csv:
  file.managed:
    - source: salt://k8s/kube-apiserver/known_tokens.csv
    - makedirs: true
    - dir_mode: 755

/srv/kubernetes/basic_auth.csv:
  file.managed:
    - source: salt://k8s/kube-apiserver/basic_auth.csv
    - makedirs: true
    - dir_mode: 755

/srv/kubernetes/auth_policy.json:
  file.managed:
    - source: salt://k8s/kube-apiserver/auth_policy.json
    - makedirs: true
    - dir_mode: 755

# Copy kube-apiserver manifest to manifests folder for kubelet.
/etc/kubernetes/manifests/kube-apiserver.manifest:
  file.managed:
    - source: salt://k8s/kube-apiserver/kube-apiserver.manifest
    - template: jinja
    - user: root
    - group: root
    - mode: 644
    - makedirs: true
    - dir_mode: 755

#stop legacy kube-apiserver service
stop_kube-apiserver:
  service.dead:
    - name: kube-apiserver
    - enable: None

{% if salt['pillar.get']('k8s:ca.key') and salt['pillar.get']('k8s:ca.crt') %}
/srv/kubernetes/ca.key:
  file.managed:
    - user: root
    - group: root
    - mode: 0644
    - makedirs: true
    - contents_pillar: k8s:ca.key

/srv/kubernetes/ca.crt:
  file.managed:
    - user: root
    - group: root
    - mode: 0644
    - makedirs: true
    - contents_pillar: k8s:ca.crt
{% endif %}

{% if salt['pillar.get']('k8s:server.key') and salt['pillar.get']('k8s:server.cert') %}
/srv/kubernetes/server.key:
  file.managed:
    - user: root
    - group: root
    - mode: 0644
    - makedirs: true
    - contents_pillar: k8s:server.key

/srv/kubernetes/server.cert:
  file.managed:
    - user: root
    - group: root
    - mode: 0644
    - makedirs: true
    - contents_pillar: k8s:server.cert
{% endif %}

{% endif %}
