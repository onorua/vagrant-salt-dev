/usr/local/bin/kubectl:
  file.managed:
    - source: salt://kube-bins/kubectl_{{salt["pillar.get"]("k8s:cluster_version")}}
    - user: root
    - group: root
    - mode: 755
