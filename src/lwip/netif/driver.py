class NetifDriver:
    def lwip_on_init(self, netif):
        """
        Called by lwIP when the network card has been added to the stack.
        This method will be called only once, right after creation of the
        `netif` object.

        The driver implementation should keep a reference to the `netif`
        object in order to:
            - Set the IP / mask / gateway of the interface
            - Tell lwIP that a link address or a network address has been
              provided (up / link_up)
            - Ingress a packet to the stack (netif.input)

        :return: ERR_OK if success, ERR_* on error
        """
        raise NotImplementedError

    def lwip_on_output(self, payload: bytes, dst_ip: bytes):
        """
        Called by lwIP when it needs to output an IPv4 packet through this
        interface

        `payload` is the complete IP packet with headers that should
        be sent to `dst_ip`.

        :return: ERR_OK if success, ERR_* on error
        """
        raise NotImplementedError
    
    def lwip_on_outpu_ip6(self, payload: bytes, dst_ip: bytes, zone: int):
        """
        Called by lwIP when it needs to output an IPv6 packe through this interface.
        """
        raise NotImplementedError

    def get_mtu(self) -> int:
        """
        Returns the Maximum Transfer Unit (MTU) for the interface, in bytes
        """
        return 1500

    def get_prefix(self) -> bytes:
        """
        Returns a 2-character prefix that identifies this interface.

        Note that the returned value must be a `bytes` object with ASCII
        characters.
        """
        return b"py"
