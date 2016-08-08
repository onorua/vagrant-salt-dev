{% for namespace in salt["k8s.get"]("namespaces", names_only=true) %}
{% set quota_path = "k8s:quotas:" ~ namespace %}

{% if  salt["pillar.get"](quota_path) or salt["pillar.get"]("k8s:default_quotas", {}) %}

{{namespace}}-quota:
  k8s.quotas_managed:
    - name: "quota"
    - namespace: {{namespace}}
    - quotas:
    {% set quota_list = [] %}
    {% for quota in salt["pillar.get"](quota_path) %}
       - {{quota}}
       {% for key, val in quota.iteritems() %}
       {% do quota_list.append(key) %}
       {% endfor %}
    {% endfor %}

    {% if "cpu" not in quota_list and salt["pillar.get"]("k8s:default_quotas:cpu") %}
       - cpu: {{salt["pillar.get"]("k8s:default_quotas:cpu") }}
    {% endif %}

    {% if "memory" not in quota_list and salt["pillar.get"]("k8s:default_quotas:memory") %}
       - memory: {{salt["pillar.get"]("k8s:default_quotas:memory")}}
    {% endif %}

{% endif %}

{% endfor %}
