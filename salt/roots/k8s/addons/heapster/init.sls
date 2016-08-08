{% if salt["pillar.get"]("k8s:cluster-monitoring:heapster") %}
/srv/kube-data/deployments/kube-system/rcs/heapster.yaml:
  file.managed:
    - source: salt://k8s/addons/heapster/files/heapster-rc.yaml
    - template: jinja
    - makedirs: true

/srv/kube-data/deployments/kube-system/services/heapster.yaml:
  file.managed:
    - source: salt://k8s/addons/heapster/files/heapster-svc.yaml
    - template: jinja
    - makedirs: true
{% else %}
/srv/kube-data/deployments/kube-system/rcs/heapster.yaml:
  file.absent

/srv/kube-data/deployments/kube-system/services/heapster.yaml:
  file.absent
{% endif %}
