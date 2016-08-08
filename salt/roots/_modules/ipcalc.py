'''
:maintainer:    IP address calculator
:maturity:      new
:depends:       ipcalc
:platform:      Linux,FreeBSD
'''

import salt.ext.ipaddress as ipaddr
import re
import salt.exceptions

__func_alias__ = {
    'list_': 'list'
}

def __virtual__():
    '''
    Confirm this module is supported by the OS and the system has
    required tools
    '''
    return True


def get_net(cidr):
    try:
        cidr_network = ipaddr.ip_interface(cidr)
    except Exception:
        raise salt.exceptions.SaltInvocationError(
            'Invalid CIDR \'{0}\''.format(cidr))
    return cidr_network

def netmask(cidr):
    '''
    return mask in accordance to cidr input 
    '''
    return str(get_net(cidr).netmask)

def broadcast(cidr):
    '''
    return mask in accordance to cidr input 
    '''
    return str(ipaddr.ip_network(get_net(cidr).network).broadcast_address)

def network(cidr):
    '''
    return mask in accordance to cidr input 
    '''
    return str(get_net(cidr).network.network_address)

def prefix(cidr):
    '''
    return prefix for mask in accordance to cidr input 
    '''
    return str(get_net(cidr).network.prefixlen)

def first_host(cidr):
    '''
    return mask in accordance to cidr input 
    '''
    cidr_network = get_net(cidr)
    return  str(ipaddr.ip_address(cidr_network._ip + 1))

