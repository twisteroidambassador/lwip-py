import enum


class NetifFlags(enum.IntFlag):
    UP = 0x01
    BROADCAST = 0x02
    LINK_UP = 0x04
    ETHARP = 0x08
    ETHERNET = 0x10
    IGMP = 0x20
    MLD6 = 0x40