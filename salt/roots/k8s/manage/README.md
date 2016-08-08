# manage labels, quotas, limits of k8s

Manage quotas:
```
k8s:
  default_quotas:
    cpu: 2
    memory: 4Gi
  quotas:
    default:
      - memory: 14Gi
      - cpu: 6
    kube-system:
      - memory: 16Gi
      - cpu: 8
```

node lables:

```
node_labels:

  ip-172-16-236-25.k8s.otlabs.fr:
    zone: common
    role: admin
```
