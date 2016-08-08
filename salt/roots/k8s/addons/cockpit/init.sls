/srv/kube-data/deployments/kube-system/rcs/cockpit.yaml:
  file.managed:
    - source: salt://k8s/addons/cockpit/files/cockpit-rc.yaml
    - template: jinja
    - makedirs: true

/srv/kube-data/deployments/kube-system/services/cockpit.yaml:
  file.managed:
    - source: salt://k8s/addons/cockpit/files/cockpit-svc.yaml
    - template: jinja
    - makedirs: true
