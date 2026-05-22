"""
This module provides a selector implementation compatible with those in the selectors stdlib module.
"""

import selectors

from . import LwIP
from .defs import PollEvent
from .socket import Socket


def _fileobj_to_fd(fileobj: int | Socket):
    """Return a file descriptor from a file object.

    Parameters:
    fileobj -- file object or file descriptor

    Returns:
    corresponding file descriptor

    Raises:
    ValueError if the object is invalid
    """
    if isinstance(fileobj, int):
        fd = fileobj
    else:
        try:
            fd = int(fileobj.lwip_fileno())
        except (AttributeError, TypeError, ValueError):
            raise ValueError("Invalid file object: "
                             "{!r}".format(fileobj)) from None
    if fd < 0:
        raise ValueError("Invalid file descriptor: {}".format(fd))
    return fd


class LwipPollSelector(selectors._PollLikeSelector):
    """
    Selctor based on lwIP's poll(). API compatible with Python stdlib selectors module.
    """
    _EVENT_READ = PollEvent.POLLIN
    _EVENT_WRITE = PollEvent.POLLOUT

    def __init__(self, lwip_inst: LwIP):
        """
        Create a selector for sockets on this lwIP instance.

        Only sockets on this lwIP instance can be used.
        Native sockets, as well as sockets on other lwIP instances,
        are not supported.

        :param lwip_inst: the LwIP instance.
        """
        self._selector_cls = lwip_inst.poll
        super().__init__()
    
    def _fileobj_lookup(self, fileobj: int | Socket):
        """Return a file descriptor from a file object.

        This wraps _fileobj_to_fd() to do an exhaustive search in case
        the object is invalid but we still have it in our map.  This
        is used by unregister() so we can unregister an object that
        was previously registered even if it is closed.  It is also
        used by _SelectorMapping.
        """
        try:
            return _fileobj_to_fd(fileobj)
        except ValueError:
            # Do an exhaustive search.
            for key in self._fd_to_key.values():
                if key.fileobj is fileobj:
                    return key.fd
            # Raise ValueError after all.
            raise