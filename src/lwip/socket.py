import errno
import socket
from collections.abc import Sequence, Iterable
from typing import Self, overload

from . import compat_translate
from . import defs
from .ffi import ffi
from .lwip_error import LwipError, check_ret_errno


class SockAddr:
    """
    Represents a sockaddr struct.

    Provide convenience methods for casting to various sockaddr_* pointers.
    """
    def __init__(self) -> None:
        self._sa = ffi.new('struct sockaddr_storage *')
    
    @property
    def len(self):
        return self._sa.s2_len
    
    @len.setter
    def len(self, new_len):
        self._sa.s2_len = new_len
    
    @property
    def family(self):
        return self._sa.ss_family
    
    @family.setter
    def family(self, new_family):
        self._sa.ss_family = new_family
    
    @property
    def sockaddr(self):
        return ffi.cast('struct sockaddr *', self._sa)
    
    @property
    def sockaddr_in(self):
        return ffi.cast('struct sockaddr_in *', self._sa)
    
    @property
    def sockaddr_in6(self):
        return ffi.cast('struct sockaddr_in6 *', self._sa)
    
    @classmethod
    def sizeof(cls) -> int:
        return ffi.sizeof('struct sockaddr_storage')
    
    @classmethod
    def create_empty_sockaddr(cls):
        sa = cls()
        sa.len = cls.sizeof()
        return sa
    
    @classmethod
    def create_empty_sockaddr_paddrlen(cls):
        """
        Create an empty sockaddr struct and a socklen_t*, suitable for receiving output from socket functions.

        Returns (SockAddr instance, "socklen_t *" instance), with socklen_t prepopulated for the allocated size.
        """
        sa = cls.create_empty_sockaddr()
        paddr_len = ffi.new("socklen_t*")
        paddr_len[0] = sa.len
        return sa, paddr_len
    
    @classmethod
    def parse_address(cls, address: tuple, family: int = socket.AF_UNSPEC) -> Self:
        """
        Parse a Python address tuple into a SockAddr instance.

        Both IPv4 (host, port) and IPv6 (host, port, flowinfo, scope_id) tuples are supported.
        `host` must be an IP address literal, not a host name.

        If `family` is specified, it must match the family of the address tuple.
        """
        if family == socket.AF_UNSPEC:
            if len(address) == 2:
                family = socket.AF_INET
            elif len(address) == 4:
                family = socket.AF_INET6
            else:
                raise ValueError('Invalid address tuple length')
        
        sa = cls()

        if family == socket.AF_INET:
            if len(address) != 2:
                raise ValueError('Invalid address tuple length for AF_INET')
            host, port = address
            if not host:
                host = bytes(4)  # INADDR_ANY
            else:
                host = socket.inet_pton(socket.AF_INET, host)
            sa_in = sa.sockaddr_in
            sa_in.sin_len = ffi.sizeof('struct sockaddr_in')
            sa_in.sin_family = family
            sa_in.sin_port = socket.htons(port)
            ffi.memmove(ffi.buffer(ffi.addressof(sa_in, 'sin_addr')), host, 4)
            return sa
        elif family == socket.AF_INET6:
            if len(address) != 4:
                raise ValueError('Invalid address tuple length for AF_INET6')
            host, port, flowinfo, scope_id = address
            if not host:
                host = bytes(16)
            else:
                host = socket.inet_pton(socket.AF_INET6, host)
            sa_in6 = sa.sockaddr_in6
            sa_in6.sin6_len = ffi.sizeof('struct sockaddr_in6')
            sa_in6.sin6_family = family
            sa_in6.sin6_port = socket.htons(port)
            sa_in6.sin6_flowinfo = flowinfo
            ffi.memmove(ffi.buffer(ffi.addressof(sa_in6, 'sin6_addr')), host, 16)
            sa_in6.sin6_scope_id = scope_id
            return sa
        else:
            raise ValueError('Invalid family')
    
    def unparse_address(self) -> tuple:
        """
        Return the contents of this SockAddr instance in Python address tuple form.
        """
        if self.family == socket.AF_INET:
            sa_in = self.sockaddr_in
            host = socket.inet_ntop(socket.AF_INET, ffi.buffer(ffi.addressof(sa_in, 'sin_addr'))[:])
            port = socket.ntohs(sa_in.sin_port)
            return host, port
        elif self.family == socket.AF_INET6:
            sa_in6 = self.sockaddr_in6
            host = socket.inet_ntop(socket.AF_INET6, ffi.buffer(ffi.addressof(sa_in6, 'sin6_addr'))[:])
            port = socket.ntohs(sa_in6.sin6_port)
            flowinfo = sa_in6.sin6_flowinfo
            scope_id = sa_in6.sin6_scope_id
            return host, port, flowinfo, scope_id
        else:
            raise ValueError('Invalid family')



class Socket:
    """
    lwIP socket object.

    This class is mostly compatible with standard library socket objects.
    Any implemented method has the same signature as stdlib socket.

    Do not instantiate this class directly.
    Use LwIP.socket() instead.

    Notable differences:
    - {get, set}timeout only supports None or 0 timeout (i.e. blocking or non-blocking).
      Other finite timeout values are not supported.
    - {get, set}sockopt only supports options specified by constants that exist both in
      lwip.defs and socket,
      and any options defined using structs may not be the same as stdlib sockets.
      use lwip_{get, set}sockopt for advanced features.

    Thread safety:
    The underlying lwIP methods are compied as thread safe (LWIP_NETCONN_FULLDUPLEX),
    so calling send* / recv* / close from separate threads is possible.
    The close() method itself is not thread safe,
    so do not call close() concurrently from multiple threads.
    """

    def __init__(self, lwip_instance, family: int, type_: int, proto: int, fd: int):
        """
        Private constructor -- use Lwip.socket instead.
        """
        self._lwip = lwip_instance
        self._family = family
        self._type = type_
        self._proto = proto
        if fd < 0:
            # The calling code should use check_ret_errno around the code where fd is obtained
            raise ValueError('Invalid FD')
        self._s = fd
    
    @property
    def lwip_instance(self):
        return self._lwip
    
    @property
    def family(self) -> int:
        return self._family
    
    @property
    def type(self) -> int:
        return self._type
    
    @property
    def proto(self) -> int:
        return self._proto
    
    def fileno(self) -> int:
        return self._s

    def bind(self, address):
        sa = SockAddr.parse_address(address)
        return check_ret_errno(
            'bind',
            self._lwip.lwip.lwip_bind,
            self._s,
            sa.sockaddr,
            sa.len,
        )

    def listen(self, backlog=-1):
        if backlog < 0:
            backlog = 0

        return check_ret_errno(
            "listen",
            self._lwip.lwip.lwip_listen,
            self._s,
            backlog,
        )

    def accept(self) -> tuple['Socket', tuple]:
        sa, paddr_len = SockAddr.create_empty_sockaddr_paddrlen()
        s = Socket(
            self._lwip,
            self.family,
            self.type,
            self.proto,
            check_ret_errno(
                "accept",
                self._lwip.lwip.lwip_accept,
                self._s,
                sa.sockaddr,
                paddr_len,
            ),
        )

        return s, sa.unparse_address()

    def connect(self, address):
        sa = SockAddr.parse_address(address)
        return check_ret_errno(
            "connect",
            self._lwip.lwip.lwip_connect,
            self._s,
            sa.sockaddr,
            sa.len,
        )
    
    def connect_ex(self, address):
        sa = SockAddr.parse_address(address)
        return self._lwip.lwip.lwip_connect(
            self._s,
            sa.sockaddr,
            sa.len,
        )

    def recv(self, bufsize, flags=0):
        buffer = ffi.new("char[]", bufsize)
        ret = check_ret_errno(
            "recv",
            self._lwip.lwip.lwip_recv,
            self._s,
            buffer,
            bufsize,
            flags,
        )
        return ffi.buffer(buffer, ret)[:]
    
    def recv_into(self, buffer: bytearray | memoryview, nbytes: int = 0, flags: int = 0) -> int:
        buflen = len(buffer)
        if nbytes < 0:
            raise ValueError('negative buffersize in recv_into')
        if nbytes == 0:
            nbytes = buflen
        if buflen < nbytes:
            raise ValueError('buffer too small for requested bytes')
        return check_ret_errno(
            'recv',
            self._lwip.lwip.lwip_recv,
            self._s,
            ffi.from_buffer(buffer, require_writable=True),
            nbytes,
            flags,
        )

    def recvfrom(self, bufsize, flags=0):
        buffer = ffi.new("char[]", bufsize)
        sa, paddr_len = SockAddr.create_empty_sockaddr_paddrlen()
        ret = check_ret_errno(
            "recvfrom",
            self._lwip.lwip.lwip_recvfrom,
            self._s,
            buffer,
            bufsize,
            flags,
            sa.sockaddr,
            paddr_len,
        )
        return ffi.buffer(buffer, ret)[:], sa.unparse_address()
    
    def recvfrom_into(self, buffer: bytearray | memoryview, nbytes: int = 0, flags: int = 0) -> tuple[int, tuple]:
        buflen = len(buffer)
        if nbytes < 0:
            raise ValueError('negative buffersize in recv_into')
        if nbytes == 0:
            nbytes = buflen
        if buflen < nbytes:
            raise ValueError('buffer too small for requested bytes')
        
        sa, paddr_len = SockAddr.create_empty_sockaddr_paddrlen()
        ret = check_ret_errno(
            'recvfrom',
            self._lwip.lwip.lwip_recvfrom,
            self._s,
            ffi.from_buffer(buffer, require_writable=True),
            nbytes,
            flags,
            sa.sockaddr,
            paddr_len,
        )
        return ret, sa.unparse_address()
    
    def recvmsg(self, bufsize: int, ancbufsize: int = 0, flags: int = 0) -> tuple[bytes, list, int, tuple | None]:
        if ancbufsize != 0:
            raise LwipError('receiving ancillary data is not supported')
        msg = ffi.new('struct msghdr *')
        sa = SockAddr.create_empty_sockaddr()
        msg.msg_name = sa.sockaddr
        msg.msg_namelen = sa.len
        iov = ffi.new('struct iovec *')
        iov_base = ffi.new('char[]', bufsize)
        iov.iov_base = iov_base
        iov.iov_len = bufsize
        msg.msg_iov = iov
        msg.msg_iovlen = 1
        msg.msg_control = ffi.NULL

        ret = check_ret_errno(
            'recvmsg',
            self._lwip.lwip.lwip_recvmsg,
            self._s,
            msg,
            flags,
        )

        if sa.family == socket.AF_UNSPEC:
            address = None
        else:
            address = sa.unparse_address()

        return (
            ffi.buffer(iov_base, ret)[:],
            [],
            msg.msg_flags,
            address,
        )
    
    def recvmsg_into(
        self,
        buffers: Iterable[bytearray | memoryview],
        ancbufsize: int = 0,
        flags: int = 0,
    ) -> tuple[int, list, int, tuple | None]:
        if ancbufsize != 0:
            raise LwipError('receiving ancillary data is not supported')
        buffers = tuple(buffers)
        if len(buffers) > defs.IOV_MAX:
            raise OSError('length of buffers exceeded IOV_MAX')
        msg = ffi.new('struct msghdr *')
        sa = SockAddr.create_empty_sockaddr()
        msg.msg_name = sa.sockaddr
        msg.msg_namelen = sa.len
        iov_contents = [
            {'iov_base': ffi.from_buffer(b, require_writable=True), 'iov_len': len(b)}
            for b in buffers
        ]
        iov = ffi.new('struct iovec []', iov_contents)
        msg.msg_iov = iov
        msg.msg_iovlen = len(iov_contents)
        msg.msg_control = ffi.NULL

        ret = check_ret_errno(
            'recvmsg',
            self._lwip.lwip.lwip_recvmsg,
            self._s,
            msg,
            flags,
        )

        if sa.family == socket.AF_UNSPEC:
            address = None
        else:
            address = sa.unparse_address()

        return (
            ret,
            [],
            msg.msg_flags,
            address,
        )

    def send(self, payload, flags=0):
        return check_ret_errno(
            "send",
            self._lwip.lwip.lwip_send,
            self._s,
            ffi.from_buffer(payload),
            len(payload),
            flags,
        )
    
    def sendall(self, payload, flags=0):
        payload = memoryview(payload)
        while payload:
            bytes_sent = self.send(payload, flags)
            payload = payload[bytes_sent:]
    
    @overload
    def sendto(self, payload: bytes | bytearray | memoryview, address: tuple, /) -> int:
        ...
    
    @overload
    def sendto(self, payload: bytes | bytearray | memoryview, flags: int, address: tuple, /) -> int:
        ...

    def sendto(self, payload, arg2, arg3 = None) -> int:
        if arg3 is None:
            address = arg2
            flags = 0
        else:
            flags = arg2
            address = arg3
        sa = SockAddr.parse_address(address)
        return check_ret_errno(
            "sendto",
            self._lwip.lwip.lwip_sendto,
            self._s,
            ffi.from_buffer(payload),
            len(payload),
            flags,
            sa.sockaddr,
            sa.len,
        )
    
    def sendmsg(
        self,
        buffers: Iterable[bytes | bytearray | memoryview],
        ancdata: Iterable[tuple] | None = None,
        flags: int = 0,
        address: tuple | None = None,
    ) -> int:
        if ancdata:
            raise LwipError('sending ancillary data is not supported')
        buffers = tuple(buffers)
        if len(buffers) > defs.IOV_MAX:
            raise OSError('length of buffers exceeded IOV_MAX')
        msg = ffi.new('struct msghdr *')
        if address is not None:
            sa = SockAddr.parse_address(address)
            msg.msg_name = sa.sockaddr
            msg.msg_namelen = sa.len
        else:
            msg.msg_name = ffi.NULL
        iov_contents = [
            {'iov_base': ffi.from_buffer(b), 'iov_len': len(b)}
            for b in buffers
        ]
        iov = ffi.new('struct iovec []', iov_contents)
        msg.msg_iov = iov
        msg.msg_iovlen = len(iov_contents)
        msg.msg_control = ffi.NULL

        return check_ret_errno(
            'sendmsg',
            self._lwip.lwip.lwip_sendmsg,
            self._s,
            msg,
            flags,
        )
    
    def shutdown(self, how: int) -> None:
        check_ret_errno(
            'shutdown',
            self._lwip.lwip.lwip_shutdown,
            self._s,
            how,
        )

    def close(self):
        """
        Close the socket.

        NOTE: this method is not thread safe. Do not call from multiple threads concurrently.
        """
        if self._s >= 0:
            try:
                check_ret_errno('close', self._lwip.lwip.lwip_close, self._s)
            finally:
                self._s = -1

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def __repr__(self):
        return f"LwipSocket(fd={self._s}, family={self.family}, type={self.type}, proto={self.proto})"

    def getpeername(self):
        sa, paddr_len = SockAddr.create_empty_sockaddr_paddrlen()
        check_ret_errno(
            'getpeername',
            self._lwip.lwip.lwip_getpeername,
            self._s,
            sa.sockaddr,
            paddr_len,
        )
        return sa.unparse_address()
    
    def getsockname(self):
        sa, paddr_len = SockAddr.create_empty_sockaddr_paddrlen()
        check_ret_errno(
            'getsockname',
            self._lwip.lwip.lwip_getsockname,
            self._s,
            sa.sockaddr,
            paddr_len,
        )
        return sa.unparse_address()
    
    @overload
    def lwip_setsockopt(
        self,
        level: int,
        optname: int,
        value: int | bytes | bytearray | memoryview,
    )-> None:
        ...
    
    @overload
    def lwip_setsockopt(
        self,
        level: int,
        optname: int,
        value: None,
        optlen: int,
    ) -> None:
        ...
    
    def lwip_setsockopt(
            self,
            level,
            optname,
            value,
            optlen = None,
        ) -> None:
        """
        setsockopt that takes LwIP's constants.

        The constants used for `level` and `optname`
        (as well as structs that may be used in `value`, etc.)
        are different between LwIP and Linux.
        This method accepts those defined by LwIP.
        """
        if optlen is None:
            if value is None:
                raise ValueError('value and optlen must not be None at the same time')
            elif isinstance(value, int):
                optval = ffi.new('int *')
                optval[0] = value
                optlen = ffi.sizeof('int')
            else:
                optval = ffi.buffer(value)
                optlen = len(value)
        else:  # optlen is not None
            if value is not None:
                raise ValueError('value and optlen cannot be not-None at the same time')
            optval = ffi.NULL
            optlen = optlen

        check_ret_errno(
            'setsockopt',
            self._lwip.lwip.lwip_setsockopt,
            self._s,
            level,
            optname,
            optval,
            optlen,
        )
    
    @overload
    def setsockopt(
        self,
        level: int,
        optname: int,
        value: int | bytes | bytearray | memoryview,
    )-> None:
        ...
    
    @overload
    def setsockopt(
        self,
        level: int,
        optname: int,
        value: None,
        optlen: int,
    ) -> None:
        ...
    
    def setsockopt(self, level, optname, value, optlen=None) -> None:
        """
        setsockopt that takes socket module constants, intended for compatibility with existing socket code.

        This method accepts `level` and `optname` defined in the socket module,
        and translate them to corresponding LwIP constants.
        Only those constants that exist in the socket module are recognized
        (for example, `socket` does not have IP_PKTINFO).
        Also, structs that may be used in `value` are not translated.
        Use `lwip_setsockopt` for those use cases.
        """
        try:
            lwip_level, lwip_optname = compat_translate.translate_sockopt(level, optname)
        except ValueError as e:
            raise OSError(errno.ENOPROTOOPT, f'LwIP: {e.args[0]}')
        
        self.lwip_setsockopt(lwip_level, lwip_optname, value, optlen)
    
    @overload
    def lwip_getsockopt(
        self,
        level: int,
        optname: int,
    ) -> int:
        ...
    
    @overload
    def lwip_getsockopt(
        self,
        level: int,
        optname: int,
        buflen: int,
    ) -> bytes:
        ...
    
    def lwip_getsockopt(
        self,
        level: int,
        optname: int,
        buflen = None,
    ):
        """
        getsockopt that takes LwIP's constants.

        Refer to documentation on `lwip_setsockopt` and `setsockopt`.
        """
        optlen = ffi.new('socklen_t *')
        if buflen is not None:
            optval = ffi.new('char[]', buflen)
            optlen[0] = buflen
        else:
            optval = ffi.new('int *')
            optlen[0] = ffi.sizeof('int')
        
        check_ret_errno(
            'getsockopt',
            self._lwip.lwip.lwip_getsockopt,
            self._s,
            level,
            optname,
            optval,
            optlen,
        )

        if buflen is not None:
            return ffi.buffer(optval)[:]
        else:
            return optval[0]
    
    @overload
    def getsockopt(
        self,
        level: int,
        optname: int,
    ) -> int:
        ...
    
    @overload
    def getsockopt(
        self,
        level: int,
        optname: int,
        buflen: int,
    ) -> bytes:
        ...

    def getsockopt(self, level, optname, buflen=None) -> int | bytes:
        """
        getsockopt that takes socket module constants.

        Refer to documentation on `lwip_setsockopt` and `setsockopt`.
        """
        try:
            lwip_level, lwip_optname = compat_translate.translate_sockopt(level, optname)
        except ValueError as e:
            raise OSError(errno.ENOPROTOOPT, f'LwIP: {e.args[0]}')
        
        return self.lwip_getsockopt(lwip_level, lwip_optname, buflen)
    
    def lwip_ioctl(self, cmd: int, arg: int = 0) -> int:
        """
        Perform ioctl on the socket.

        In LwIP, argp can only be an int pointer, so arg only takes an int.

        Returns the content of argp as an int.
        """
        argp = ffi.new('int *')
        argp[0] = arg
        check_ret_errno(
            'ioctl',
            self._lwip.lwip.lwip_ioctl,
            self._s,
            cmd,
            argp,
        )
        return argp[0]

    
    def lwip_fcntl(self, cmd: int, val: int = 0) -> int:
        """
        Perform fcntl on the socket.

        val can only be an int.

        Returns the return value of fcntl.
        """
        return check_ret_errno(
            'fcntl',
            self._lwip.lwip.lwip_fcntl,
            self._s,
            cmd,
            val,
        )
    
    def getblocking(self) -> bool:
        """
        Return True if socket is in blocking mode, False otherwise.

        We do not support settimeout with finite timeout values,
        and do not maintain a timeout / blocking state.
        So this method always query LwIP internals.
        """
        flags = self.lwip_fcntl(defs.F_GETFL)
        return not bool(flags & defs.O_NONBLOCK)
    
    def setblocking(self, blocking: bool) -> None:
        self.lwip_ioctl(defs.FIONBIO, int(not blocking))
    
    def gettimeout(self) -> float | None:
        if self.getblocking():
            return None
        return 0.0
    
    def settimeout(self, value: float | None) -> None:
        """
        Set a timeout on blocking socket operations, except we don't support any timeout other than infinite or 0.

        This method can be used to put the socket in blocking or non-blocking mode.
        Positive finite timeouts are not supported.
        """
        if value is None:
            self.setblocking(True)
        elif value == 0.0:
            self.setblocking(False)
        else:
            raise ValueError('Only infinite or 0 timeout supported')
