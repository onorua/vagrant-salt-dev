# -*- coding: utf-8 -*-
'''
Salt module to manage Kubernetes cluster

.. versionadded:: 2016.3.0

Roadmap:

* Add (auto)scalling

'''

from __future__ import absolute_import

import os
import re
import logging
import random
import json
import copy
import base64
import hashlib
import tempfile
import time
from urllib import basejoin as urljoin
from salt.ext.six.moves.urllib.parse import urlparse as _urlparse  # pylint: disable=no-name-in-module
import salt.ext.six as six
import yaml

import salt.utils.http as http
from salt.utils import dictdiffer, traverse_dict
from salt.utils.dictupdate import update as dictupdate
from salt.utils.dictupdate import merge as dictmerge

__virtualname__ = 'k8s'

# Setup the logger
log = logging.getLogger(__name__)

HASH_ANNOTATION = "salt/sha1"
FORBIDDEN_ANNOTATION = "salt/failing"


def __virtual__():
    '''Load module'''
    return __virtualname__


class Kubernetes(object):

    def __init__(self, kubeconfig="", context_name=""):
        self.context_name = context_name
        self.kubeconfig = kubeconfig
        self.client_crt = tempfile.mktemp()
        self.client_key = tempfile.mktemp()
        self.ca = tempfile.mktemp()
        self.known_namespaces = []
        self.get_auth()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        for i in [self.client_crt, self.client_key, self.ca]:
            try:
                os.unlink(i)
            except OSError:
                pass
            except Exception as e:
                log.info('could not cleanup tmp file %s due to error %s', i, e)

    def guess_api_version(self, kind):
        kind = self.kind(kind)
        if kind == 'replicationcontrollers':
            return 'v1'
        else:
            return 'extensions/v1beta1'

    @staticmethod
    def load_manifest(filename):
        """ load manifest in yaml or json format into the dictionary or array of dictionaries
        support multiple documents in single file """
        data = []
        if not filename:
            return {}
        if not os.path.isfile(filename):
            log.error("path %s is not file", filename)
            return {}
        log.debug("loading manifest %s", filename)
        with open(filename, 'r') as f:
            try:
                for i in yaml.safe_load_all(f):
                    if isinstance(i, six.string_types):
                        log.error("expected manifest data, but got plaintext: %s", i)
                    else:
                        data.append(i)
            except yaml.YAMLError as exc:
                log.error("yaml can't be loaded due to error: [%s]", exc)
            except:
                try:
                    for line in f:
                        while True:
                            try:
                                jobj = json.loads(line)
                                break
                            except ValueError:
                                # Not yet a complete JSON value
                                line += next(f)
                        data.append(jobj)
                except:
                    log.error("manifest file %s is neither yaml nor json file or format is wrong", filename)
        if len(data) == 1:
            return data[0]
        else:
            return data

    def _get_context(self):
        """
        Get the context info such as:
            cluster info
            user info
        from kubeconfig file, if context_name is not set,
        current-context will be used automatically.
        """
        config = self.load_manifest(self.kubeconfig)

        if not self.context_name:
            self.context_name = config.get('current-context')
        log.debug('context name is: %s', self.context_name)

        for i in config.get('contexts', []):
            if i.get('name', '') == self.context_name:
                context = i.get('context')
                break
        else:
            return {}

        cluster_name = context.get('cluster')
        user_name = context.get('user')

        for i in config.get('clusters', []):
            if i.get('name', '') == cluster_name:
                cluster = i.get('cluster', {})
                log.trace("cluster info: %s", cluster)
                break
        else:
            return {}

        for i in config.get('users', []):
            if i.get('name', '') == user_name:
                user = i.get('user', {})
                log.trace("user info: %s", cluster)
                break
        else:
            return {}

        return dictmerge(cluster, user)

    def get_context_name(self):
        return self.context_name

    @staticmethod
    def get_names(kobj):
        """ get names out of any object received by kubernetes or array of objects"""
        log.trace("got kubernetes object: %s", kobj)
        names = []
        if "items" in kobj:
            for i in kobj.get("items", []):
                name = traverse_dict(i, "metadata:name", None)
                if name:
                    names.append(name)
        elif traverse_dict(kobj, "metadata:name", None):
            names.append(traverse_dict(kobj, "metadata:name", None))
        log.trace("got names: %s", names)
        return names

    @staticmethod
    def get_labels(kobj, label_name=None):
        '''Get all labels from a kube object.'''
        if label_name:
            return traverse_dict(kobj, "metadata:labels:{0}".format(label_name), None)
        return traverse_dict(kobj, "metadata:labels", None)

    def get_auth(self):
        context = self._get_context()
        self.auth = {}

        self.api_server = context.get('server', 'http://127.0.0.1:8080')

        if 'client-certificate-data' in context and 'client-key-data' in context:
            # we have client certification auth
            log.trace('client-certificate-data %s', context.get('client-certificate-data', ""))
            with open(self.client_crt, 'w') as crt:
                crt.write(base64.decodestring(context.get('client-certificate-data', "")))
            log.trace('client-key-data %s', context.get('client-key-data', ""))
            with open(self.client_key, 'w') as key:
                key.write(base64.decodestring(context.get('client-key-data', "")))
            self.auth['cert'] = (self.client_crt, self.client_key)

        if self.api_server.startswith('https'):
            log.trace('certificate-authority-data %s', context.get('certificate-authority-data', ""))
            with open(self.ca, 'w') as ca:
                ca.write(base64.decodestring(context.get('certificate-authority-data', "")))
            self.auth['ca_bundle'] = self.ca
            self.auth['verify_ssl'] = True

        # token and username/password are mutually exclusive
        if 'token' in context:
            self.auth.setdefault('header_dict', {})['Authorization'] = 'Bearer {0}'.format(context.get('token'))
        elif 'username' in context and 'password' in context:
            self.auth['username'] = context.get('username')
            self.auth['password'] = context.get('password')

        log.trace('kubernetes login information: %s', self.auth)
        return self.auth

    def url(self, path):
        log.debug("generated url: %s", urljoin(self.api_server, path))
        return urljoin(self.api_server, path)

    @staticmethod
    def kind(kind):
        """ generate normalized kind name out of user defined ones: """
        # format is 0 element is "expected" by k8s the rest is aliases
        kinds = {
            "pods": ["pod", "po"],
            "services": ["service", "svc", "svcs"],
            "deployments": ["deployment"],
            "replicasets": ["rs"],
            "replicationcontrollers": ["rc", "rcs", "replicationcontroller"],
            "nodes": ["no", "node", ],
            "events": ["ev", "event", "evs"],
            "limitranges": ["limitrange", "limit", "limits"],
            "persistentvolumes": ["pv", "persistentvolume", "pvs"],
            "persistentvolumeclaims": ["pvc", "persistentvolumeclaim", "pvcs"],
            "resourcequotas": ["resourcequota", "quota", "quotas"],
            "namespaces": ["namespace", "ns"],
            "serviceaccounts": [],
            "ingresses": ["ing"],
            "horizontalpodautoscalers": ["hpa"],
            "daemonsets": ["ds"],
            "configmaps": ["configmap"],
            "componentstatuses": ["cs"],
            "endpoints": ["ep", "endpoint"],
            "secrets": ["secret"]
        }

        log.trace("Got object for normalization: %s", kind)
        if isinstance(kind, bool):
            # for some reason k8s.get no produces False as input
            kind = "nodes"
        else:
            kind = kind.lower()
            for k, v in kinds.iteritems():
                if kind == k or kind in v:
                    kind = k
                    break

        log.trace("normalized object is: %s", kind)
        return kind

    @staticmethod
    def is_dns_subdomain(name):
        ''' Check that name is DNS subdomain: One or more lowercase rfc1035/rfc1123
        labels separated by '.' with a maximum length of 253 characters '''

        dns_subdomain = re.compile(r"""^[a-z0-9\.-]{1,253}$""")
        return bool(dns_subdomain.match(name))

    def get_path(self, kind, namespace="", name="", api=""):
        " generate URL based on values "
        kind = self.kind(kind)

        if api == 'extensions/v1beta1' or api == '/apis/extensions/v1beta1':
            api = '/apis/extensions/v1beta1'
        else:
            api = '/api/v1'

        if kind == 'namespaces':
            if namespace:
                return '{api}/namespaces/{namespace}'.format(api=api, namespace=namespace)
            elif name:
                return '{api}/namespaces/{namespace}'.format(api=api, namespace=name)

        if name and namespace:
            return '{api}/namespaces/{namespace}/{kind}/{name}'.format(api=api, namespace=namespace, kind=kind, name=name)
        elif kind == 'nodes' and namespace and not name:
            return '{api}/{kind}/{name}'.format(api=api, kind=kind, name=namespace)
        elif namespace:
            return '{api}/namespaces/{namespace}/{kind}'.format(api=api, namespace=namespace, kind=kind)
        elif name:
            return '{api}/{kind}/{name}'.format(api=api, kind=kind, name=name)
        else:
            return '{api}/{kind}'.format(api=api, kind=kind)

    def get(self, path, data=None):
        ''' get any object from kubernetes based on URL '''

        # Make request
        try:
            ret = http.query(self.url(path), method='GET', params=data, raise_error=False, **self.auth)
        except Exception as exp:
            log.error("Can't make request due to error: %s", exp)
            raise Exception(str(exp))

        log.trace("GET got a reply: %s", ret)

        try:
            body = json.loads(ret.get('body'))
        except TypeError as exp:
            # body is None
            log.info("could not load json from body due to [%s], input is [%s]", exp, ret)
            body = {}
        if body.get('kind') == 'Status' and body.get('status') == 'Failure':
            if body.get('code') == 404:
                raise LookupError
            else:
                raise Exception(body)
        return body

    def delete(self, path, data=None):
        ''' delete any object from kubernetes based on URL '''

        # Make request
        try:
            ret = http.query(self.url(path), method='DELETE',
                             data=json.dumps(data), raise_error=False, **self.auth)
        except Exception as exp:
            log.error("Can't make request due to error: %s", exp)
            raise exp

        log.trace("DELETE got a reply: %s", ret)

        body = json.loads(ret.get('body'))
        if body.get('kind') == 'Status' and body.get('status') == 'Failure':
            raise Exception(body)
        return body

    def post(self, path, data):
        ''' create any object in kubernetes based on URL '''

        auth = copy.copy(self.auth)

        # Prepare headers
        header = {"Content-Type": "application/json"}
        auth['header_dict'] = dictmerge(header, auth.get('header_dict', {}))
        # Make request
        try:
            ret = http.query(self.url(path), method='POST', data=json.dumps(data), raise_error=False, **auth)
        except Exception as exp:
            log.error("Can't make request due to error: %s", exp)
            raise exp

        # Check requests status
        log.trace("POST got a reply: %s", ret)

        body = json.loads(ret.get('body'))
        if body.get('kind') == 'Status' and body.get('status') == 'Failure':
            raise Exception(body)
        return body

    def put(self, path, data):
        ''' put any object in kubernetes based on URL '''
        auth = copy.copy(self.auth)

        # Prepare headers
        header = {"Content-Type": "application/json"}
        auth['header_dict'] = dictmerge(header, auth.get('header_dict', {}))
        # Make request
        try:
            ret = http.query(self.url(path), method='PUT', data=json.dumps(data), **auth)
        except Exception as exp:
            log.error("Can't make request due to error: %s", exp)
            raise exp

        # Check requests status
        log.trace("PUT got a reply: %s", ret)

        body = json.loads(ret.get('body'))
        if body.get('kind') == 'Status' and body.get('status') == 'Failure':
            raise Exception(body)
        return body

    def patch(self, path, data, patch_mode="json"):
        ''' patch any object in kubernetes based on URL '''

        auth = copy.copy(self.auth)
        log.trace("patch operations are %s", data)

        # Prepare headers
        # Prepare headers
        if patch_mode == "merge":
            # RFC7386
            header = {"Content-Type": "application/merge-patch+json"}
        elif patch_mode == "k8s":
            # Kubernetes custom implementation of merge-patch
            header = {"Content-Type": "application/strategic-merge-patch+json"}
        else:
            # RFC6902
            header = {"Content-Type": "application/json-patch+json"}

        auth['header_dict'] = dictmerge(header, auth.get('header_dict', {}))
        # Make request
        try:
            ret = http.query(self.url(path), method='PATCH', data=json.dumps(data), **auth)
        except Exception as exp:
            log.error("Can't make request due to error: %s", exp)
            raise exp

        body = json.loads(ret.get('body'))
        if body.get('kind') == 'Status' and body.get('status') == 'Failure':
            raise Exception(body)
        return body


def _get_filename(source, saltenv):
    """ get filename out from source definition which can be one of:
        salt://path, file:///path or even http://path
    """
    try:
        source_url = _urlparse(source)
    except TypeError:
        return '', {}, ('Invalid format for source parameter')

    protos = ('salt', 'http', 'https', 'ftp', 'swift', 's3', 'file')

    log.trace("parsed source looks like: %s", source_url)  # pylint: disable=no-member
    if not source_url.scheme or source_url.scheme == 'file':
        # just a regular file
        filename = os.path.abspath(source_url.path)
        log.debug("Source is a regular local file: %s", source_url.path)
    else:
        if source_url.scheme in protos:
            # The source is a file on a server
            filename = __salt__['cp.cache_file'](source, saltenv)
            if not filename:
                log.warn("Source file: %s can not be retrieved", source)
                return ""
    return filename


def label_folder_absent(kind, namespace="", name="", var="", kubeconfig="", context_name="", k8s=None):
    '''
    .. versionadded:: 2016.3.0

    Delete label folder to the current node

    CLI Example:

    .. code-block:: bash

        salt '*' k8s.label_folder_absent hw
        salt '*' k8s.label_folder_absent hw/ kube-node.cluster.local http://kube-master.cluster.local

    '''
    folder = var.strip("/") + "/"
    ret = {'name': folder, 'result': True, 'comment': '', 'changes': {}}

    if not k8s:
        with Kubernetes(kubeconfig, context_name) as k8s:
            return label_folder_absent(kind=kind, namespace=namespace,
                                       name=name, var=var,
                                       kubeconfig=kubeconfig,
                                       context_name=context_name, k8s=k8s)
    old_labels = get(kind, namespace, name, k8s=k8s, labels_only=True)
    if not isinstance(old_labels, dict):
        ret["result"] = False
        ret["comment"] = old_labels
        return ret

    # Prepare a temp labels dict
    for key in old_labels.keys():
        if key.startswith(folder):
            label(kind, namespace, name, var=key, k8s=k8s)
    return ret


def get(kind, namespace="", name="", kubeconfig="", context_name="", k8s=None,
        names_only=False, labels_only=False, label_selector={}, field_selector={}):
    """
    Get k8s kind

    CLI Example:

    .. code-block:: bash

        salt '*' k8s.get [object_type] [namespace=default] [obj_name] [apiserver_url] [names_only=False}


    Object type can be one of the:
        nodes
        secrets
        pods
        replicationcontrollers
        services
        serviceaccounts
        limitranges
        podtemplates
        proxy
        persistentvolumeclaims
        resourcequotas

    Examples:

    .. code-block:: bash

        salt '*' k8s.get namespaces
        salt '*' k8s.get secrets namespace_name secret_name http://kube-master.cluster.local
        salt '*' k8s.get pods namespace_name pod_name http://kube-master.cluster.local
        salt '*' k8s.get rc namespace_name rc_name

    """
    data = {}
    if label_selector:
        data['labelSelector'] = _prepare_selector(label_selector)
    if field_selector:
        data['fieldSelector'] = _prepare_selector(field_selector)
    log.debug("label selector is [%s], field selector is [%s]", data.get('labelSelector'), data.get('fieldSelector'))
    # Make request
    if not data:
        data = None

    if not k8s:
        with Kubernetes(kubeconfig, context_name) as k8s:
            return get(kind=kind, namespace=namespace, name=name,
                       kubeconfig=kubeconfig, context_name=context_name, k8s=k8s,
                       names_only=names_only, label_selector=label_selector,
                       field_selector=field_selector)
    else:
        url = k8s.get_path(kind, namespace, name)
        try:
            ret = k8s.get(url, data)
        except LookupError:
            ret = {}
        except Exception as exp:
            log.error("get was not successful due to: %s", exp)
            ret = {}

    if names_only:
        return k8s.get_names(ret)
    elif labels_only and 'items' not in ret:
        return k8s.get_labels(ret)
    else:
        return ret


def delete(kind="", namespace="", name="", kubeconfig="", context_name="",
           cascade=False, grace_period=0, k8s=None):
    """
    Delete k8s object

    CLI Example:

    .. code-block:: bash

        salt '*' k8s.delete [object_type] [namespace=default] [obj_name] [apiserver_url]


    Object type can be one of the:
        secrets
        pods
        replicationcontrollers
        services
        serviceaccounts
        limitranges
        podtemplates
        proxy
        persistentvolumeclaims
        resourcequotas

    Examples:

    .. code-block:: bash

        salt '*' k8s.delete namespace
        salt '*' k8s.delete secrets namespace_name secret_name http://kube-master.cluster.local
        salt '*' k8s.delete pods namespace_name pod_name http://kube-master.cluster.local
        salt '*' k8s.delete rc namespace_name rc_name

    """
    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}

    if not namespace:
        return {'name': namespace, 'result': False, 'comment': 'No namespace defined', 'changes': {}}

    # we don't want to copy/paste logic for k8s object available and not, but we
    # do need destructor to be called after the Kubernetes class exists so we
    # use recursion here :(
    if not k8s:
        with Kubernetes(kubeconfig, context_name) as k8s:
            return delete(kind=kind, namespace=namespace, name=name, cascade=cascade, grace_period=grace_period, k8s=k8s)
    else:
        kind = k8s.kind(kind)
        url = k8s.get_path(kind, namespace, name)
        if kind == 'replicationcontrollers' and cascade:
            annotate("rc", namespace, name, "salt/next-action", int(time.time() + 60))
            scale(kind, namespace, name, 0, k8s=k8s)
            rc = get('rc', namespace, name, k8s=k8s)
            selector = traverse_dict(rc, "spec:selector", {"fakeselector": "+1"})
            while get("pods", namespace, names_only=True, label_selector=selector, k8s=k8s):
                time.sleep(3)

        request_body = {
            "kind": "DeleteOptions",
            "apiVersion": "v1",
            "gracePeriodSeconds": grace_period
        }
        # Make request
        try:
            if grace_period:
                k8s.delete(url, request_body)
            else:
                k8s.delete(url)
            ret['comment'] = "Removed {0} {1} in {2} namespace".format(kind, name, namespace)
            ret['changes'][' '.join([kind, name])] = '{0} {1} removed'.format(kind, name)
        except Exception as e:
            ret['comment'] = "Could not remove due to error: {0}".format(e)
            ret['result'] = False
    return ret


# Namespaces
def create_namespace(name, kubeconfig="", context_name="", k8s=None):
    '''
    .. versionadded:: 2016.3.0

    Create kubernetes namespace from the name, similar to the functionality added to kubectl since v.1.2.0:
    .. code-block:: bash

        kubectl create namespaces namespace-name

    CLI Example:

    .. code-block:: bash

        salt '*' k8s.create_namespace namespace_name

        salt '*' k8s.create_namespace namespace_name kubeconfig context_name

    '''
    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}
    # Prepare data
    data = {
        "kind": "Namespace",
        "apiVersion": "v1",
        "metadata": {
            "name": name,
        }
    }
    log.trace("namespace creation requests: %s", data)  # pylint: disable=no-member
    # Make request
    if not k8s:
        with Kubernetes(kubeconfig, context_name) as k8s:
            return create_namespace(name=name, k8s=k8s)
    try:
        k8s.get(k8s.get_path('namespaces', name))
        log.debug("Namespace %s is already present", name)
        ret['comment'] = "Namespace {0} is already present".format(name)
    except LookupError:
        try:
            k8s.post(k8s.get_path('namespaces'), data)
            log.info("Successfully created namespace %s", name)
            ret['changes'][name] = "namespace created"
        except Exception as exp:
            log.error("Could not create namespace due to error [%s]", exp)
            ret['result'] = False
            ret['comment'] = "Could not create namespace due to error [{0}]".format(exp)
    return ret


# Secrets
def _update_secret(namespace, name, data, k8s):
    '''Replace secrets data by a new one'''
    # Prepare URL
    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}

    # Prepare data
    data = [{"op": "replace", "path": "/data", "value": data}]
    # Make request
    try:
        url = k8s.get_path("secrets", namespace, name)
        k8s.patch(url, data)
        ret['changes'][name] = 'updated'
        log.info('secret %s is updated on %s namespace', name, namespace)
    except Exception as exp:
        ret['result'] = False
        ret['comment'] = str(exp)
        log.error('secret %s could not be updated on %s namespace due to: [%s]', name, namespace, exp)
    return ret


def _create_secret(namespace, name, data, k8s):
    ''' create namespace on the defined k8s cluster '''
    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}
    # Prepare URL
    url = k8s.get_path('secrets', namespace)
    # Prepare data
    request = {
        "apiVersion": "v1",
        "kind": "Secret",
        "metadata": {
            "name": name,
            "namespace": namespace,
        },
        "data": data
    }
    # Make request
    try:
        k8s.post(url, request)
        ret['changes'][name] = 'created'
        log.info('secret %s created on %s namespace', name, namespace)
    except Exception as exp:
        ret['result'] = False
        ret['comment'] = str(exp)
        log.error('secret %s could not be created on %s namespace due to: [%s]', name, namespace, exp)
    return ret


def _is_valid_secret_file(filename):
    """ checks that secret file is actually a file and it is exists """
    if os.path.exists(filename) and os.path.isfile(filename):
        log.debug("File: %s is valid secret file", filename)
        return True
    log.warn("File: %s does not exists or not file", filename)
    return False


def _file_encode(filename):
    """ encode file into base64 format """
    log.trace("Encoding secret file: %s", filename)  # pylint: disable=no-member
    with open(filename, "rb") as fd:
        data = fd.read()
        return base64.b64encode(data)


def decode_secrets(namespace, name="", kubeconfig="", context_name="", k8s=None):
    '''
    Get k8s secret with already decoded data

    CLI Example:

    .. code-block:: bash

        salt '*' k8s.decode_secrets namespace_name
        salt '*' k8s.decode_secrets namespace_name secret_name http://kube-master.cluster.local

    '''

    if not k8s:
        with Kubernetes(kubeconfig, context_name) as k8s:
            return decode_secrets(namespace=namespace, name=name,
                                  kubeconfig=kubeconfig,
                                  context_name=context_name, k8s=k8s)

    secrets = get("secrets", namespace, name=name, k8s=k8s)

    items = secrets.get("items", [])
    if items:
        for i, secret in enumerate(items):
            log.trace(i, secret)  # pylint: disable=no-member
            for k, v in secret.get("data", {}).iteritems():
                items[i]['data'][k] = base64.b64decode(v)
        secrets["items"] = items
        return secrets
    else:
        for k, v in secrets.get("data", {}).iteritems():
            secrets['data'][k] = base64.b64decode(v)
        return secrets


def _source_encode(source, saltenv):
    """ encode files with base64 to use it inside secrets """
    try:
        source_url = _urlparse(source)
    except TypeError:
        return '', {}, ('Invalid format for source parameter')

    protos = ('salt', 'http', 'https', 'ftp', 'swift', 's3', 'file')

    log.trace("parsed source looks like: %s", source_url)  # pylint: disable=no-member
    if not source_url.scheme or source_url.scheme == 'file':
        # just a regular file
        filename = os.path.abspath(source_url.path)
        sname = os.path.basename(filename)
        log.debug("Source is a regular local file: %s", source_url.path)
        if Kubernetes.is_dns_subdomain(sname) and _is_valid_secret_file(filename):
            return sname, _file_encode(filename)
        else:
            log.error("Data name %s is not valid for secret, it must be dns subdomain", sname)
    else:
        if source_url.scheme in protos:
            # The source is a file on a server
            filename = __salt__['cp.cache_file'](source, saltenv)
            if not filename:
                log.warn("Source file: %s can not be retrieved", source)
                return "", ""
            return os.path.basename(filename), _file_encode(filename)
    return "", ""


def _get_secrets_data(sources, saltenv='base', force=True):
    data = {}
    for source in sources:
        log.debug("source is: %s", source)
        if isinstance(source, dict):
            # format is array of dictionaries:
            # [{public_auth: salt://public_key}, {test: "/tmp/test"}]
            log.trace("source is dictionary: %s", source)  # pylint: disable=no-member
            for k, v in source.iteritems():
                sname, encoded = _source_encode(v, saltenv)
                if not encoded:
                    log.warning("Source file %s is missing or name is incorrect", v)
                    if not force:
                        raise "Source file {0} is missing or name is incorrect".format(v)
                data[k] = encoded
        elif isinstance(source, six.string_types):
            # expected format is array of filenames
            sname, encoded = _source_encode(source, saltenv)
            if not encoded:
                log.warning("Source file %s is missing or name is incorrect", v)
                if not force:
                    raise "Source file {0} is missing or name is incorrect".format(v)
            data[sname] = encoded
    return data


def create_secret(namespace, name, sources, kubeconfig="", context_name="", force=False, update=False, do_not_create=False, saltenv='base', k8s=None):
    '''
    .. versionadded:: 2016.3.0

    Create k8s secrets in the defined namespace from the list of files

    CLI Example:

    .. code-block:: bash

        salt '*' k8s.create_secret namespace_name secret_name sources

        salt '*' k8s.create_secret namespace_name secret_name sources
        http://kube-master.cluster.local

    sources are either array of dictionary pairs [{name: path}, {name1: path}] or array of strings defining paths.

    Example of paths array:

    .. code-block:: bash

    ['/full/path/filename', "salt://secret/storage/file.txt", "http://user:password@securesite.com/secret-file.json"]

    Example of dictionaries:

    .. code-block:: bash

    [{"nameit": '/full/path/fiename'}, {name2: "salt://secret/storage/file.txt"}]

    it also accepts mixed format such as array of dictionaries and strings

    optional parameters accepted:

    update=[false] default value is false
    if set to false, and secret is already present on the cluster - warning will
    be returned no changes to the secret will be done.
    In case it is set to "true" and secret is present but data is differ - secret will be updated.

    force=[true] default value is true
    if the to False, secret will not be created in case one of the files is not
    valid kubernetes secret. e.g. capital letters in secret name or _
    in case force is set to True, wrong files will be skipped but secret will be created any way.

    saltenv=['base'] default value is base
    in case 'salt://' path is used, this parameter can change the visibility of files

    '''
    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}

    if not sources:
        ret['result'] = False
        ret['comment'] = 'No source available'
        return ret

    if not k8s:
        with Kubernetes(kubeconfig, context_name) as k8s:
            return create_secret(namespace=namespace, name=name,
                                 sources=sources, kubeconfig=kubeconfig,
                                 context_name=context_name, force=force, update=update,
                                 do_not_create=do_not_create, saltenv=saltenv, k8s=k8s)
    if force:
        create_namespace(name=namespace, k8s=k8s)

    log.info("creating secret %s out of %s", name, sources)
    # we need namespace to create secret in it

    try:
        secret = get("secrets", namespace, name, k8s=k8s)
    except LookupError as exp:
        secret = {}
    if secret and not update:
        log.info("Secret %s is already present on %s", name, namespace)
        return {'name': name, 'result': True,
                'comment': 'Secret {0} is already present'.format(name),
                'changes': {}}

    try:
        data = _get_secrets_data(sources, saltenv, force)
    except Exception as exp:
        ret['result'] = False
        ret['comment'] = str(exp)
        return ret

    log.trace("secret data is: %s", data)  # pylint: disable=no-member

    if update and do_not_create and not secret:
        log.info("I've instructed to don't create new secrets, but %s "
                 "doesn't exists yet on namespace %s", name, namespace)
        ret['result'] = False
        ret['comment'] = "I've instructed to don't create new secrets, but {0} doesn't exists yet on namespace {1}".format(name, namespace)
    elif secret and data != secret.get('data', "") and update:
        log.info("updating secret %s", name)
        ret = _update_secret(namespace=namespace, name=name, data=data, k8s=k8s)
    elif not secret:
        log.info("creating secret %s", name)
        ret = _create_secret(namespace=namespace, name=name, data=data, k8s=k8s)
    return ret


# LimitRange
# https://github.com/kubernetes/kubernetes/blob/release-1.2/docs/design/admission_control_limit_range.md
def _normalize_limits(limits):
    """ k8s wants us to omit values if they are empty
     that is why I have to check each of them and create if needed"""
    normalized_limits = []
    limit_categories = ['type', 'min', 'max', 'default', 'defaultRequest', 'maxLimitRequestRatio']

    if isinstance(limits, (tuple, list)):
        for i in limits:
            normalized = {}
            for j in [j for j in limit_categories if j in i.keys()]:
                if j == 'type' and i.get("type") in ["Container", "Pod"]:
                    normalized["type"] = i.get("type")
                    continue
                for k, v in i.get(j).iteritems():
                    if k in ["cpu", "memory"]:
                        normalized.setdefault(j, {})[k] = str(v)
            normalized_limits.append(normalized)

    return normalized_limits


def _get_limit_changes(limit_obj, configured_limits):
    """
    get limit object from kubernetes and normalized limits from the create_limit_range compare them,
    if there is a change - generate "patch" operation to replace limits with the normalized values
    """
    log.trace("Cluster limit object is: %s", limit_obj)
    log.trace("Configured limit object is: %s", configured_limits)
    limits = limit_obj.get("spec", {})
    diff = dictdiffer.DictDiffer({"limits": configured_limits}, limits)
    if diff.added() or diff.changed() or diff.removed():
        return [{"op": "replace", "path": "/spec/limits", "value":
                 configured_limits}]
    else:
        return None


def create_limit_range(namespace, limits, name="limits", kubeconfig="",
                       context_name="", force=True, update=True, k8s=None):
    """
    .. versionadded:: 2016.3.0

    Manages limit ranges for kubernetes namespace. Requires LimitRanger admission controller to work.

    Validation:

    Min (if specified) <= DefaultRequest (if specified) <= Default (if specified) <= Max (if specified)

    Kubernetes expects following request:
    .. code-block:: bash

       apiVersion: "v1"
       kind: "LimitRange"
       metadata:
         name: "limits"
         namespace: default
       spec:
         limits:
           - type: "Container"
             defaultRequests:
               cpu: "100m"

    limits is a array of dictionaries
    [{"type": "Container", "defaultRequests": {"cpu": "100m", "memory": "250Mi"}}}]

    accepted type values are "Container" and "Pod"

    accepted constraint values are:

    min - minimum requested value of the type
    max - maximum
    default - default limit
    defaultRequest - default requests
    maxLimitRequestRatio - ratio between requests and limit possible

    There are 2 possible limits you can set: "cpu" and "memory"

    """
    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}

    if not k8s:
        with Kubernetes(kubeconfig, context_name) as k8s:
            return create_limit_range(namespace, limits, name=name,
                                      kubeconfig=kubeconfig,
                                      context_name=context_name, force=force,
                                      update=update, k8s=k8s)

    normalized_limits = _normalize_limits(limits)
    if not normalized_limits:
        return {'name': name, 'result': False, 'comment': 'Limits format is not recognized', 'changes': {}}

    try:
        limit_range = k8s.get(k8s.get_path("limits", namespace, name))
        log.info("limit range %s is available on %s namespace", name, namespace)
        if not update:
            log.info("I was instructed to don't update %s limit range on namespace %s", name, namespace)
            return {'name': name, 'result': False, 'comment': 'Limit is already present', 'changes': {}}
        changes = _get_limit_changes(limit_range, normalized_limits)
        if changes:
            try:
                k8s.patch(k8s.get_path("limitranges", namespace), changes)
                log.info("limit range %s updated, changes are [%s]", name, changes)
                ret['comment'] = "Limits updated"
                ret['changes'][name] = normalized_limits
            except Exception as exp:
                log.error("can't update limit range %s due to error %s", name, exp)
                ret['comment'] = str(exp)
                ret['result'] = False
    except LookupError:
        request = {
            "apiVersion": "v1",
            "kind": "LimitRange",
            "metadata": {
                "name": name,
                "namespace": namespace
            },
            "spec": {
                "limits": normalized_limits
            }
        }

        log.trace("limit range create requests: %s", request)  # pylint: disable=no-member
        try:
            k8s.post(k8s.get_path("limitranges", namespace), request)
            log.info("created limit range %s on namespace %s", name, namespace)
            ret['comment'] = "Limits created"
            ret['changes'][name] = normalized_limits
        except Exception as exp:
            log.error("could not create limit range %s due to %s", name, exp)
            ret['comment'] = "Could not create limits: {0}".format(str(exp))
            ret['result'] = False
    return ret


# Resource quotas
# https://github.com/kubernetes/kubernetes/blob/release-1.2/docs/design/admission_control_resource_quota.md
def _get_quota_changes(quota, normalized):
    """ get PATCH string out from quota object and defined normalized value """
    quotas = quota.get("spec", {}).get("hard", {})
    diff = dictdiffer.DictDiffer(normalized, quotas)
    if diff.changed() or diff.added() or diff.removed():
        return [{"op": "replace", "path": "/spec/hard", "value": normalized}]
    else:
        return None


def _normalize_quotas(quota):
    """ k8s wants us to omit values if they are empty
    that is why I have to check each of them and create if defined but omit if
    they are empy """
    normalized = {}

    valid_quotas = ["cpu", "memory", "persistentvolumeclaims", "pods",
                    "replicationcontrollers", "resourcequotas", "secrets",
                    "services"]

    if isinstance(quota, dict):
        for i in [i for i in valid_quotas if i in quota]:
            normalized[i] = str(quota.get(i))
    elif isinstance(quota, (tuple, list)):
        for i in quota:
            k, v = i.items()[0]
            if k in valid_quotas:
                normalized[k] = str(v)
    return normalized


def create_resource_quota(namespace, quota, name="quota", update=True,
                          force=True, kubeconfig="", context_name="", k8s=None):

    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}

    if not k8s:
        with Kubernetes(kubeconfig, context_name) as k8s:
            return create_resource_quota(namespace, quota, name=name,
                                         update=update, force=force,
                                         kubeconfig=kubeconfig,
                                         context_name=context_name, k8s=k8s)

    # we need namespace to create quotas
    if force:
        create_namespace(namespace, k8s=k8s)

    normalized = _normalize_quotas(quota)
    if not normalized:
        log.error("could not understand your quotas definition for %s", name)
        return {'name': name, 'result': False,
                'comment': "Could not understand your quota's definition", 'changes': {}}

    try:
        quota = k8s.get(k8s.get_path("quotas", namespace, name))
        if not update:
            log.info("Resource Quota %s is already exists on %s namespace", name, namespace)
            return {'name': name, 'result': False, 'comment': 'Quota is already present', 'changes': {}}
        else:
            changes = _get_quota_changes(quota, normalized)
            if changes:
                k8s.patch(k8s.get_path("quotas", namespace, name), changes)
                ret['changes'][name] = changes
                ret['comment'] = 'Quota is updated'
                log.info("updated quota %s", name)
    except LookupError:
        # create new one
        request = {
            "apiVersion": "v1",
            "kind": "ResourceQuota",
            "metadata": {
                "name": name,
                "namespace": namespace
            },
            "spec": {
                "hard": normalized
            }
        }

        try:
            k8s.post(k8s.get_path("quotas", namespace), request)
            ret['comment'] = "Quotas are created"
            ret['changes'][name] = "quotas are created"
            log.info("created quota %s", name)
        except Exception as exp:
            ret['comment'] = "Could cont create quotas due to {0}".format(exp)
            ret['result'] = False
            log.error("could not create quota %s", exp)
    except Exception as exp:
        ret["result"] = False
        ret['comment'] = str(exp)
        log.error("could not create quota %s", exp)
    return ret


# Label
def label(kind, namespace="", name="", var="", val=None, kubeconfig="", context_name="", k8s=None):
    """
    .. versionadded:: 2016.3.0

    Manage labels of the kubernetes objects such as:
        secrets
        pods
        replicationcontrollers
        services
        serviceaccounts
        limitranges
        podtemplates
        proxy
        persistentvolumeclaims
        resourcequotas

    Format:
    .. code-block:: bash

       k8s.label kubernetes_object namespace obj_name label_name [label_value]

    Example:
    .. code-block:: bash

       salt '*' k8s.label service default kubernetes test123 12345

    Following example will set label test123 to value 12345 for the service
    inside default namespace.

    """
    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}

    if not k8s:
        with Kubernetes(kubeconfig, context_name) as k8s:
            return label(kind, namespace=namespace, name=name, var=var, val=val, k8s=k8s)

    url = k8s.get_path(kind, namespace, name)
    try:
        kind_item = k8s.get(url)
    except LookupError:
        ret['result'] = False
        ret['comment'] = 'Could not find {0} {1} at namespace {2}'.format(kind, name, namespace)
        return ret

    label_value = k8s.get_labels(kind_item, var)

    log.debug('current value of label %s is %s', var, label_value)
    # value must be either string or null
    try:
        if val:
            val = str(val)
        else:
            val = None
    except Exception:
        val = None

    if val and val == label_value:
        log.info("label %s is set properly", var)
        ret["comment"] = "Label is set properly already"
        return ret
    elif not label_value and not val:
        log.info("label %s is removed already", var)
        ret["comment"] = "You already removed this label"
        return ret

    data = {
        "metadata": {
            "labels": {
                str(var): val
            }
        }
    }

    try:
        k8s.patch(url, data, patch_mode="k8s")
        if val:
            log.info("set value %s to label name %s", val, var)
            ret["comment"] = "set label {0} with value {1}".format(var, val)
            ret["changes"]["label {0}".format(var)] = val
        else:
            log.info("removed label %s", var)
            ret["comment"] = "removed label {0}".format(var)
            ret["changes"]["label {0}".format(var)] = "removed"
    except Exception as exp:
        log.error("There is an error: [%s]", exp)
        ret['result'] = False
        ret['comment'] = exp
    return ret


# Annotate
def annotate(kind, namespace, name, var, val=None, kubeconfig="", context_name="", k8s=None):
    """
    .. versionadded:: 2016.3.0

    Manage annotations of the kubernetes objects such as:
        secrets
        pods
        replicationcontrollers
        services
        serviceaccounts
        limitranges
        podtemplates
        proxy
        persistentvolumeclaims
        resourcequotas

    Format:
    .. code-block:: bash

       k8s.annotate kubernetes_object namespace obj_name annotation_name [annotation_value]

    Example:
    .. code-block:: bash

       salt '*' k8s.annotate service default kubernetes test123 12345

    Following example will set annotation test123 to value 12345 for the service
    inside default namespace.

    """
    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}

    if not k8s:
        with Kubernetes(kubeconfig, context_name) as k8s:
            return annotate(kind=kind, namespace=namespace, name=name, var=var, val=val,
                            kubeconfig=kubeconfig, context_name=context_name, k8s=k8s)

    try:
        k8s_item = get(kind, namespace, name, k8s=k8s)
        annotation = _get_annotation(k8s_item, var)
        if val:
            val = str(val)
        if val != annotation:
            data = {
                "metadata": {
                    "annotations": {
                        str(var): val
                    }
                }
            }
            try:
                k8s.patch(k8s.get_path(kind, namespace, name), data, patch_mode="k8s")
                if val:
                    ret["comment"] = "annotated {0} with value {1}".format(var, val)
                    log.info("annotated %s with value", var, val)
                else:
                    ret["comment"] = "removed annotation {0}".format(var)
                    log.info("annotation %s removed", var)
                ret["changes"] = {str(var): val}
            except Exception as exp:
                log.error("annotation failed due to: %s", exp)
                ret['result'] = False
                ret['comment'] = str(exp)
    except LookupError:
        log.warning("could not find resource to annotate")
        ret["result"] = False
        ret["comment"] = "could not find resource to annotate"
    except Exception as exp:
        log.error("could annotate due to %s", exp)
        ret['result'] = False
        ret['comment'] = str(exp)

    return ret


def _get_annotation(obj_dict, annotation, default=None):
    """ get annotation value out from cluster object dictionary """
    if annotation:
        path = "metadata:annotations:{0}".format(annotation)
    else:
        path = "metadata:annotations"
    return traverse_dict(obj_dict, path, default)


def get_annotation(kind, namespace, name, annotation, kubeconfig="",
                   context_name="", k8s=None):
    """
    .. versionadded:: 2016.3.0

    Get annotations of the kubernetes objects such as:
        secrets
        pods
        replicationcontrollers
        services
        serviceaccounts
        limitranges
        podtemplates
        proxy
        persistentvolumeclaims
        resourcequotas

    Format:
    .. code-block:: bash

       k8s.get_annotation kubernetes_object namespace obj_name annotation_name

    Example:
    .. code-block:: bash

       salt '*' k8s.get_annotation service default kubernetes test123

    Following example will get annotation test123 for the service inside default namespace.

    """
    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}

    if not k8s:
        with Kubernetes(kubeconfig, context_name) as k8s:
            return get_annotation(kind=kind, namespace=namespace, name=name,
                                  annotation=annotation, kubeconfig=kubeconfig,
                                  context_name=context_name, k8s=k8s)

    try:
        k8s_item = k8s.get(k8s.get_path(kind, namespace, name))
        return _get_annotation(k8s_item, annotation, {})
    except LookupError:
        ret["result"] = False
        ret["comment"] = "could not find {0} {1} on {2} namespace".format(kind, name, namespace)
    except Exception as exp:
        log.error("get annotation failed due to %s", exp)
        ret["result"] = False
        ret["comment"] = str(exp)
    return ret


# Services
def _get_service_changes(service, manifest):
    """ get PATCH string out from service object and configured manifest """
    change_ops = []
    svc_spec = service.get("spec", {})
    m_spec = manifest.get("spec", {})
    svc_meta = service.get("metadata", {})
    m_meta = manifest.get("metadata", {})

    spec = dictdiffer.DictDiffer(m_spec, svc_spec)
    changes = spec.changed() | spec.added() | spec.removed()
    log.trace("service changes are: %s", changes)
    for change in changes:
        if change != "clusterIP" and m_spec.get(change):
            change_ops.append({"op": "replace",
                               "path": "/spec/{0}".format(change),
                               "value": m_spec.get(change)})

    # In case labels are changed - we must update them also
    meta = dictdiffer.DictDiffer(m_meta, svc_meta)
    meta_changes = meta.changed() | meta.added() | spec.removed()
    if 'labels' in meta_changes:
        change_ops.append({"op": "replace",
                           "path": "/metadata/labels/",
                           "value": m_meta.get("labels", {})})
    return change_ops


def _needs_recreation(service, manifest):
    """ check for read only fields, if they are changed """
    service = service.get("spec", {})
    manifest = manifest.get("spec", {})

    # clusterIP can't be changed during runtime, so we can't actually update it
    if "clusterIP" in manifest:
        diff = dictdiffer.DictDiffer(service, manifest)
        return 'clusterIP' in diff.changed()
    else:
        return False


def create_service(namespace, source, name="", labels=None, force=True,
                   update=False, saltenv='base', replace_name=True,
                   replace_namespace=True, kubeconfig="", context_name="", k8s=None):
    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}

    if not k8s:
        with Kubernetes(kubeconfig, context_name) as k8s:
            return create_service(namespace=namespace, source=source, name=name,
                                  labels=labels, force=force, update=update,
                                  saltenv=saltenv, replace_name=replace_name,
                                  replace_namespace=replace_namespace,
                                  kubeconfig=kubeconfig, context_name=context_name, k8s=k8s)

    if force:
        create_namespace(name=namespace, k8s=k8s)

    # we support either dictionary or filename in yaml or json format
    if isinstance(source, six.string_types):
        manifest = _get_filename(source, saltenv)
        data = k8s.load_manifest(manifest)
    elif isinstance(source, dict):
        data = source
    else:
        ret["result"] = False
        ret["comment"] = "Could not load manifest file"
        return ret

    if name and replace_name:
        data.setdefault("metadata", {})["name"] = name
    else:
        name = data.get("metadata", {}).get("name")

    if replace_namespace:
        data.setdefault("metadata", {})["namespace"] = namespace
    else:
        namespace = data.get("metadata", {}).get("namespace")

    url = k8s.get_path("services", namespace)
    try:
        service = k8s.get(k8s.get_path("services", namespace, name))
        if not update:
            ret["result"] = False
            ret["comment"] = "Service {0} already exists, not instructed to update".format(name)
            log.info("Service %s is already exists, not going to update", name)
        else:
            if _needs_recreation(service, data) and force:
                try:
                    k8s.delete(k8s.get_path("services", namespace, name))
                    data = _set_data_hash(data)
                    k8s.post(url, data)
                    log.info("recreated service %s on namespace %s", name, namespace)
                    ret['changes'][name] = "recreated"
                except Exception as exp:
                    ret['result'] = False
                    ret['comment'] = str(exp)
                return ret

            data_hash = _gen_data_hash(data)
            service_hash = _get_annotation(service, HASH_ANNOTATION)

            if not service_hash:
                annotate("services", namespace, name, HASH_ANNOTATION, data_hash)
                ret["chages"] = "prepared for salt management"
            elif data_hash != service_hash:
                changes = _get_service_changes(service, data)
                try:
                    k8s.patch(k8s.get_path("services", namespace, name), changes)
                    ret['changes'] = changes
                    ret['comment'] = "Service is updated"
                    annotate("svc", namespace, name, HASH_ANNOTATION, data_hash)
                except Exception as exp:
                    ret['comment'] = "Could not update service due to {0}".format(str(exp))
                    ret['result'] = False
    except LookupError:
        # new service creation
        data = _set_data_hash(data)
        try:
            k8s.post(url, data)
            ret['comment'] = "Service is created"
            ret['changes'][name] = 'created'
        except Exception as exp:
            ret['comment'] = "Could not create service due to error {0}".format(str(exp))
            ret['result'] = False
    except Exception as exp:
        ret['result'] = False
        ret['comment'] = str(exp)

    return ret


# Replication Controllers
def _get_replicas(rc):
    " get replicas out from replication controller"
    return int(traverse_dict(rc, "spec:replicas", 0))


def _needs_scaling(rc, data):
    " checks that replication controller needs scaling "
    old_replicas = _get_replicas(rc)
    new_replicas = _get_replicas(data)

    next_action_time = _get_annotation(rc, "salt/next-action", 0)
    if float(next_action_time) > time.time():
        return False

    if _get_annotation(rc, "kubernetes.io/update-partner"):
        return False
    return old_replicas != new_replicas


def scale(kind, namespace, name, replicas, kubeconfig="", context_name="", k8s=None):
    """
    .. versionadded:: 2016.3.0

    scale replication controller to the replicas value
    Format:
    .. code-block:: bash

       k8s.scale namespace rc_name replicas [apiserver_url]

    Example:
    .. code-block:: bash

       salt '*' k8s.scale kube-system kube-dns 2

    Following example will scale kube-dns replication controller on kube-system
    names to 2 replicas.

    """
    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}

    if not k8s:
        with Kubernetes(kubeconfig, context_name) as k8s:
            return scale(kind=kind, namespace=namespace, name=name, replicas=replicas,
                         kubeconfig=kubeconfig, context_name=context_name, k8s=k8s)
    data = {
        "spec": {"replicas": replicas}
    }
    try:
        url = k8s.get_path(kind, namespace, name, api=k8s.guess_api_version(kind))
        item = k8s.get(url)
        if _get_replicas(item) != replicas:
            k8s.patch(url, data, patch_mode="k8s")
            ret["changes"] = {"kind": kind, "replicas": replicas}
            log.info("scaled %s %s on %s namespace to %s", kind, name, namespace, replicas)
    except LookupError:
        ret["result"] = False
        ret["comment"] = "could not find {0} {1} on {2} namespace to scale".format(kind, name, namespace)
        log.warning("could not find %s %s on %s namespace to scale", kind, name, namespace)
    except Exception as exp:
        ret["result"] = False
        ret["comment"] = str(exp)
        log.error("%s", exp)
    return ret


def _set_zero_replicas(rc, replicas):
    " set initial replicas count to 0, but annotate desired replicas "
    log.trace("replicas set to %s", replicas)

    data = {
        "metadata": {
            "annotations": {
                "kubernetes.io/desired-replicas": str(replicas)
            }
        },
        "spec": {
            "replicas": 0
        }
    }

    return dictupdate(rc, data)


def _gen_data_hash(data):
    " generate hash out of replication controller data "
    tmp = copy.deepcopy(data)
    # prevent rolling-update for scaling requests
    tmp.get("spec", {}).pop("replicas", None)
    return hashlib.sha1(json.dumps(tmp, sort_keys=True)).hexdigest()


def _set_data_hash(rc, data_hash=None):
    " set data hash of the replication controller "
    if _get_annotation(rc, HASH_ANNOTATION):
        return rc

    if not data_hash:
        data_hash = _gen_data_hash(rc)

    data = {
        "metadata": {
            "annotations": {
                HASH_ANNOTATION: data_hash
            }
        }
    }

    return dictupdate(rc, data)


def _set_deployment_label(rc, rc_hash):
    data = {
        "spec": {
            "template": {
                "metadata": {
                    "labels": {
                        "kubernetes.io/deployment": str(rc_hash)
                    }
                }
            },
            "selector": {
                "kubernetes.io/deployment": str(rc_hash)
            }
        }
    }

    return dictupdate(rc, data)


def _set_rc_selector(namespace, name, old_hash, k8s):

    rc = get("rc", namespace, name, k8s=k8s)
    if traverse_dict(rc, "spec:selector:kubernetes.io/deployment", "") != str(old_hash) \
       or traverse_dict(rc, "spec:template:metadata:labels:kubernetes.io/deployment", "") != str(old_hash):
        data = {
            "spec": {
                "template": {
                    "metadata": {
                        "labels": {
                            "kubernetes.io/deployment": str(old_hash)
                        }
                    }
                },
                "selector": {
                    "kubernetes.io/deployment": str(old_hash)
                }
            }
        }

        return k8s.patch(k8s.get_path('replicationcontrollers', namespace, name), data, patch_mode="k8s")
    return True


def _rollout(namespace, old_rc, next_rc, k8s, batch=1):
    """ increase replicas for next and decrease old by batch value """
    old_name = k8s.get_names(old_rc)[0]
    next_name = k8s.get_names(next_rc)[0]

    desired_replicas = int(_get_annotation(next_rc,
                                           "kubernetes.io/desired-replicas",
                                           traverse_dict(old_rc, "spec:replicas", 0)))

    next_replicas = int(traverse_dict(next_rc, "spec:replicas", 0))
    old_replicas = int(traverse_dict(old_rc, "spec:replicas", 0))

    # prevent race conditions
    next_action_time = _get_annotation(old_rc, "salt/next-action", time.time())
    if float(next_action_time) > time.time():
        return False

    if old_replicas - batch <= 0:
        old_final = 0
    else:
        old_final = old_replicas - batch
    scale("replicationcontrollers", namespace, old_name, old_final, k8s=k8s)
    log.info("scaling %s to %s replicas", old_name, old_final)

    if desired_replicas > next_replicas:
        next_final = next_replicas + batch
    elif desired_replicas < next_replicas:
        if next_replicas - batch <= 0:
            next_final = 0
        else:
            next_final = next_replicas - batch
    else:
        next_final = desired_replicas
    log.info("scaling %s to %s replicas", next_name, next_final)
    scale("replicationcontrollers", namespace, next_name, next_final, k8s=k8s)

    return old_final, next_final


def _get_original_rc_data(next_rc):
    metadata = next_rc.get("metadata", {})
    spec = next_rc.get("spec", {})

    metadata.get("annotations", {}).pop("kubernetes.io/desired-replicas", None)
    metadata.get("annotations", {}).pop("kubernetes.io/deployment", None)
    metadata.get("labels", {}).pop("kubernetes.io/deployment", None)
    for i in ("selfLink", "resourceVersion", "uid", "creationTimestamp", "generation", ""):
        metadata.pop(i, None)

    spec.get("template", {}).get("metadata", {}).get("labels", {}).pop("kubernetes.io/deployment", None)
    spec.get("selector", {}).pop("kubernetes.io/deployment", None)
    next_rc['metadata'] = metadata
    next_rc['spec'] = spec
    next_rc.pop("status", None)

    return next_rc


def _prepare_selector(labels):
    return ','.join(["{0}={1}".format(k, v) for k, v in labels.iteritems()])


def rolling_update(namespace, name, source, kubeconfig="", context_name="",
                   one_change_only=True, saltenv="base", create_new=True,
                   update_period=0, poll_interval=3, batch=1, k8s=None):
    """ perform replication controller rolling update """
    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}

    if not k8s:
        with Kubernetes(kubeconfig, context_name) as k8s:
            return rolling_update(namespace=namespace, name=name, source=source,
                                  kubeconfig=kubeconfig,
                                  context_name=context_name,
                                  one_change_only=one_change_only,
                                  saltenv=saltenv, create_new=create_new,
                                  update_period=update_period,
                                  poll_interval=poll_interval, batch=batch,
                                  k8s=k8s)

    if isinstance(source, six.string_types):
        manifest = _get_filename(source, saltenv)
        data = k8s.load_manifest(manifest)
    elif isinstance(source, dict):
        data = source

    if not data:
        ret["result"] = False
        ret['comment'] = "data is empty, nothing to do"
        return ret

    # preparation
    full_data_hash = _gen_data_hash(data)
    log.debug("full data hash is: %s", full_data_hash)
    data_hash = hashlib.sha1(json.dumps(data.get("spec"), sort_keys=True)).hexdigest()[:16]
    log.debug("data hash is %s:", data_hash)

    try:
        old_rc = get('rc', namespace, name, k8s=k8s)
        log.debug("old replication controller %s is present", name)
    except LookupError:
        log.debug("old replication controller %s is not present", name)
        if create_new:
            data = _set_data_hash(data, full_data_hash)
            log.debug("creating new rc from rolling update")
            return create_rc(namespace, data, name, k8s=k8s)
        else:
            ret['comment'] = 'could not find replication controller {0}'.format(name)
            ret['result'] = False
            return ret
    except Exception as exp:
        ret['result'] = False
        ret['comment'] = "no rolling update possible: {0}".format(str(exp))
        log.error("no rolling update possible %s", exp)
        return ret

    next_name = traverse_dict(old_rc, "metadata:annotations:kubernetes.io/update-partner",
                              "{0}-{1}".format(name, data_hash))

    log.debug("next name defined is %s", next_name)
    try:
        log.debug("entered next_rc creation")
        next_rc = k8s.get(k8s.get_path('replicationcontrollers', namespace, next_name))
        if _get_annotation(old_rc, FORBIDDEN_ANNOTATION) == full_data_hash:
            _rollback(namespace, old_rc, k8s=k8s)
            return ret
        log.debug("it is not in FORBIDDEN")
        if _get_annotation(old_rc, HASH_ANNOTATION) == full_data_hash:
            # the same data present on old and new rc
            delete("rc", namespace, next_name, k8s=k8s)
            ret['comment'] = "rolling update is finished"
            return ret
        log.debug("it is no the same")
    except LookupError:
        log.debug("did not find %s", next_name)
        if _get_annotation(old_rc, FORBIDDEN_ANNOTATION) == full_data_hash:
            ret["result"] = False
            ret["comment"] = "We already tried this one, and it failed, remove annotation {0} to try again".format(FORBIDDEN_ANNOTATION)
            log.info("we tried to do rolling update for %s with hash %s but it"
                     "failed, please remove %s to try once again", name, full_data_hash, FORBIDDEN_ANNOTATION)
            return ret
        log.debug("No replication controller %s present, creating one", next_name)
        # create next rc and do rollout
        data = _set_zero_replicas(data, data.get("spec", {}).get("replicas"))
        data = _set_deployment_label(data, data_hash)
        data = _set_data_hash(data, full_data_hash)
        log.debug("creating new rc %s", next_name)
        create_rc(namespace, data, next_name, k8s=k8s, replace_name=True, update=False, force=False)
        next_rc = data
        # mark old rc with our name
        annotate('rc', namespace, name, "kubernetes.io/update-partner", next_name, k8s=k8s)
    except Exception as exp:
        log.debug("some exception")
        log.error("%s", exp)

    log.debug("doing actual rolling out for %s and %s", name, next_name)
    next_action_time = _get_annotation(old_rc, "salt/next-action", time.time())
    if float(next_action_time) > time.time():
        return {'name': name, 'result': True, 'changes': {},
                'comment': 'it is too early, wait for {0} seconds and try again'.format(int(next_action_time) - int(time.time()))}

    old_deploy_hash = traverse_dict(old_rc, "metadata:labels:kubernetes.io/deployment", None)
    old_selector_hash = traverse_dict(old_rc, "spec:selector:kubernetes.io/deployment", None)
    old_hash = hashlib.sha1(json.dumps(old_rc.get("spec"), sort_keys=True)).hexdigest()[:16]
    old_selector = traverse_dict(old_rc, "spec:selector", {})

    if not old_deploy_hash:
        # both replication controllers must have deployment labels
        # we just begin the rolling update
        log.debug("No deployment hash assigned to old RC")
        label('rc', namespace, name, "kubernetes.io/deployment", data_hash, k8s=k8s)

    if not old_selector_hash:
        # we must mark old pods with the new labels to fit selector of old rc
        log.info("Assigning deployment selector %s to pods from rc %s", old_hash, k8s.get_names(old_rc)[0])
        for pod in get("pods", namespace, label_selector=old_selector, k8s=k8s).get('items', []):
            log.debug("assigning label %s to kubernetes.io/deployment for pod %s", old_hash, k8s.get_names(pod)[0])
            # selector of old rc match (we own this pod)
            label("pods", namespace, k8s.get_names(pod)[0], "kubernetes.io/deployment", old_hash)

        # we must add some deployment key as a selector, which is different from
        # next's selector
        annotate("rc", namespace, name, "kubernetes.io/update-partner", next_name, k8s=k8s)
        _set_rc_selector(namespace, name, old_hash, k8s=k8s)

    log.debug("checking that we need a rollback")
    if _needs_rollback(namespace, next_rc, k8s=k8s):
        log.debug("we need a rollback")
        _rollback(namespace, old_rc, k8s=k8s)
        return ret
    else:
        log.debug("we doing a rollout")
        old_replicas, next_replicas = _rollout(namespace, old_rc, next_rc, k8s, batch)
        log.info("after manipulations %s has %s replicas, %s: %s", name, old_replicas, next_name, next_replicas)

    # update to prevent race condition
    if not update_period:
        update_period = calculate_safe_timeout(next_rc)
    timestamp = int(time.time()) + update_period
    log.info("set next action time to +%s seconds", update_period)
    annotate("rc", namespace, name, "salt/next-action", str(timestamp), k8s=k8s)

    # cleanup
    desired_replicas = int(_get_annotation(next_rc, "kubernetes.io/desired-replicas",
                                           traverse_dict(old_rc, "spec:replicas", 0)))

    # we want to wait for one more cycle before the removal
    next_replicas = int(traverse_dict(next_rc, "spec:replicas", 0))
    log.debug("desired replicas of next rc: %s", desired_replicas)
    if desired_replicas == next_replicas and old_replicas == 0:
        original_data = _get_original_rc_data(next_rc)
        log.debug("next rc data: %s", original_data)
        delete('rc', namespace, name, k8s=k8s)
        # cleanup
        res = create_rc(namespace, original_data, name, k8s=k8s)
        if res.get("result") is False:
            return res
        delete("rc", namespace, next_name, k8s=k8s)

    return ret


def create_rc(namespace, source, name="", labels={}, kubeconfig="",
              context_name="", force=True, update=False, saltenv='base', replace_name=True,
              replace_namespace=True, patch_labels=[], one_change_only=False, k8s=None):

    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}

    if not k8s:
        with Kubernetes(kubeconfig, context_name) as k8s:
            return create_rc(namespace=namespace, source=source, name=name,
                             labels=labels, kubeconfig=kubeconfig,
                             context_name=context_name, force=force,
                             update=update, saltenv=saltenv,
                             replace_name=replace_name,
                             replace_namespace=replace_namespace,
                             patch_labels=patch_labels,
                             one_change_only=one_change_only, k8s=k8s)

    if force:
        create_namespace(namespace, k8s=k8s)

    if isinstance(source, six.string_types):
        manifest = _get_filename(source, saltenv)
        data = k8s.load_manifest(manifest)
    elif isinstance(source, dict):
        data = source

    if not data:
        ret["result"] = False
        return ret

    if name and replace_name:
        data.setdefault("metadata", {})["name"] = name
    else:
        name = data.get("metadata", {}).get("name")

    if namespace and replace_namespace:
        data.setdefault("metadata")["namespace"] = namespace
    else:
        namespace = data.get("metadata", {}).get("namespace")

    log.trace("replication controller data is: %s", data)

    try:
        rc = k8s.get(k8s.get_path("replicationcontrollers", namespace, name))

        replicas = _get_replicas(data)
        if _needs_scaling(rc, data):
            return scale("replicationcontrollers", namespace, name, replicas, k8s=k8s)

        if not update:
            ret["comment"] = """Replication controller {0} already exists and I've been instructed not to update it""".format(name)
        else:
            data_hash = _gen_data_hash(data)
            rc_hash = _get_annotation(rc, HASH_ANNOTATION)

            if not rc_hash:
                # RC is was not managed by salt
                annotate("rc", namespace, name, HASH_ANNOTATION, data_hash, k8s=k8s)
                ret["comment"] = """prepared rc for management from salt"""
            elif rc_hash != data_hash:
                # rolling update required
                log.debug('rolling update of %s required', name)
                ret = rolling_update(namespace, name, data, one_change_only=one_change_only, k8s=k8s)
    except LookupError:
        # there is no such RC
        log.debug("replication controller %s not found, need to create one", name)
        data = _set_data_hash(data)
        try:
            k8s.post(k8s.get_path("replicationcontrollers", namespace), data)
            ret["changes"][name] = "created replication controller on namespace {0}".format(namespace)
            log.info("created replication controller %s on namespace %s", name, namespace)
        except Exception as exp:
            ret['result'] = False
            ret['comment'] = str(exp)
    except Exception as exp:
        ret['result'] = False
        ret['comment'] = str(exp)
    return ret


def _needs_rollback(namespace, next_rc, k8s):
    answer = False
    selector = traverse_dict(next_rc, "spec:selector", {})
    pods = {}
    if selector:
        try:
            pods = get("pods", namespace, label_selector=selector, k8s=k8s)
        except LookupError:
            pass
        except Exception as exp:
            log.error("%s", exp)
    for pod in pods.get("items", []):
        pod_name = k8s.get_names(pod)[0]
        pod_uid = traverse_dict(pod, "metadata:uid", "-12")
        field_selector = {
            "involvedObject.name": pod_name,
            "involvedObject.namespace": namespace,
            "involvedObject.uid": pod_uid
        }
        events = get("events", namespace, field_selector=field_selector, k8s=k8s)
        for event in events.get("items"):
            log.debug("cheking even for pod %s: %s", pod_name, events)
            if event.get("reason", "").lower() in ["failedsync", "backoff", "unhealthy"]:
                log.info("have to rollback due to pod %s with reason %s", pod_name, event.get("reason"))
                return True
    return answer


def _rollback(namespace, target, k8s, batch=1):
    """ perform rollback of failed rolling update """
    if isinstance(target, six.string_types):
        # it is just name
        old_rc = get('rc', namespace, target, k8s=k8s)
        name = target
    else:
        old_rc = target
        name = k8s.get_names(target)[0]

    partner = _get_annotation(old_rc, "kubernetes.io/update-partner")
    next_rc = get('rc', namespace, partner, k8s=k8s)
    desired_replicas = _get_annotation(next_rc, "kubernetes.io/desired-replicas")
    data_hash = _get_annotation(next_rc, HASH_ANNOTATION)

    # mark deployment as forbidden
    annotate("rc", namespace, name, FORBIDDEN_ANNOTATION, data_hash, k8s=k8s)
    annotate("rc", namespace, name, "kubernetes.io/desired-replicas", desired_replicas, k8s=k8s)

    next_replicas, old_replicas = _rollout(namespace, next_rc, old_rc, k8s, batch)
    if int(old_replicas) == int(desired_replicas) and int(next_replicas) == 0:
        delete("rc", namespace, partner, cascade=True, k8s=k8s)


def calculate_safe_timeout(resource):
    """ calculate timeout based on containers liveness and readiness
    probe information """
    containers = []
    if isinstance(resource, dict):
        # we have just rc
        containers = traverse_dict(resource, "spec:template:spec:containers", [])
    else:
        containers = resource

    timeouts = [60]  # minimum value is 60 seconds the same as kubectl value
    secure_margin = random.randint(5, 20)

    for container in containers:
        for probe_type in ("livenessProbe", "readinessProbe"):
            probe = container.get(probe_type)
            if probe:
                probe_timeout = (
                    int(probe.get("initialDelaySeconds", 0))
                    + int(probe.get("timeoutSeconds", 1)) * int(probe.get("failureThreshold", 1))
                    + int(probe.get("periodSeconds", "20")) * int(probe.get("failureThreshold", 1))
                )
                log.debug("calculated safe timeout based on probe %s data: %s", probe_type, probe_timeout)
                timeouts.append(probe_timeout)
    return max(timeouts) + secure_margin


def create(source, namespace="", kubeconfig="", context_name="", force=True,
           replace_namespace=True, update=True, saltenv='base', k8s=None):

    ret = {'name': "create", 'result': True, 'comment': '', 'changes': {}}

    if not k8s:
        with Kubernetes(kubeconfig, context_name) as k8s:
            return create(source=source, namespace=namespace, kubeconfig=kubeconfig, context_name=context_name,
                          force=force, replace_namespace=replace_namespace, update=update, saltenv=saltenv, k8s=k8s)

    log.debug("source is [%s], namespace is [%s] "
              "kubeconfig is [%s]", source, namespace, kubeconfig)
    if isinstance(source, six.string_types):
        log.info("manifest file is: %s", source)
        manifest = _get_filename(source, saltenv)
        mdata = k8s.load_manifest(manifest)
        log.debug("data is %s", mdata)
    elif isinstance(source, dict):
        mdata = source

    # we unify format to deal with array of dicts
    if isinstance(mdata, dict):
        mdata = [mdata]

    origin_namespace = namespace

    for data in mdata:
        log.trace("created data: %s", data)
        if not data:
            ret["result"] = False
            continue
        kind = data.get("kind", "").lower()
        api = data.get("apiVersion", "").lower()
        name = traverse_dict(data, "metadata:name", "")

        log.debug("kind: [%s], api: [%s], name: [%s]", kind, api, name)

        # in case of multiple manifests, we need to start over
        if origin_namespace != namespace:
            namespace = origin_namespace

        if namespace and replace_namespace:
            data = dictupdate(data, {"metadata": {"namespace": namespace}})
        elif traverse_dict(data, "metadata:namespace", None):
            namespace = traverse_dict(data, "metadata:namespace", "")
        else:
            namespace = "default"

        log.debug("after manipulations namespace is set to %s", namespace)

        kind = k8s.kind(kind)
        if kind == "replicationcontrollers":
            log.debug("got replication controller")
            ret = create_rc(namespace, data, update=update, force=force, replace_namespace=replace_namespace, k8s=k8s)
        elif kind == "services":
            log.debug("got service")
            ret = create_service(namespace, data, update=update, force=force, replace_namespace=replace_namespace, k8s=k8s)
        elif kind == "resourcequotas":
            log.debug("got resource quota")
            ret = create_resource_quota(namespace, data, update=update, force=force, k8s=k8s)
        elif kind == "limitranges":
            log.debug("got limits range")
            ret = create_limit_range(namespace, data, force=force, update=update, k8s=k8s)
        else:
            log.debug("using default create method for %s", kind)
            try:
                kobj = k8s.get(k8s.get_path(kind, namespace, name, api=api))
                log.info("%s %s is already existing on %s", kind, name, namespace)
                continue
            except LookupError:
                if force:
                    create_namespace(namespace, k8s=k8s)
                url = k8s.get_path(kind, namespace, api=api)
                try:
                    log.debug("creating resource %s with name %s", kind, name)
                    data = _set_data_hash(data)
                    k8s.post(url, data)
                    log.info("created resource %s with name %s", kind, name)
                    ret['changes']["{0} {1}".format(kind, name)] = "created"
                except Exception as exp:
                    log.error("could not create %s %s due to: %s", kind, name, exp)
                    ret['comment'] = str(exp)
                    ret['result'] = False
                    log.error(str(exp))
            except Exception as exp:
                log.error("could not create %s %s due to: %s", kind, name, exp)
                ret['comment'] = str(exp)
                ret['result'] = False
                log.error(str(exp))
    return ret


def drain(node, grace_period=None, kubeconfig="", context_name="", k8s=None):
    ret = {'name': "drain", 'result': True, 'comment': '', 'changes': {}}
    if not k8s:
        with Kubernetes(kubeconfig, context_name) as k8s:
            return drain(node=node, kubeconfig=kubeconfig, context_name=context_name, k8s=k8s)
    try:
        log.info("draining node %s", node)
        for pod in get("pods", field_selector={"spec.nodeName": node}, k8s=k8s).get('items'):
            namespace = traverse_dict(pod, "metadata:namespace", "default")
            name = traverse_dict(pod, "metadata:name", "default")
            ret['changes'].setdefault(namespace, {})[name] = "pod deleted"
            delete("pods", namespace, name, grace_period=grace_period, k8s=k8s)
    except Exception as exp:
        log.error("oops drain of the node failed due to %s", exp)
        ret['result'] = False
        ret['comment'] = str(exp)
    return ret


def cordon(node, kubeconfig="", context_name="", k8s=None):
    ret = {'name': "cordon", 'result': True, 'comment': '', 'changes': {}}
    if not k8s:
        with Kubernetes(kubeconfig, context_name) as k8s:
            return cordon(node=node, kubeconfig=kubeconfig, context_name=context_name, k8s=k8s)

    data = {'spec': {'unschedulable': True}}
    try:
        log.info("patching %s to cordon", node)
        k8s.patch(k8s.get_path('nodes', name=node), data, patch_mode="k8s")
        log.info("finished patching %s cordon", node)
        ret["changes"][node] = "node cordoned"
    except Exception as exp:
        log.error("oops can't cordon due to %s", exp)
        ret['result'] = False
        ret['comment'] = str(exp)
        return ret
    return ret


def uncordon(node, kubeconfig="", context_name="", k8s=None):
    ret = {'name': "uncordon", 'result': True, 'comment': '', 'changes': {}}
    if not k8s:
        with Kubernetes(kubeconfig, context_name) as k8s:
            return uncordon(node=node, kubeconfig=kubeconfig, context_name=context_name, k8s=k8s)

    data = {'spec': {'unschedulable': None}}
    try:
        node_data = get('nodes', name=node, k8s=k8s)
        log.info("current cordon state is: %s", traverse_dict(node_data, "spec:unschedulable", False))
        if traverse_dict(node_data, "spec:unschedulable", None):
            k8s.patch(k8s.get_path('nodes', name=node), data, patch_mode="k8s")
            ret["changes"][node] = "node uncordoned"
    except Exception as exp:
        log.error("oops, can't uncordong due to %s", exp)
        ret['result'] = False
        ret['comment'] = str(exp)
    return ret
