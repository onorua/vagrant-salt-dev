{% set docker_version = pillar.get("override_docker_ver", "") %}

install-utils:
  pkg.installed:
    - pkgs: 
      - bridge-utils
      - python-apt
      - iptables-persistent

{% set docker_name = "docker-engine" %}
{% set deb_url = "deb https://apt.dockerproject.org/repo " ~ grains.os|lower ~ "-" ~ grains.oscodename|lower ~ " main" %} 
{% if docker_version %}
{% set docker_version = docker_version ~ "*" %}
{% else %}
{% set docker_version = false %}
{% endif %}

docker-repo:
  pkgrepo.managed:
    - humanname: Docker repo
    - name: {{deb_url}}
    - file: /etc/apt/sources.list.d/docker.list
    - keyid: 58118E89F3A912897C070ADBF76221572C52609D
    - keyserver: hkp://pgp.mit.edu:80
    - refresh_db: True
    - require_in:
        - pkg: {{ docker_name }}

{{docker_name}}:
  pkg.installed:
    - name: {{docker_name}}
{% if docker_version %}
    - version: {{docker_version}}
{% endif %}
    - require:
      - file: /etc/systemd/system/docker.service.d/local.conf
      - file: /etc/systemd/system/docker.service.d/http-proxy.conf

net.ipv4.ip_forward:
  sysctl.present:
    - value: 1

{% set http_proxy = pillar.get("docker_http_proxy", pillar.get("http_proxy")) %}
{% if http_proxy %}
/etc/systemd/system/docker.service.d/http-proxy.conf:
  file.managed:
    - source: salt://deploy/docker/files/http-proxy.conf
    - template: jinja
    - user: root
    - group: root
    - mode: 644
    - makedirs: true
    - defaults:
      http_proxy: {{http_proxy}}
{% else %}
/etc/systemd/system/docker.service.d/http-proxy.conf:
  file.absent
{% endif %}


/etc/systemd/system/docker.service.d/local.conf:
  file.managed:
    - source: salt://deploy/docker/files/docker.dropin
    - template: jinja
    - user: root
    - group: root
    - mode: 644
    - makedirs: true

/opt/kubernetes/helpers/docker-healthcheck:
  file.managed:
    - source: salt://deploy/docker/files/docker-healthcheck
    - makedirs: true
    - user: root
    - group: root
    - mode: 755

/lib/systemd/system/docker-healthcheck.service:
  file.managed:
    - source: salt://deploy/docker/files/docker-healthcheck.service
    - template: jinja
    - user: root
    - group: root
    - mode: 644

/lib/systemd/system/docker-healthcheck.timer:
  file.managed:
    - source: salt://deploy/docker/files/docker-healthcheck.timer
    - template: jinja
    - user: root
    - group: root
    - mode: 644

docker:
  service.running:
    - enable: True
    - watch:
      - file: /etc/systemd/system/docker.service.d/local.conf
      - pkg: {{docker_name}}
    - require:
      - pkg: {{docker_name}}
    - order: last
  module.wait:
    - name: service.systemctl_reload
    - watch:
      - file: /etc/systemd/system/docker.service.d/local.conf
      - file: /etc/systemd/system/docker.service.d/http-proxy.conf

docker-healthcheck:
  service.running:
    - enable: True
    - watch:
      - file: /lib/systemd/system/docker-healthcheck.service
      - file: /lib/systemd/system/docker-healthcheck.timer
  module.wait:
    - name: service.systemctl_reload
    - watch:
      - file: /lib/systemd/system/docker-healthcheck.service

docker-healthcheck.timer:
  service.running:
    - enable: True
    - watch:
      - file: /lib/systemd/system/docker-healthcheck.timer
  module.wait:
    - name: service.systemctl_reload
    - watch:
      - file: /lib/systemd/system/docker-healthcheck.timer

{% if pillar.get("docker_auth") %}

/root/.dockercfg:
  file.managed:
    - source: salt://deploy/docker/files/dockercfg
    - template: jinja
    - user: root
    - group: root
    - mode: 644
    - makedirs: true
    - defaults:
      docker_auth: {{pillar.docker_auth}}

/.dockercfg:
  file.managed:
    - source: salt://deploy/docker/files/dockercfg
    - template: jinja
    - user: root
    - group: root
    - mode: 644
    - makedirs: true
    - defaults:
      docker_auth: {{pillar.docker_auth}}

/root/.docker/config.json:
  file.managed:
    - source: salt://deploy/docker/files/docker.config
    - template: jinja
    - user: root
    - group: root
    - mode: 644
    - makedirs: true
    - defaults:
      docker_auth: {{pillar.docker_auth}}
{% endif %}
