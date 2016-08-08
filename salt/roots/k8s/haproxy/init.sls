/etc/haproxy/haproxy.conf:
  file.managed:
    - source: salt://k8s/haproxy/files/haproxy.conf
    - template: jinja
    - makedirs: true

/etc/kubernetes/manifests/api-lb-haproxy.manifest:
  file.managed:
    - source: salt://k8s/haproxy/files/haproxy.pod
    - template: jinja
    - makedirs: true
    - require:
      - file: /etc/haproxy/haproxy.conf

kill-api-lb-haproxy-docker:
  cmd.wait:
    - name: which docker && sleep 1 && timeout --preserve-status 5 docker rm -f $(timeout 3 docker ps | grep k8s_k8s-lb-haproxy | awk {'print $1'})
    - watch:
      - file: /etc/haproxy/haproxy.conf
    - onlyif: which docker && timeout --preserve-status 5 docker ps | grep -q k8s_k8s-lb-haproxy
