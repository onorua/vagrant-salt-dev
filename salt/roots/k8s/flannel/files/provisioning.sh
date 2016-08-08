#!/bin/bash

source /etc/kubernetes/flannel_etcd

etcd_address=${ETCD_LIST[$RANDOM % ${#ETCD_LIST[@]} ]}

/usr/bin/curl -L http://${etcd_address}/v2/keys/${ETCD_PREFIX}/network/config -XPUT --data-urlencode value@/etc/kubernetes/flannel.json

exit 0;
