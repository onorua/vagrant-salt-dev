# -*- coding: utf-8 -*-
'''
Operations on OpenvSwitch Bridges
=================================

'''
# Import python libs
import logging
import pprint
import yaml

# Import salt libs
import salt.utils
import salt.utils.templates
from salt.exceptions import CommandExecutionError

def managed(name, create=True, ports=[], clean=False, stp=True, enabled=True):
    '''
    Ensure a OpenVSwitch based bridge existe and optionally has
    a list of interfaces as ports assigned.
    '''
    ret = {'name': name,
       'changes': {},
       'result': True,
       'comment': ''}

    if not __salt__['ovs_bridge.exists'](name):
        __salt__['ovs_bridge.add'](name)
        ret['changes'][name] = 'New ovs_bridge'

    if ports and (not isinstance(ports, list) or not isinstance(ports[0], dict)):
        # I sure hope a str doesn't qualify as list...
        raise ValueError

    for iface in ports:
        if not __salt__['ovs_bridge.is_connected'](iface.get('name'),
                                                   iface.get('type'),
                                                   iface.get('peer')):
            __salt__['ovs_bridge.connect'](iface.get('name'), iface.get('type'),
                                                       iface.get('peer'))
        if __salt__['ovs_bridge.find_interfaces'](iface.get('name'))[iface.get('name')] == name:
            continue
        elif __salt__['ovs_bridge.addif'](name, iface.get('name')):
            ret['changes'][iface.get('name')] = 'Added to bridge "{0}"'.format(name)
        else:
            ret['comment'] = 'Failed to add one or more ports to '\
                            'bridge "{0}" ("{1}" among others).'\
                            ''.format(name,iface)

            ret['changes'][iface.get('name')] = 'Added connection to "{0}"'.format(iface.get('peer'))

    if enabled:
        if not __salt__['ovs_bridge.state'](name):
            __salt__['ovs_bridge.state'](name, 'up')
            ret['changes'][name+' state'] = 'Get the bridge {0} to state up'.format(name)
    else:
        if __salt__['ovs_bridge.state'](name):
            __salt__['ovs_bridge.state'](name, 'down')
            ret['changes'][name+' state'] = 'Get the bridge {0} to state down'.format(name)

    if stp:
        if not __salt__['ovs_bridge.stp'](name):
            __salt__['ovs_bridge.stp'](name, 'enable')
            ret['changes'][name+' stp'] = 'enable STP on the bridge {0}'.format(name)
    else:
        if __salt__['ovs_bridge.stp'](name):
            __salt__['ovs_bridge.stp'](name, 'disable')
            ret['changes'][name+' stp'] = 'disable STP on the bridge {0}'.format(name)

    if not clean:
        return ret

    for iface in __salt__['ovs_bridge.interfaces'](name):
        if iface not in [x.get('name') for x in ports]:
            if __salt__['ovs_bridge.delif'](name, iface):
                ret['changes']["-"+iface] = 'Deleted from bridge "{0}"'\
                                        ''.format(name)
            else:
                ret['result'] = False
                ret['comment'] = 'Failed to del one or more ports'\
                                'from bridge "{0}"'.format(name)
    return ret
    
