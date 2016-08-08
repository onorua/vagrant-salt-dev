{% for namespace in salt["k8s.get"]("namespaces", names_only=true) %}
{% set limits_path = "k8s:limits:" ~ namespace %}
{{namespace}}-limits:
  k8s.limits_managed:
    - name: limits
    - namespace: {{namespace}}
    - limits:
    {% if  salt["pillar.get"](limits_path) %}
    {% for limit in salt["pillar.get"](limits_path) %}
      - {{limit}}
    {% endfor %}
    {% else %}
      - type: Container
        defaultRequest:
          cpu: {{salt["pillar.get"]("k8s:default_limits:requests_cpu", "250m") }}
          memory: {{salt["pillar.get"]("k8s:default_limits:requests_memory", "250Mi")}}
        default:
          cpu: {{salt["pillar.get"]("k8s:default_limits:max_cpu", "500m") }}
          memory: {{salt["pillar.get"]("k8s:default_limits:max_memory", "1Gi") }}
    {% endif %}
{% endfor %}
