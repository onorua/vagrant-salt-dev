{% if 'kubernetes-master' in  grains.get('roles', {})  and pillar.master_files is defined -%}
{% for item in pillar.master_files %}

{% if item.url is defined %}
{{item.name}}:
  git.latest:
    - name: {{item.url}}
    - target: {{item.folder}}
    - force_checkout: true
    - force_clone: true
    - rev: {{item.revision|default("master")}}
    - force_reset: true
    - force_fetch: true
    - https_user: "{{item.https_user}}"
    - https_pass: "{{item.https_pass}}"
{% endif %}

{% if item.callbacks is defined %}
{% for callback in item.callbacks %}
{{callback}}_{{loop.index}}:
  {{callback}}:
    - name: {{item.folder}}
{% if item.url is defined %}
    - require:
      - git: {{item.name}}
{% endif %}
      {% endfor %}
      {% endif %}

{% endfor %}


{% endif %}
