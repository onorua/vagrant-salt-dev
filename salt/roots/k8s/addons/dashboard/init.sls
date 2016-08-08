/srv/kube-data/deployments/kube-system/rcs/dashboard.yaml:
  file.managed:
    - source: salt://k8s/addons/dashboard/files/dashboard-rc.yaml
    - template: jinja
    - makedirs: true

/srv/kube-data/deployments/kube-system/services/dashboard.yaml:
  file.managed:
    - source: salt://k8s/addons/dashboard/files/dashboard-svc.yaml
    - template: jinja
    - makedirs: true
