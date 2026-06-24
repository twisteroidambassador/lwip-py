import errno

from .defs import PollEvent
from .ffi import ffi
from .lwip_error import check_ret_errno
from .socket import Socket


class LwipPoll:
    """
    A poll object that works on lwIP sockets, similar to select.poll.

    All implemented methods have the same signature as select.poll,
    but only accept lwIP socket objects instead of Python stdlib sockets,
    and uses event mask values defined in lwip.defs.PollEvent instead of select.POLL*.

    Do not instantiate this class directly.
    Instead, use LwIP.poll().
    """
    def __init__(self, lwip_instance) -> None:
        """
        Private initializer. Do not call directly, Use LwIP.poll() instead. 
        """
        self._lwip = lwip_instance
        self._registered_fds: dict[int, int] = dict()  # fd -> event mask
        self._fds = None
        self._fds_fresh = False
    
    @property
    def lwip_instance(self):
        return self._lwip
    
    def _get_fd(self, fd: int | Socket) -> int:
        if not isinstance(fd, int):
            if fd.lwip_instance is not self.lwip_instance:
                raise ValueError('Socket is not on same LwIP instance')
            fd = fd.fileno()
        if fd < 0:
            raise ValueError(f'Invalid fd {fd}')
        return fd
    
    def register(
            self,
            fd: int | Socket,
            eventmask: int = PollEvent.POLLIN | PollEvent.POLLOUT | PollEvent.POLLPRI,
    ) -> None:
        self._registered_fds[self._get_fd(fd)] = eventmask
        self._fds_fresh = False
    
    def modify(self, fd: int | Socket, eventmask: int) -> None:
        fd = self._get_fd(fd)
        if fd not in self._registered_fds:
            raise OSError(errno.ENOENT, f'LwIP poll: fd {fd} not registered')
        self._registered_fds[fd] = eventmask
        self._fds_fresh = False
    
    def unregister(self, fd: int | Socket) -> None:
        fd = self._get_fd(fd)
        del self._registered_fds[fd]
        self._fds_fresh = False
    
    def _populate_fds(self):
        if self._fds_fresh:
            assert self._fds is not None
            return self._fds
        self._fds = ffi.new(
            'struct pollfd []',
            [
                {'fd': k, 'events': v}
                for k, v in self._registered_fds.items()
            ]
        )
        self._fds_fresh = True
        return self._fds

    def poll(self, timeout: float | None = None) -> list[tuple[int, PollEvent]]:
        if timeout is None:
            timeout = -1
        fds = self._populate_fds()
        nready = check_ret_errno(
            'poll',
            self._lwip.lwip.lwip_poll,
            fds,
            len(fds),
            timeout,
        )
        ready_fds = [
            (s.fd, PollEvent(s.revents))
            for s in fds
            if s.revents
        ]
        assert nready == len(ready_fds), 'Incorrect nready'
        return ready_fds