"""
This file includes asserts that ensure constants defined by LwIP have the same value as those in the socket module,
to ensure our socket objects are compatible with stdlib sockets.
"""

import socket

from . import defs


# SOL_SOCKET differs


def check_values_with_prefix(prefix: str) -> None:
    keys = [s for s in dir(defs) if s.startswith(prefix)]
    for key in keys:
        lwip_value = getattr(defs, key)
        try:
            socket_value = getattr(socket, key)
        except AttributeError:
            continue
        assert lwip_value == socket_value, f'Value of {key} differs between LwIP ({lwip_value}) and socket({socket_value})'


check_values_with_prefix('AF_')
check_values_with_prefix('IPPROTO_')
check_values_with_prefix('SOCK_')
check_values_with_prefix('SHUT_')

# MSG_* differs