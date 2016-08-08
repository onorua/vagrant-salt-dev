fluentd-config:
  file.managed:
    - name: /etc/td-agent/td-agent.conf
    - source: salt://k8s/fluentd-es/td-agent.conf
    - template: jinja
    - user: root
    - group: root
    - mode: 644
    - makedirs: true
    - dir_mode: 755
    - defaults:
      dns_domain: {{pillar.dns_domain}}

kubernetes-log-directory:
  file.directory:
    - name: /var/log/kubernetes
    - makedirs: true
    - dir_mode: 755

/etc/kubernetes/manifests/fluentd-es.yaml:
  file.managed:
    - source: salt://k8s/fluentd-es/fluentd-es.yaml
    - template: jinja
    - user: root
    - group: root
    - mode: 644
    - makedirs: true
    - dir_mode: 755
    - require:
      - file: fluentd-config

