# deliver kubernetes binaries which are not dockerized yet

Generally it checks `cluster_version` and pull docker image:
`onorua/kube-bins:{{cluster_version}}` then run it, mounting master filesystem and copy binary files onto predefined folder. 
