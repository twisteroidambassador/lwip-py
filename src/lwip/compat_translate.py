"""
Tools for translating between constants defined in LwIP and in socket module.
"""

import itertools
import socket
from collections.abc import Callable
from typing import Iterable, Iterator, NamedTuple

from . import defs


class TranslateEntry(NamedTuple):
    name: str
    lwip_value: int
    socket_value: int


def _yield_socket_lwip_matching_entries(predicate: Callable[[str], bool]) -> Iterator[TranslateEntry]:
    for key in filter(predicate, dir(defs)):
        try:
            yield TranslateEntry(key, getattr(defs, key), getattr(socket, key))
        except AttributeError:
            continue


def _yield_sockopt_translate_entry(
        level_name: str,
        opt_entries: Iterable[TranslateEntry],
) -> Iterator[tuple[int, tuple[TranslateEntry, dict[int, TranslateEntry]]]]:
    try:
        socket_level_value = getattr(socket, level_name)
        lwip_level_value = getattr(defs, level_name)
    except AttributeError:
        return
    yield (
        socket_level_value,
        (
            TranslateEntry(level_name, lwip_level_value, socket_level_value),
            {e.socket_value: e for e in opt_entries},
        )
    )


_sockopt_translate_table = dict(itertools.chain(
    _yield_sockopt_translate_entry(
        'SOL_SOCKET',
        _yield_socket_lwip_matching_entries(lambda s: s.startswith('SO_')),
    ),
    _yield_sockopt_translate_entry(
        'IPPROTO_IP',
        _yield_socket_lwip_matching_entries(lambda s: s.startswith('IP_')),
    ),
    _yield_sockopt_translate_entry(
        'IPPROTO_TCP',
        _yield_socket_lwip_matching_entries(lambda s: s.startswith('TCP_')),
    ),
    _yield_sockopt_translate_entry(
        'IPPROTO_IPV6',
        _yield_socket_lwip_matching_entries(lambda s: s.startswith('IPV6_')),
    ),
    _yield_sockopt_translate_entry(
        'IPPROTO_UDPLITE',
        _yield_socket_lwip_matching_entries(lambda s: s.startswith('UDPLITE_')),
    ),
    _yield_sockopt_translate_entry(
        'IPPROTO_RAW',
        _yield_socket_lwip_matching_entries(lambda s: s == 'IPV6_CHECKSUM'),
    ),
))


def translate_sockopt(level: int, optname: int) -> tuple[int, int]:
    """
    Translate (level, optname) pair from socket module into corresponding lwIP values.

    :raises ValueError: if level or optname is not supported or is not found in socket module.
    """
    try:
        level_entry, optname_translate_table = _sockopt_translate_table[level]
    except KeyError:
        raise ValueError(f'No corresponding level for {level}')
    try:
        optname_entry = optname_translate_table[optname]
    except KeyError:
        raise ValueError(f'No corresponding optname for {optname} in level {level_entry}')
    return level_entry.lwip_value, optname_entry.lwip_value