# -*- coding: utf-8 -*-
# vim: ft=yaml

#
# Import defaults and settings as 'sample1' for using map.jinja and lookup
#
{% from "sample1/map.jinja" import sample1 with context %}

#
# Installed and required OS specific packages
#
required_utilities:
  pkg.installed:
    - pkgs: {{ sample1.pkgs|json }}

#
# Create a directory for all of this stuff
#
{{ sample1.repo_dir }}:
  file.directory:
    - user: {{ sample1.user }}
    - makedirs: True

#
# Create a simple file in the directory
#
{{ sample1.repo_dir }}/repo_info.txt:
  file.managed:
    - user: {{ sample1.user }}
    - contents: 'Repo Directory'
    - require:
      - file: {{ sample1.repo_dir }}

#
# For all repos described in the sample1 pillar, create a directory
#   and sync a repo from the specifiec URL
#
{% for type, names in salt['pillar.get']('sample1', {}).iteritems() %}
{% if type == 'repo' %}
{% for name, config in names.iteritems() %}
{{ sample1.repo_dir }}/{{ name }}:
  git.latest:
    - name: {{ config.url }}
    - rev: {{ config.rev if config.rev is defined else 'master' }}
    - target: {{ sample1.repo_dir }}/{{ name }}
    - user: {{ sample1.user }}
    - require:
      - pkg: required_utilities
{% endfor %}
{% endif %}
{% endfor %}
