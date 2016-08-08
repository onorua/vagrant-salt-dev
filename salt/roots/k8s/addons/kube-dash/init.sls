/srv/kube-data/deployments/kube-system/rcs/kube-dash.yaml:
  file.managed:
    - source: salt://k8s/addons/kube-dash/files/kube-dash-rc.yaml
    - template: jinja
    - makedirs: true

/srv/kube-data/deployments/kube-system/services/kube-dash.yaml:
  file.managed:
    - source: salt://k8s/addons/kube-dash/files/kube-dash-svc.yaml
    - template: jinja
    - makedirs: true
