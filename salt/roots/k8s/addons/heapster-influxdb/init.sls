{% set heapster_rcs =  ["heapster-controller.yaml", "influxdb-grafana-controller.yaml"] %}
{% set heapster_services =  ["grafana-service.yaml", "heapster-service.yaml", "influxdb-service.yaml"] %}

{% if salt["pillar.get"]("k8s:cluster-monitoring") == "heapster-influxdb" %}
{% for file in heapster_rcs %}
/srv/kube-data/deployments/kube-system/rcs/{{file}}:
  file.managed:
    - source: salt://k8s/addons/heapster-influxdb/files/{{file}}
    - template: jinja
    - makedirs: true
{% endfor %}

{% for file in heapster_services %}
/srv/kube-data/deployments/kube-system/services/{{file}}:
  file.managed:
    - source: salt://k8s/addons/heapster-influxdb/files/{{file}}
    - template: jinja
    - makedirs: true
{% endfor %}

{% else %}
{% for file in heapster_rcs %}
/srv/kube-data/deployments/kube-system/rcs/{{file}}:
  file.absent
{% endfor %}

{% for file in heapster_services %}
/srv/kube-data/deployments/kube-system/services/{{file}}:
  file.absent
{% endfor %}
{% endif %}
