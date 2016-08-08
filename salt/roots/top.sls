base:
  '*':
    - manage.resolver

  'roles:dns-server':
    - match: grain
    - deploy.dns

  'roles:kubernetes-master':
    - match: grain
    - k8s.kube-bins
    - k8s.etcd
    - k8s.kube-apiserver
    - k8s.kube-controller-manager
    - k8s.kube-scheduler
    - k8s.kube-client-tools
    - k8s.kube-admission-controls
    - k8s.dns
    # - k8s.master-files
    #    - k8s.manage.goodies

  'roles:kubernetes-pool':
    - match: grain
    - k8s.kube-proxy
    - k8s.flannel
    - deploy.docker
    - k8s.kubelet
    - k8s.haproxy
{% if pillar.get('centralized_logging') %}
    - k8s.fluentd-es
{% endif %}

