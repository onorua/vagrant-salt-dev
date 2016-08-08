# Import Python libs
from __future__ import absolute_import
import time
import yaml
import logging as logger
log = logger.getLogger(__name__)


def __virtual__():
    '''
    Only make these states available if a service provider has been detected or
    assigned for this minion
    '''
    return 'otk8s.create_secret' in __salt__

#def manage_node_labels(name, node_labels):
#    """
#    node_lables is dictionary with following format:
#    fqdn (as grains fqdn):
#      - label1_name: label1_value
#      - label2_name: label2_value
#    """
#    ret = {'name': name,
#           'changes': {},
#           'result': True,
#           'comment': ''}
#    cluster_node_labels = __salt__['otk8s.get_all_node_labels']()
#    log.debug("Cluster labels {}".format(cluster_node_labels))
#    for node, lbls in node_labels.items():
#        # we need to make sure values are string
#        lbls = [(k,str(v)) for k,v in lbls.items()]
#        log.debug("Configured labels for node: {}".format(lbls))
#        if node in cluster_node_labels:
#            log.debug("Cluster labels for node: {}".format(cluster_node_labels[node]))
#            labels = set(lbls) - set(cluster_node_labels[node].items())
#            labels = ["{}={}".format(k[0], k[1]) for k in labels]
#            if labels and __salt__['kubernetes.label']('node', node, " ".join(labels)):
#                ret['changes'][node] = "added labels: {}".format(labels)
#    return ret

def manage_secrets(name):
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}
    if not name:
        return ret

    paths =  __salt__['otk8s.path_listing'](name)
    namespaces_data = __salt__['otk8s.get_namespaces_paths'](paths)
    configured_namespaces = namespaces_data.keys()
    for ns in  namespaces_data.keys():
        res = __salt__['k8s.create_namespace'](ns)
        if res.get("changes") != {}:
            ret["changes"]["namespace {0}".format(ns)] = res.get("changes")

    for namespace in configured_namespaces:
        cluster_secrets = __salt__['k8s.get']('secrets', namespace=namespace)
        if cluster_secrets:
            cluster_secrets = cluster_secrets.get('items', [])
        else:
            cluster_secrets = []
        for p in namespaces_data[namespace]:
            n, secret_name, data = __salt__['otk8s.get_secret_paths'](p)
            res = __salt__['k8s.create_secret'](namespace, secret_name, data, update=True, force=True)
            if res.get("changes") != {}:
                ret["changes"]["secret {0}".format(secret_name)] = res.get("changes")
    return ret

def manage_services(name):
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}
    if not name:
        return ret

    paths =  __salt__['otk8s.path_listing'](name)
    namespaces_data = __salt__['otk8s.get_namespaces_paths'](paths)
    configured_namespaces = namespaces_data.keys()
    for ns in  namespaces_data.keys():
        res = __salt__['k8s.create_namespace'](ns)
        if res.get("changes") != {}:
            ret["changes"]["namespace {0}".format(ns)] = res.get("changes")

    for namespace in configured_namespaces:
        cluster_services = __salt__['k8s.get']('services', namespace=namespace)
        cluster_services = cluster_services.get('items', {})
        for p in namespaces_data[namespace]:
            n, paths = __salt__['otk8s.get_path_data'](p)
            local_services = __salt__['otk8s.get_configured']('services', paths)

            for service in local_services:
                if not service or not isinstance(service, dict):
                    continue
                __salt__["k8s.create_service"](namespace, service, update=True,
                                               replace_namespace=True)
    return ret

def manage_replication_controllers(name):
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}
    if not name:
        return ret

    paths =  __salt__['otk8s.path_listing'](name)
    namespaces_data = __salt__['otk8s.get_namespaces_paths'](paths)
    configured_namespaces = namespaces_data.keys()
    for ns in  namespaces_data.keys():
        res = __salt__['k8s.create_namespace'](ns)
        if res.get("changes") != {}:
            ret["changes"]["namespace {0}".format(ns)] = res.get("changes")

    for namespace in configured_namespaces:
        endpoints = __salt__['k8s.get']('endpoints', namespace=namespace)
        if endpoints:
            endpoints = endpoints.get('items', [])
        cluster_rcs = __salt__['k8s.get']('rc', namespace=namespace)
        cluster_rcs = cluster_rcs.get('items', {})
        for p in namespaces_data[namespace]:
            namespace, paths = __salt__['otk8s.get_path_data'](p)
            local_rcs = __salt__['otk8s.get_configured']('rcs', paths)
            for lrc in local_rcs:
                __salt__['k8s.create_rc'](namespace, lrc, update=True,
                                          replace_namespace=True)
    return ret


def manage_manifests(name):
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}
    if not name:
        return ret

    skip_dirs = ["pods"]
    paths =  __salt__['otk8s.path_listing'](name)
    namespaces_data = __salt__['otk8s.get_namespaces_manifests'](paths,
                                                                 skip_dirs=skip_dirs)
    for namespace, manifests in namespaces_data.iteritems():
        for manifest in manifests:
            res = __salt__['k8s.create'](manifest, namespace=namespace, update=True, replace_namespace=True)
            if res.get('changes'):
                ret['changes'][manifest] = res.get('changes')
    return ret
