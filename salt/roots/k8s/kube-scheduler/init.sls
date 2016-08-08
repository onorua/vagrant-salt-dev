{% if grains.roles is defined and 'kubernetes-master' in grains.roles %}
# Copy kube-scheduler manifest to manifests folder for kubelet.

/etc/kubernetes/manifests/kube-scheduler.manifest:
  file.managed:
    - source: salt://k8s/kube-scheduler/kube-scheduler.manifest
    - template: jinja
    - makedirs: true
    - dir_mode: 755

#stop legacy kube-scheduler service 
stop_kube-scheduler:
  service.dead:
    - name: kube-scheduler
    - enable: None

{%endif%}
