import socket

from .defs import AF_INET, AF_INET6, INADDR_ANY
from .ffi import ffi
from .lwip_error import LwipError, check_ret_errno


class Socket:
    """
    lwIP socket abstraction

    Implemented methods try to mimic Python's socket API as closely as possible. Exceptions
    are documented in the offending method's docs.
    """

    def __init__(self, lwip_instance, family, fd):
        """
        Private constructor -- use Lwip.socket instead.
        """
        self.lwip = lwip_instance
        self.family = family
        if fd < 0:
            # The calling code should use check_ret_errno around the code where fd is obtained
            raise ValueError('Invalid FD')
        self.s = fd

    def bind(self, address):
        addr, addr_len = self._parse_address(address)
        return check_ret_errno(
            'bind',
            self.lwip.lwip_bind,
            self.s,
            ffi.cast('struct sockaddr *', addr),
            addr_len,
        )

    def listen(self, backlog=-1):
        if backlog < 0:
            backlog = 0

        return check_ret_errno(
            "listen",
            self.lwip.lwip_listen,
            self.s,
            backlog,
        )

    def accept(self):
        addr, paddr_len = self._create_address_buffer()
        s = Socket(
            self.lwip,
            self.family,
            check_ret_errno(
                "accept",
                self.lwip.lwip_accept,
                self.s,
                ffi.cast('struct sockaddr *', addr),
                paddr_len,
            ),
        )

        return s, self._unparse_address(addr, paddr_len)

    def connect(self, address):
        addr, addr_len = self._parse_address(address)
        return check_ret_errno(
            "connect",
            self.lwip.lwip_connect,
            self.s,
            ffi.cast('struct sockaddr *', addr),
            addr_len,
        )

    def recv(self, bufsize, flags=0):
        buffer = ffi.new("char[]", bufsize)
        ret = check_ret_errno(
            "recv",
            self.lwip.lwip_recv,
            self.s,
            buffer,
            bufsize,
            flags,
        )
        return ffi.buffer(buffer, ret)[:]

    def recvfrom(self, bufsize, flags=0):
        buffer = ffi.new("char[]", bufsize)
        addr, paddr_len = self._create_address_buffer()
        ret = check_ret_errno(
            "recv",
            self.lwip.lwip_recvfrom,
            self.s,
            buffer,
            bufsize,
            flags,
            ffi.cast('struct sockaddr *', addr),
            paddr_len,
        )
        return ffi.buffer(buffer, ret)[:], self._unparse_address(addr, paddr_len)

    def send(self, payload, flags=0):
        return check_ret_errno(
            "send",
            self.lwip.lwip_send,
            self.s,
            payload,
            len(payload),
            flags,
        )

    def sendto(self, payload, address, flags=0):
        """
        Differences from Python's socket.sendto:
            - flags is a named argument instead of a positional one
        """
        addr, addr_len = self._parse_address(address)
        return check_ret_errno(
            "sendto",
            self.lwip.lwip_sendto,
            self.s,
            payload,
            len(payload),
            flags,
            ffi.cast('struct sockaddr *', addr),
            addr_len,
        )

    def close(self):
        if self.s >= 0:
            self.lwip.lwip_close(self.s)
            self.s = -1

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
    
    def _create_sockaddr(self):
        if self.family == AF_INET:
            addr = ffi.new('struct sockaddr_in *')
            addr_len = ffi.sizeof('struct sockaddr_in')
            addr.sin_len = addr_len
            addr.sin_family = self.family
        elif self.family == AF_INET6:
            addr = ffi.new('struct sockaddr_in6 *')
            addr_len = ffi.sizeof('struct sockaddr_in6')
            addr.sin6_len = addr_len
            addr.sin6_family = self.family
        else:
            assert False, 'Unexpected family'
        return addr, addr_len

    def _create_address_buffer(self):
        """
        Creates a new `struct sockaddr_in` structure to hold addresses returned by
        methods like connect / recvfrom / etc.

        NOTE: The returned objects hold ownership of the structure and pointers, keep
        a reference in a variable to them while they are needed to prevent the GC from
        freeing them while they are still in use.

        :return: (struct sockaddr_in* or struct sockaddr_in6*, socklen_t*)
                 Created structure and a pointer variable containing its size.
        """
        paddr_len = ffi.new("socklen_t*")
        addr, addr_len = self._create_sockaddr()
        paddr_len[0] = addr_len
        return addr, paddr_len

    def _parse_address(self, address):
        """
        Parses an address from Python's socket API format into a `struct sockaddr*`.

        Note the type of return values, and cast to "struct sockaddr*" as required.

        TODO: This does not work for dual-stack sockets accepting an IPv4 connection.

        :param address: (host, port) tuple
        :return: (struct sockaddr_in* or struct sockaddr_in6*, int)
                 Parsed address and length of the address, in bytes.
        """
        saddr, addr_len = self._create_sockaddr()
        if self.family == AF_INET:
            if not isinstance(address, tuple) or len(address) != 2:
                raise TypeError("Only (host, port) tuples are supported (AF_INET)")

            host, port = address
            if not host:
                host = INADDR_ANY
            else:
                host = socket.inet_pton(socket.AF_INET, host)

            ffi.memmove(ffi.buffer(ffi.addressof(saddr, 'sin_addr')), host, 4)
            saddr.sin_port = socket.htons(port)
            return saddr, addr_len
        elif self.family == AF_INET6:
            if not isinstance(address, tuple) or len(address) != 4:
                raise TypeError("Only (host, port, flowinfo, scope_id) tuples are supported (AF_INET6)")
            host, port, flowinfo, scope_id = address
            if not host:
                host = bytes(16)
            else:
                host = socket.inet_pton(socket.AF_INET6, host)
            saddr.sin6_port = socket.htons(port)
            saddr.sin6_flowinfo = flowinfo
            ffi.memmove(ffi.buffer(ffi.addressof(saddr, 'sin6_addr')), host, 16)
            saddr.sin6_scope_id = scope_id
            return saddr, addr_len
        assert False, 'Unexpected family'

    def _unparse_address(self, sockaddr, _paddr_len):
        """
        Takes a `struct sockaddr*` and `socklen_t*` as input and returns the same
        address in the format specified by Python's socket API. This is the inverse
        function of _parse_address.

        :param sockaddr: `struct sockaddr*`
        :param _paddr_len:  `socklen_t*` Real size of address
        :return: (host, port)
        """
        assert ffi.cast("struct sockaddr*", sockaddr).sa_family == self.family, 'Unexpected family'

        if self.family == AF_INET:
            sockaddr_in = ffi.cast('struct sockaddr_in *', sockaddr)
            assert _paddr_len[0] >= sockaddr_in.sin_len, 'addr_len too small'
            host = socket.inet_ntop(socket.AF_INET, ffi.buffer(ffi.addressof(sockaddr_in, 'sin_addr'))[:])
            port = socket.ntohs(sockaddr_in.sin_port)
            return host, port
        elif self.family == AF_INET6:
            sockaddr_in6 = ffi.cast('struct sockaddr_in6 *', sockaddr)
            assert _paddr_len[0] >= sockaddr_in6.sin6_len, 'addr_len too small'
            host = socket.inet_ntop(socket.AF_INET6, ffi.buffer(ffi.addressof(sockaddr_in6, 'sin6_addr'))[:])
            port = socket.ntohs(sockaddr_in6.sin6_port)
            flowinfo = sockaddr_in6.sin6_flowinfo
            scope_id = sockaddr_in6.sin6_scope_id
            return host, port, flowinfo, scope_id
        assert False, 'family fallthrough'

    def __repr__(self):
        return f"LwipSocket(fd={self.s})"
