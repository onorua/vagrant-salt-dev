/etc/kubernetes/addons:
  file.directory

{% set  enabled_addons = [] %}

{% for addon in salt['pillar.get']('k8s:addons') %}
{% do enabled_addons.append(addon) %}
{% set prefix = 'k8s/addons/' ~ addon %}
{% for manifest in salt['cp.list_master'](prefix=prefix) %}
{% set items = manifest.split('/') %}
{% set filename = items|last %}
{% if "yaml" in filename|lower or "yml" in filename|lower or "json" in filename|lower %}
/etc/kubernetes/addons/{{addon}}/{{filename}}:
  file.managed:
    - source: salt://{{ manifest }}
    - makedirs: true
    - template: jinja

k8s-/etc/kubernetes/addons/{{addon}}/{{filename}}:
  k8s.manage_manifest:
    - name: /etc/kubernetes/addons/{{addon}}/{{filename}}
    - update: true

{% endif %}
{% endfor %}
{% endfor %}

{% set to_remove = [] %}
{# cleanup of the old manifests #}
{% set prefix = 'k8s/addons/' %}
{% for manifest in salt['cp.list_master'](prefix=prefix) %}
{% set items = manifest.split('/') %}
{% if items[2] not in enabled_addons and items[2] not in to_remove%} 
{% do to_remove.append(items[2]) %}
{% endif %}
{% endfor %}

{% for removeme in to_remove %}
remove /etc/kubernetes/addons/{{removeme}}:
  file.absent:
    - name: /etc/kubernetes/addons/{{removeme}}
{% endfor %}
