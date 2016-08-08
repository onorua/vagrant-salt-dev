{% if pillar.get("kube-controller-manager_docker_tag", "").startswith("v1.1") or pillar.get("kube-scheduler_docker_tag", "").startswith("v1.1") %}
{% if grains.roles is defined and 'kubernetes-master' in grains.roles %}
/etc/kubernetes/manifests/podmaster.manifest:
  file.managed:
    - source: salt://k8s/kube-podmaster/podmaster.yaml
    - template: jinja
    - user: root
    - group: root
    - mode: 644
    - makedirs: true
    - dir_mode: 755

#stop legacy kube-apiserver service
stop_legcy-kube-apiserver:
  service.dead:
    - name: kube-apiserver
    - enable: None
{% endif %}
{% else %}

/etc/kubernetes/manifests/podmaster.manifest:
  file.absent

{% endif %}
