{# this is a bit hacky and may be not optimized #}

deliver kubelet binary:
  file.managed:
    - name: /srv/salt/kube-bins/kubelet_{{salt["pillar.get"]("k8s:cluster_version")}}
    - source: https://github.com/onorua/vagrant-salt-dev/releases/download/{{salt["pillar.get"]("k8s:cluster_version")}}/kubelet_{{salt["pillar.get"]("k8s:cluster_version")}}
    - makedirs: true
    - skip_verify: true
    - replace: False

deliver kube-proxy binary:
  file.managed:
    - name: /srv/salt/kube-bins/kube-proxy_{{salt["pillar.get"]("k8s:cluster_version")}}
    - source: https://github.com/onorua/vagrant-salt-dev/releases/download/{{salt["pillar.get"]("k8s:cluster_version")}}/kube-proxy_{{salt["pillar.get"]("k8s:cluster_version")}}
    - makedirs: true
    - skip_verify: true
    - replace: False

deliver kubectl binary:
  file.managed:
    - name: /srv/salt/kube-bins/kubectl_{{salt["pillar.get"]("k8s:cluster_version")}}
    - source: https://github.com/onorua/vagrant-salt-dev/releases/download/{{salt["pillar.get"]("k8s:cluster_version")}}/kubectl_{{salt["pillar.get"]("k8s:cluster_version")}}
    - makedirs: true
    - skip_verify: true
    - replace: False

{% set etcd_version = salt["pillar.get"]("k8s:etcd_version") %}
deliver etcd binary:
  cmd.run:
    - name: curl -s -L https://github.com/coreos/etcd/releases/download/{{etcd_version}}/etcd-{{etcd_version}}-linux-amd64.tar.gz |  tar xzvf - etcd-{{etcd_version}}-linux-amd64/etcd --strip-components 1 && mv etcd /srv/salt/kube-bins/etcd_{{etcd_version}}
    - creates: /srv/salt/kube-bins/etcd_{{etcd_version}}


{% set flannel_version = salt["pillar.get"]("k8s:flannel_version", "")[1:] %}
deliver flannel binary:
  cmd.run:
    - name: curl -s -L https://github.com/coreos/flannel/releases/download/v{{flannel_version}}/flannel-{{flannel_version}}-linux-amd64.tar.gz | tar xzvf - flannel-{{flannel_version}}/flanneld --strip-components 1 && mv flanneld /srv/salt/kube-bins/flanneld_v{{flannel_version}}
    - creates: /srv/salt/kube-bins/flanneld_v{{flannel_version}}
