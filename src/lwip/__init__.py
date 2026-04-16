import os

from tempfile import NamedTemporaryFile

from .ffi import ffi
from .defs import SOCK_STREAM, SOCK_DGRAM, AF_INET, AF_INET6
from .lwip_error import LwipError
from .netif import Netif
from .netif.driver import NetifDriver
from .socket import Socket
from .tcpip import tcpip_init


class LwIP:
    def __init__(self, shared_object_path=None):
        self.lwip = _load_lwip(shared_object_path)
        self.allocs = []  # Prevent GC from freeing memory in use by lwIP
        self.routing_hook = None
        tcpip_init(self.lwip)

    def create_netif(self, driver: NetifDriver):
        """
        Creates a new netif instance for a given driver.

        Note that this will not register the netif with the stack, you need to
        call netif.add for that.

        This method will create a permanent memory allocation for the netif
        instance that will not be freed while this lwIP instance is alive.
        Keep that in mind if your use case requires constant creation and
        removal of netifs.

        :param driver: Driver instance, must be a subclass of NetifDriver
        :return: new Netif instance
        """
        new_netif = Netif(self.lwip, driver)
        self.allocs.append(new_netif)
        return new_netif

    def socket(self, family, socket_type, flags=0):
        """
        Creates a new socket, in a similar way to how Python's `socket.socket()` function works

        For reference see `lwip_socket`.

        :return: An lwIP Socket instance.
        """
        s = self.lwip.lwip_socket(family, socket_type, flags)
        return Socket(self.lwip, family, s)

    def set_routing_function(self, routing_fn):
        """
        Sets an override for lwIP hook `LWIP_HOOK_IP4_ROUTE_SRC`.

        This will replace any previous override

        :param routing_fn: (src: int, dst: int) -> Netif | None.
                           Hook override. Takes two IPs in numeric format and
                           returns a Netif instance or None. In case None is
                           returned, the default lwIP routing function will
                           be used.
        """

        @ffi.callback("struct netif *(const void *src, const void *dest)")
        def hook(src, dst):
            srcip = ffi.cast("const ip4_addr_t*", src)
            dstip = ffi.cast("const ip4_addr_t*", dst)
            if output := routing_fn(srcip.addr, dstip.addr):
                return output.native_netif()
            return ffi.NULL

        self.routing_hook = hook  # Prevent GC from taking it
        self.lwip.set_ip4_route_fn_override(hook)


def _load_lwip(so_path: str | None = None, private: bool = False):
    """
    Creates a new instance of the lwIP shared object library.

    :param so_path: Path to `liblwip.so`. It can be an absolute or
                    relative path. If no path is given, will try to
                    use a path in the environment variable LIBLWIP_PATH.
                    If that variable is not set, it will try to use
                    "liblwip.so" as path.
    :param private: If true, load a separate instance of the library

    :return: A new instance of the shared object.
    """
    if not so_path:
        so_path = os.environ.get("LIBLWIP_PATH") or "./liblwip.so"

    if private:
        # You may be wondering "why isn't this code just `dlopen(path)`?"
        #
        # Well, lwIP uses global variables for context and loading the library
        # in the usual way would cause different instances to share those global
        # variables.
        #
        # We want to avoid that to be able to simulate different devices in
        # different threads of the same process.
        #
        # So we are left with, at least, two choices:
        # - Using RTLD_PRIVATE (only Linux, not supported by most dlopen
        #   wrappers, cffi is not an exception).
        # - Tricking dlopen into thinking that it's actually loading a different
        #   library each time.
        # It turns out that tricking dlopen is actually quite easy. The only thing
        # needed is for the file to be in a different path. So we are taking this
        # approach:
        #  - Create a named temporary file
        #  - Copy the shared object to the temporary file
        #  - dlopen the temporary file
        #  - And once it's been dlopen'd it's already in memory so we can delete the temporary file
        # It has some caveats, though:
        #  - It requires writing a temporary file
        #  - It loads the same binary in memory several times
        # But since the library is rather small (about 1MB in size) this is no big deal.
        with open(so_path, "rb") as lib, NamedTemporaryFile() as tmplib:
            tmplib.write(lib.read())
            tmplib.flush()
            lwip = ffi.dlopen(tmplib.name)
            return lwip
    
    return ffi.dlopen(so_path)
