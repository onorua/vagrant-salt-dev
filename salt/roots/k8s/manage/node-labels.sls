{% set node_names = salt["k8s.get"]("nodes", names_only=true) %}

{% for node, labels in pillar.get("node_labels", {}).iteritems() %}
{% for label, value in labels.iteritems() %}
{% if node in node_names %}
{{node}}-{{label}}:
  k8s.node_label_present:
    - name: '{{label}}'
    - node: '{{node}}'
    - value: '{{value}}'
{% endif %}
{% endfor %} {# end label for #}
{% endfor %} {# end hostname for #}

{% for node, labels in salt["pillar.get"]("k8s:node_labels", {}).iteritems() %}
{% for label, value in labels.iteritems() %}
{% if node in node_names %}
"k8s-{{node}}-{{label}}":
  k8s.node_label_present:
    - name: '{{label}}'
    - node: '{{node}}'
    - value: '{{value}}'
{% endif %}
{% endfor %} {# end label for #}
{% endfor %} {# end hostname for #}
