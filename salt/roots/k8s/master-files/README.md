# deployment, services and secrets management

Checks the configuration, executes `git pull` and call callback salt-stack state:

```
master_files:
  - name: git-secrets
    url: https://url
    folder: /srv/kube-data/secrets
    revision: master
    https_user: username
    https_pass: "password"
    callbacks:
      - otk8s.manage_secrets

  - name: git-deployments
    url: https://url
    folder: /srv/kube-data/deployments
    https_user: username
    https_pass: "password"
    revision: master
    callbacks:
      - otk8s.manage_manifests
```

you can also get it through ssh auth here, but just an example
