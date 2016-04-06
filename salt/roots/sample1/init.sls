# -*- coding: utf-8 -*-
# vim: ft=yaml

#
# Import defaults and settings as 'map' for sample1 using jinja
#
{% from "sample1/map.jinja" import map with context %}

#
# Installed and required OS specific packages
#
required_utilities:
  pkg.installed:
    - pkgs: {{ map.pkgs|json }}

#
# Create a directory for all of this stuff
#
{{ map.repo_dir }}:
  file.directory:
    - user: {{ map.user }}
    - makedirs: True

#
# Create a simple file in the directory
#
{{ map.repo_dir }}/repo_info.txt:
  file.managed:
    - user: {{ map.user }}
    - contents: 'Repo Directory'
    - require:
      - file: {{ map.repo_dir }}

#
# For all repos described in the sample1 pillar, create a directory
#   and sync a repo from the specifiec URL
#
{% for type, names in salt['pillar.get']('sample1', {}).iteritems() %}
{% if type == 'repo' %}
{% for name, config in names.iteritems() %}
{{ map.repo_dir }}/{{ name }}:
  git.latest:
    - name: {{ config.url }}
    - rev: {{ config.rev if config.rev is defined else 'master' }}
    - target: {{ map.repo_dir }}/{{ name }}
    - user: {{ map.user }}
    - require:
      - pkg: required_utilities
{% endfor %}
{% endif %}
{% endfor %}
