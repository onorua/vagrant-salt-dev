{% if  'kubernetes-master' in grains.get("roles", {}) %}

/etc/kubernetes/manifests/kube-controller-manager.manifest:
  file.managed:
    - source: salt://k8s/kube-controller-manager/kube-controller-manager.manifest
    - template: jinja
    - makedirs: true
    - dir_mode: 755

stop-legacy-kube_controller_manager:
  service.dead:
    - name: kube-controller-manager
    - enable: None

{%endif%}
