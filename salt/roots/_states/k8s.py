# -*- coding: utf-8 -*-
'''
Manage Kubernetes

.. versionadded:: 2016.3.0

.. code-block:: yaml

    kube_label_1:
      k8s.label_present:
        - name: mylabel
        - value: myvalue
        - node: myothernodename
        - apiserver: http://mykubeapiserer:8080

    kube_label_2:
      k8s.label_absent:
        - name: mylabel
        - node: myothernodename
        - apiserver: http://mykubeapiserer:8080

    kube_label_3:
      k8s.label_folder_present:
        - name: mylabel
        - node: myothernodename
        - apiserver: http://mykubeapiserer:8080

    k8s-quota:
      k8s.quotas_managed:
        - name: "quota"
        - namespace: kube-system
        - quotas:
           - cpu: 20
           - memory: 1Gi
           - persistentvolumeclaims: "10"
           - pods: "10"
           - replicationcontrollers: "20"
           - resourcequotas: "1"
           - secrets: "10"
           - services: "5"
'''

__virtualname__ = 'k8s'


def __virtual__():
    '''Load only if kubernetes module is available.'''
    if 'k8s.get' not in __salt__:
        return False
    return True


def node_label_present( name, value, node, kubeconfig="", context_name=""):
    '''
    Ensure the label exists on the kube node.

    name
        Name of the label.

    value
        Value of the label.

    node
        Override node ID.

    apiserver
        K8S apiserver URL.

    '''
    # Use salt k8s module to set label
    return __salt__['k8s.label']("nodes", name=node, var=name, val=value, kubeconfig=kubeconfig, context_name=context_name)


def node_label_absent( name, node=None, kubeconfig="", context_name=""):
    '''
    Ensure the label doesn't exist on the kube node.

    name
        Name of the label.

    node
        Override node ID.

    apiserver
        K8S apiserver URL.

    '''
    # Use salt k8s module to set label
    return __salt__['k8s.label']("nodes", name=node, var=name, kubeconfig=kubeconfig, context_name=context_name)


def label_folder_absent( name, node=None, kubeconfig="", context_name=""):
    '''
    Ensure the label folder doesn't exist on the kube node.

    name
        Name of the label folder.

    node
        Override node ID.

    apiserver
        K8S apiserver URL.

    '''
    # Use salt k8s module to set label
    return __salt__['k8s.folder_absent'](name, node, kubeconfig=kubeconfig,
                                         context_name=context_name)


def namespace_present(name, kubeconfig="", context_name=""):
    '''
    Ensure the label folder doesn't exist on the kube node.

    name
        Name of the namespace

    apiserver
        K8S apiserver URL.

    '''

    # Use salt k8s module to set label
    return __salt__['k8s.namespace_present'](name, kubeconfig=kubeconfig,
                                            context_name=context_name)


def secret_managed(name, namespace, sources, kubeconfig="", context_name="", update=True,
                   force=True):
    '''
    Ensure the label folder doesn't exist on the kube node.

    name
        Name of the namespace

    apiserver
        K8S apiserver URL.

    '''

    # Use salt k8s module to set label
    return __salt__['k8s.secret_create'](namespace, name, sources,
                                        kubeconfig=kubeconfig,
                                        context_name=context_name,
                                        update=update, force=force)


def quotas_managed(name, namespace, quotas, kubeconfig="",
                   context_name="", update=True, force=True):
    '''
    Ensure the label folder doesn't exist on the kube node.

    name
        Name of the namespace

    apiserver
        K8S apiserver URL.

    '''

    # Use salt k8s module to set label
    return __salt__['k8s.create_resource_quota'](namespace, quotas, name,
                                                kubeconfig=kubeconfig,
                                                context_name=context_name, update=update, force=force)


def limits_managed(name, namespace, limits, kubeconfig="", context_name="", update=True, force=True):
    '''
    Ensure the label folder doesn't exist on the kube node.

    name
        Name of the namespace

    apiserver
        K8S apiserver URL.

    '''

    # Use salt k8s module to set label
    return __salt__['k8s.create_limit_range'](namespace, limits, name,
                                              kubeconfig=kubeconfig,
                                              context_name=context_name,
                                              update=update, force=force)


def manage_manifest(name, namespace="", kubeconfig="", context_name="", force=True, replace_namespace=True, update=True, saltenv='base'):
    '''
    Ensure the label folder doesn't exist on the kube node.

    name
        Name of the namespace

    apiserver
        K8S apiserver URL.

    '''

    # Use salt k8s module to set label
    return __salt__['k8s.create'](name, namespace=namespace,
                                  kubeconfig=kubeconfig,
                                  context_name=context_name, force=force,
                                  replace_namespace=replace_namespace,
                                  update=update, saltenv=saltenv)


def cordon(name, kubeconfig="", context_name=""):
    return __salt__['k8s.cordon'](node=name, kubeconfig=kubeconfig, context_name=context_name)


def uncordon(name, kubeconfig="", context_name=""):
    return __salt__['k8s.uncordon'](node=name, kubeconfig=kubeconfig, context_name=context_name)


def maintenance_mode(name, kubeconfig="", context_name=""):
    if __salt__['k8s.cordon'](node=name, kubeconfig=kubeconfig, context_name=context_name).get('result'):
        return __salt__['k8s.drain'](node=name, kubeconfig=kubeconfig, context_name=context_name)

def drain(name, kubeconfig="", context_name=""):
    return __salt__['k8s.drain'](node=name, kubeconfig=kubeconfig, context_name=context_name)
