/etc/kubernetes/addons/skydns.yaml:
  file.managed:
    - source: salt://k8s/dns/files/kube-dns-rc.yaml
    - template: jinja
    - makedirs: true

/etc/kubernetes/addons/skydns-svc.yaml:
  file.managed:
    - source: salt://k8s/dns/files/kube-dns-svc.yaml
    - template: jinja
    - makedirs: true

#deploy skydns rc:
#  k8s.manage_manifest:
#    - name: /etc/kubernetes/addons/skydns.yaml
#    - namespace: kube-system
#    - kubeconfig: /var/lib/kubelet/kubeconfig
#
#deploy skydns svc:
#  k8s.manage_manifest:
#    - name: /etc/kubernetes/addons/skydns-svc.yaml
#    - namespace: kube-system
#    - kubeconfig: /var/lib/kubelet/kubeconfig
