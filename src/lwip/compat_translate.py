"""
Tools for translating between constants defined in LwIP and in socket module.
"""

import socket
from typing import NamedTuple

from . import defs


class TranslateEntry(NamedTuple):
    name: str
    lwip_value: int
    socket_value: int


def gather_entries_with_prefix(prefix: str) -> set[TranslateEntry]:
    lwip_keys = set(s for s in dir(defs) if s.startswith(prefix))
    socket_keys = set(s for s in dir(socket) if s.startswith(prefix))
    common_keys = lwip_keys.intersection(socket_keys)
    return set(TranslateEntry(k, getattr(defs, k), getattr(socket, k)) for k in common_keys)


# Dicts for translating from socket constants to LwIP constants
# keys are socket constant values
SO_socket = {e.socket_value: e for e in gather_entries_with_prefix('SO_')}
IP_socket = {e.socket_value: e for e in gather_entries_with_prefix('IP_')}
TCP_socket = {e.socket_value: e for e in gather_entries_with_prefix('TCP_')}
IPV6_socket = {e.socket_value: e for e in gather_entries_with_prefix('IPV6_')}
UDPLITE_socket = {e.socket_value: e for e in gather_entries_with_prefix('UDPLITE_')}