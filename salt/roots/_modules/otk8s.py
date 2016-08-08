'''
Manage Kubernetes secrets from Salt.

:maintainer:    Iaroslav Molochko i.molochko@oberthur.com
:maturity:      new
:depends:       kubectl
:platform:      Linux
'''

from __future__ import absolute_import
import logging as logger

# Import third party libs
try:
#    import requests
#    import requests.exceptions
    import base64
    import os
    import yaml
    import json
    import tempfile
    HAS_LIBS = True
except ImportError:
    HAS_LIBS = False

# Import salt libs
import salt.utils
import salt.output
import salt.exceptions

# Setup the logger
log = logger.getLogger(__name__)


__func_alias__ = {
    'list_': 'list'
}

def __virtual__():
    '''
    Confirm this module is supported by the OS and the system has
    required tools
    '''

    if HAS_LIBS and salt.utils.which('kubectl'):
         return True
    return False


def get_tmpfile(suffix=None):
    if suffix:
        return tempfile.mktemp(suffix=suffix)
    else:
        return tempfile.mktemp(suffix='.yaml')


def load_manifest(filename):
    with open(filename, 'r') as f:
        data = {}
        try:
            data = yaml.load(f)
        except yaml.YAMLError as exc:
            log.error("yaml can't be loaded due to error: [{}]".format(exc))
        except:
            try:
                data = json.load(f)
            except:
                log.error("manifest file {} is neither yaml nor json file or format is wrong")
        return data

def get_path_data(relative_path, prefix=None):
    if prefix:
        abspath = os.path.join([prefix, relative_path])
    else:
        abspath = os.path.abspath(relative_path)
    path_array = abspath.split(os.path.sep)
    paths = {}

    if os.path.isfile(abspath):
        namespace = path_array[-3]
        otype = path_array[-2]
        if otype not in paths:
            paths[otype] = {}
        path, filename = os.path.split(abspath)
        paths[otype][path] = [filename]
    else:
        namespace = path_array[-2]
        otype = path_array[-1]
        if otype not in paths:
            paths[otype] = {}
        paths[otype][abspath] = os.listdir(abspath)

    if not namespace:
        namespace = 'default'
    return namespace, paths


def get_namespaces(list_path_result, childs=2):
    namespaces = [x.split(os.path.sep)[-childs] for x in list_path_result]
    return list(set(namespaces))


def get_namespaces_paths(list_path_result, childs=2):
    namespaces = {}
    for i in list_path_result:
        namespace = i.split(os.path.sep)[-childs]
        namespaces.setdefault(namespace, []).append(i)

    return namespaces


def get_namespaces_manifests(list_path_result, skip_dirs=[]):
    namespaces = {}
    for i in list_path_result:
        namespace = i.split(os.path.sep)[-2]
        dir_name = i.split(os.path.sep)[-1]
        if dir_name not in skip_dirs:
            files = os.listdir(i)
            for f in [x for x in files if x.endswith(".yaml") or x.endswith(".yml") or x.endswith(".json")]:
                namespaces.setdefault(namespace, []).append(os.path.join(i, f))
    return namespaces

def get_namespaces_names(cluster_namespaces_list):
    namespaces = []
    if 'items' in cluster_namespaces_list:
        cluster_namespaces_list  = cluster_namespaces_list.get('items', [])

    for i in cluster_namespaces_list:
        namespace = i.get('metadata', {}).get('name', {})
        if namespace:
            namespaces.append(namespace)
    return namespaces


def get_secret_data(relative_path, prefix=None):
    if prefix:
        abspath = os.path.join([prefix, relative_path])
    else:
        abspath = os.path.abspath(relative_path)
    base64_data = {}
    path_array = abspath.split(os.path.sep)

    if os.path.isfile(abspath):
        namespace = path_array[-3]
        secret_name = path_array[-2]
        _, name = os.path.split(abspath)
        with open(abspath, "rb") as f:
            data = f.read()
            base64_data[name] = base64.b64encode(data)
    else:
        namespace = path_array[-2]
        secret_name = path_array[-1]
        for name in os.listdir(abspath):
            full_path = os.path.join(abspath, name)
            if os.path.isfile(full_path):
                with open(full_path, "rb") as f:
                    data = f.read()
                    base64_data[name] = base64.b64encode(data)

    if not namespace:
        namespace = 'default'

    return namespace, secret_name, base64_data


def get_secret_paths(relative_path, prefix=None):
    if prefix:
        abspath = os.path.join([prefix, relative_path])
    else:
        abspath = os.path.abspath(relative_path)
    paths = []
    path_array = abspath.split(os.path.sep)

    if os.path.isfile(abspath):
        namespace = path_array[-3]
        secret_name = path_array[-2]
        paths.append(abspath)
    else:
        namespace = path_array[-2]
        secret_name = path_array[-1]
        for name in os.listdir(abspath):
            full_path = os.path.join(abspath, name)
            paths.append(full_path)

    if not namespace:
        namespace = 'default'

    return namespace, secret_name, paths


def secret_exists(secrets_list, name):
    for secret in secrets_list:
        if secret.get('metadata', {}).get('name', "") == name:
            return True
    return False

def create_or_update_secret(secrets_list, namespace, secret_name, base64_data):
    secret = None
    for i in secrets_list:
        if secret_name == i.get('metadata', {}).get('name', ''):
            secret = i
            break
    if secret:
        if is_secret_changed(secret, base64_data):
            return update_secret(namespace, secret_name, base64_data)
    else:
        return create_secret(namespace, secret_name, base64_data)
    return True

def is_secret_changed(cluster_secret, base64_data):
    if cluster_secret.get('data') != base64_data:
        return True
    else:
        return False

def create_secret(namespace, secret_name, base64_data, kubeconfig=None):
    request = __salt__['kubernetes.gen_secret'](secret_name, base64_data,
                                                namespace=namespace)
    tfile = get_tmpfile('.json')
    with open(tfile, 'w') as f:
        json.dump(request, f)
    res =  __salt__['kubernetes.kube_create'](tfile, namespace=namespace,
                                              kubeconfig=kubeconfig)
    os.remove(tfile)
    return res

def update_secret(namespace, secret_name, base64_data, kubeconfig=None):
    request = __salt__['kubernetes.gen_secret'](secret_name, base64_data,
                                                namespace=namespace)
    tfile = get_tmpfile()
    with open(tfile, 'w') as f:
        f.write(yaml.dump(request))
    res = __salt__['kubernetes.kube_update'](tfile, namespace=namespace,
                                             kubeconfig=kubeconfig)
    os.remove(tfile)
    return res

def delete_secret(namespace, secret_name, kubeconfig=None):
    res = __salt__['kubernetes.kube_delete']('secrets', secret_name,
                                             namespace=namespace,
                                             kubeconfig=kubeconfig)
    return res

# services management
def get_configured(otype, paths):
    result = []
    for path, files in paths.get(otype, {}).items():
        for f in files:
            data = load_manifest(os.path.join(path,f))
            result.append(data)
    return result

def get_configured_services(path):
    (namespace, paths) = get_path_data(path)
    return get_configured('services', paths)

def create_service(namespace, request, kubeconfig=None):
    tfile = get_tmpfile()
    with open(tfile, 'w') as f:
        f.write(yaml.dump(request))
    res =  __salt__['kubernetes.kube_create'](tfile, namespace=namespace,
                                              kubeconfig=kubeconfig)
    os.remove(tfile)
    return res

def replace_service(namespace, name, request, kubeconfig=None):
    tfile = get_tmpfile()
    with open(tfile, 'w') as f:
        f.write(yaml.dump(request))
    res =  __salt__['kubernetes.kube_update'](tfile, name=name, namespace=namespace,
                                              kubeconfig=kubeconfig)
    os.remove(tfile)
    return res

def delete_service(namespace, request, kubeconfig=None):
    name = request.get('metadata', {}).get('name', "")
    res = __salt__['kubernetes.kube_delete']('services', name,
                                             namespace=namespace,
                                             kubeconfig=kubeconfig)
    return res

def service_exists(services_list, request):
    name = request.get('metadata', {}).get('name', "")
    for service in services_list:
        if service.get('metadata', {}).get('name', "") == name:
            return True
    return False

def create_or_update_service(services_list, local_services, namespace):
    for service_request in local_services:
        if not service_exists(services_list, service_request):
            create_service(namespace, service_request)
        elif is_changed(services_list, service_request):
            delete_service(namespace, service_request)
            create_service(namespace, service_request)
    return True

# RC
def get_configured_rcs(path):
    (namespace, paths) = get_path_data(path)
    return get_configured('rc', paths)

def rc_exists(services_list, request):
    name = request.get('metadata', {}).get('name', "")
    for service in services_list:
        if service.get('metadata', {}).get('name', "") == name:
            return True
    return False


def get_glusterfs_volumes(rc_data, kubeconfig=None):
    all_volumes = rc_data.get('spec', {}).get('template',
                                              {}).get('spec',
                                                      {}).get('volumes', {})
    return [x.get("glusterfs") for x in all_volumes if "glusterfs" in x]


def get_existing_glusterfs_volumes(volumes):
    for volume in volumes:
        pass
    return True


def create_endpoint(namespace, endpoint_name, kubeconfig=None):
    endpoints = __salt__['pillar.get']('gluster_endpoints')
    if endpoint_name in endpoints:
        log.debug("endpoint_data is {}".format(endpoints.get(endpoint_name)))
        __salt__['kubernetes.create_endpoint'](namespace, endpoint_name,
                                               endpoints.get(endpoint_name),
                                              kubeconfig)


def get_all_node_labels(kubeconfig=None):
    nodes =  __salt__['kubernetes.get_all']('nodes', kubeconfig=kubeconfig)
    node_labels = {}
    for n in nodes.get('items'):
        node_name = n.get('metadata', {}).get('name')
        labels = n.get('metadata', {}).get('labels')
        node_labels[node_name] = labels
    return node_labels


def manage_endpoints(namespace, endpoints, volumes):
    endpoint_names = get_names_from_list(endpoints)
    log.debug("available cluster endpoint names are: {}".format(endpoint_names))
    for volume in volumes:
        log.trace("processing volume: {}".format(volume))
        endpoint = volume.get('endpoints', None)
        if endpoint and endpoint not in endpoint_names:
            create_endpoint(namespace, endpoint)
    return True



def create_glusterfs(namespace, volumes, endpoint_names, kubeconfig=None):
    for volume in volumes:
        endpoint = volume.get('endpoint', "none")
        if endpoint not in endpoint_names:
            create_endpoint(namespace, endpoint, kubeconfig)
    return True


def manage_namespaces(namespaces_data):
    changes = {}
    configured_namespaces = namespaces_data.keys()
    log.info("configured namespaces are: "+str(configured_namespaces))
    cluster_namespaces = __salt__['kubernetes.get_all']('namespaces')
    cluster_namespaces = __salt__['otk8s.get_namespaces_names'](cluster_namespaces)
    log.info("available on cluster namespaces are: "+str(cluster_namespaces))

    if not cluster_namespaces:
        cluster_namespaces = []
    if not configured_namespaces:
        configured_namespaces = []

    for namespace in set(configured_namespaces)-set(cluster_namespaces):
        __salt__['kubernetes.create_namespace'](namespace)
        changes["namespace "+namespace] = "namespace {} is created".format(namespace)

    return changes


def gluster_exists(volumes_lists):
    return True


def get_names_from_list(items_list):
    items = []
    for i in items_list:
        name = i.get('metadata', {}).get('name', "")
        items.append(name)
    return items


def create_rc(namespace, request, endpoints = [], kubeconfig=None):
    tfile = get_tmpfile()
    gluster_volumes = get_glusterfs_volumes(request)
    endpoint_names = get_names_from_list(endpoints)
    if gluster_volumes:
        create_glusterfs(namespace, gluster_volumes, endpoint_names, kubeconfig=kubeconfig)
    with open(tfile, 'w') as f:
        f.write(yaml.dump(request))
    res =  __salt__['kubernetes.kube_create'](tfile, namespace=namespace,
                                              kubeconfig=kubeconfig)
    os.remove(tfile)
    return res


def replace_rc(namespace, name, request, kubeconfig=None):
    tfile = get_tmpfile()
    with open(tfile, 'w') as f:
        f.write(yaml.dump(request))
    res =  __salt__['kubernetes.kube_update'](tfile, name=name, namespace=namespace,
                                              kubeconfig=kubeconfig)
    os.remove(tfile)
    return res

def rolling_update(namespace, new_name, old_name, request, kubeconfig=None):
    tfile = get_tmpfile()
    with open(tfile, 'w') as f:
        f.write(yaml.dump(request))
    res =  __salt__['kubernetes.kube_rolling_update'](manifest=tfile,
                                                      old_name=old_name,
                                                      new_name=new_name,
                                                      namespace=namespace,
                                                      kubeconfig=kubeconfig)
    os.remove(tfile)
    return res

def delete_rc(namespace, request, kubeconfig=None):
    name = request.get('metadata', {}).get('name', "")
    res = __salt__['kubernetes.kube_delete']('rc', name,
                                             namespace=namespace,
                                             kubeconfig=kubeconfig)
    return res

def create_or_update_rc(rcs_list, local_rcs, namespace):
    for rc_request in local_rcs:
        if not rc_exists(rcs_list, rc_request):
            create_rc(namespace, rc_request)
        elif is_scaled(rcs_list, rc_request):
            changes = __salt__['kubernetes.is_changed'](request, service)
            create_rc(namespace, rc_request)
        elif is_changed(rcs_list, rc_request):
            delete_rc(namespace, rc_request)
            create_rc(namespace, rc_request)
    return True

def path_listing(list_path, childs=2):
    result = []
    sep = os.path.sep
    if list_path[-1] == sep:
        list_path = list_path[:-1]
    c = len(list_path.split(sep))
    if os.path.isdir(list_path):
        for root, dirs, files in os.walk(list_path):
            if not dirs and '.git' not in root \
               and (len(root.split(sep)) - c) == childs and files:
                result.append(root)
    return result


def is_changed(request, service):
    changes = __salt__['kubernetes.is_changed'](request, service)
    if changes:
        if 'dic_item_removed' in changes:
            changes.pop("dic_item_removed")
        if changes:
            log.warn(changes)
        return changes
    else:
        return False

