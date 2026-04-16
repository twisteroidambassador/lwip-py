from lwip.ffi import ffi
from lwip.inet import ip4_addr, ip6_addr
from lwip.lwip_error import check_ret
from lwip.defs import PBUF_RAM, PBUF_RAW, NetifFlags
from lwip.tcpip import TcpIpCoreLock

# Maximum number of buffers in a pbuf chain to concat before giving up.
MAX_PBUF_FRAGMENTS = 1000


class Netif:
    """
    Wrapper for lwIP `struct netif` objects.
    """

    def __init__(self, lwip_instance, driver):
        """
        Private constructor -- use Lwip.create_netif instead.
        """
        self.lwip = lwip_instance
        self.driver = driver
        self.netif = ffi.new("struct netif*")
        self.handle = ffi.new_handle(self)

    def native_netif(self):
        """
        Returns the underlying `struct netif` object.
        """
        return self.netif
    
    @property
    def hwaddr(self) -> bytes:
        """
        The hardware address for this interface.
        """
        return ffi.buffer(self.netif.hwaddr)[:self.netif.hwaddr_len]
    
    @hwaddr.setter
    def hwaddr(self, hw_addr: bytes) -> None:
        if len(hw_addr) > ffi.sizeof(self.netif.hwaddr):
            raise ValueError('Exceeded max length for hardware address')
        ffi.memmove(ffi.addressof(self.netif.hwaddr), hw_addr, len(hw_addr))
        self.netif.hwaddr_len = len(hw_addr)
    
    @property
    def flags(self) -> NetifFlags:
        """The flags for this netif instance."""
        return NetifFlags(self.netif.flags)
    
    @flags.setter
    def flags(self, new_flags: int) -> None:
        self.netif.flags = new_flags

    def add(self, ip: str, netmask: str, gateway: str):
        """
        See netif_add.

        Sets the IP, network mask and gateway of the interface and registers
        it in the lwIP stack. This will trigger lwip_on_init in the driver
        implementation.
        """
        with TcpIpCoreLock(self.lwip):
            self.lwip.netif_add(
                self.netif,
                ip4_addr(ip),
                ip4_addr(netmask),
                ip4_addr(gateway),
                self.handle,
                _netif_init,
                self.lwip.tcpip_input,
            )

    def remove(self):
        """
        See netif_remove.

        Removes the interface from the stack. Note that this will not
        destroy the interface, it can be later added again with the
        same or a different IP address.
        """
        with TcpIpCoreLock(self.lwip):
            self.lwip.netif_remove(self.netif)

    def set_up(self):
        """
        See netif_set_up.

        Enables the interface so it can handle traffic.
        """
        with TcpIpCoreLock(self.lwip):
            self.lwip.netif_set_up(self.netif)
    
    def set_down(self):
        """See netif_set_down."""
        with TcpIpCoreLock(self.lwip):
            self.lwip.netif_set_down(self.netif)

    def set_link_up(self):
        """
        See netif_set_link_up.

        Notifies the stack that the link in this interface has become active.
        """
        with TcpIpCoreLock(self.lwip):
            self.lwip.netif_set_link_up(self.netif)
    
    def set_link_down(self):
        """See netif_set_link_down."""
        with TcpIpCoreLock(self.lwip):
            self.lwip.netif_set_link_down(self.netif)

    def set_default(self):
        """
        See netif_set_default.

        Marks the interface as the default output interface. Packets that do not match
        any routing rule will be sent through this interface.
        """
        with TcpIpCoreLock(self.lwip):
            self.lwip.netif_set_default(self.netif)

    def input(self, payload: bytes):
        """
        See struct netif::input.

        Sends an IP packet to the lwIP network stack.

        :param payload: raw IP packet
        """
        pbuf = self.lwip.pbuf_alloc(PBUF_RAW, len(payload), PBUF_RAM)
        ffi.memmove(pbuf.payload, payload, len(payload))
        return self.netif.input(pbuf, self.netif)
    
    def create_ip6_linklocal_address(self, from_mac_48bit: bool = True) -> None:
        """See netif_create_ip6_linklocal_address."""
        with TcpIpCoreLock(self.lwip):
            self.lwip.netif_create_ip6_linklocal_address(self.netif, int(from_mac_48bit))
    
    def add_ipv6_address(self, address: str, zone: int = 0) -> int:
        """See netif_add_ip6_address."""
        chosen_index = ffi.new('s8_t *')
        new_addr = ip6_addr(address, zone)
        with TcpIpCoreLock(self.lwip):
            check_ret('netif_add_ip6_address', self.lwip.netif_add_ip6_address(self.netif, new_addr, chosen_index))
        return chosen_index[0]


@ffi.callback("err_t(struct netif*)")
def _netif_init(netif):
    """
    Generic handler for netif_init event.

    Sets up the netif structure with information from the driver and
    calls driver.lwip_on_init
    """
    self = ffi.from_handle(netif.state)

    prefix = self.driver.get_prefix()
    assert len(prefix) == 2, "Prefix must be no longer than 2 bytes"
    assert isinstance(prefix, bytes), "Prefix must be a `bytes` object"

    netif.hwaddr_len = 0
    netif.mtu = self.driver.get_mtu()
    ffi.memmove(netif.name, prefix, 2)
    netif.output = _netif_output
    netif.output_ip6 = _netif_output_ip6

    return self.driver.lwip_on_init(self)


def _pbuf_to_bytes(pbuf) -> bytes:
    payload = []
    for i in range(MAX_PBUF_FRAGMENTS):
        payload.append(ffi.buffer(ffi.cast("char*", pbuf.payload), pbuf.len)[:])

        if pbuf.len == pbuf.tot_len:
            break

        pbuf = pbuf.next
        if not pbuf:
            break
    return b''.join(payload)


@ffi.callback("err_t(struct netif*, struct pbuf*, ip4_addr_t*)")
def _netif_output(netif, pbuf, ip_addr):
    """
    Generic handler for netif_output callback.

    Converts the packet into a Python `bytes` object and calls driver.lwip_on_output
    """
    # Reconstruct packet into Python `bytes`
    payload = _pbuf_to_bytes(pbuf)
    addr = ffi.buffer(ffi.addressof(ip_addr, 'addr'))[:]

    self = ffi.from_handle(netif.state)
    return self.driver.lwip_on_output(payload, addr)


@ffi.callback("err_t(struct netif*, struct pbuf*, const ip6_addr_t *)")
def _netif_output_ip6(netif, pbuf, ip6_addr):
    """Generic handler for netif_output_ip6 callback."""
    payload = _pbuf_to_bytes(pbuf)
    addr = ffi.buffer(ffi.addressof(ip6_addr, 'addr'))[:]

    self = ffi.from_handle(netif.state)
    return self.driver.lwip_on_output_ip6(payload, addr, ip6_addr.zone)