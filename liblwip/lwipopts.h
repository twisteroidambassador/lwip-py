#ifndef LWIP_LWIPOPTS_H
#define LWIP_LWIPOPTS_H


#define NO_SYS                          0  /* default */

#define LWIP_TCPIP_CORE_LOCKING         1  /* default */
#define LWIP_TCPIP_CORE_LOCKING_INPUT   1

#define MEM_LIBC_MALLOC                 1
#define MEMP_MEM_MALLOC                 1
#define MEM_USE_POOLS                   0  /* default */
/* should be no need to set memory details like MEM_SIZE, MEM_ALIGNMENT when using MALLOC
*/

#define MEMP_NUM_RAW_PCB                1024
#define MEMP_NUM_UDP_PCB                1024
#define MEMP_NUM_TCP_PCB                1024
#define MEMP_NUM_TCP_PCB_LISTEN         128
#define MEMP_NUM_NETCONN                1024

#define LWIP_ARP                        1  /* default */
#define ARP_TABLE_SIZE                  128
#define ARP_QUEUEING                    1
#define ARP_QUEUE_LEN                   10

#define LWIP_IPV4                       1  /* default */
#define IP_FORWARD                      1

#define LWIP_RAW                        1

#define LWIP_DHCP                       1

#define LWIP_IGMP                       1

#define LWIP_DNS                        1
#define DNS_TABLE_SIZE                  16
#define LWIP_DNS_SUPPORT_MDNS_QUERIES   1

#define LWIP_UDP                        1  /* default */
#define LWIP_NETBUF_RECVINFO            1

#define LWIP_TCP                        1  /* default */
#define TCP_WND                         0xffff0
#define LWIP_TCP_SACK_OUT               1
#define TCP_MSS                         1460
#define TCP_SND_BUF                     (128 * TCP_MSS)
#define TCP_LISTEN_BACKLOG              1
#define LWIP_WND_SCALE                  1
#define TCP_RCV_SCALE                   4
#define TCP_SNDLOWAT                    (0xffff - (4*TCP_MSS) - 1)

#define LWIP_NETIF_API                  1
#define LWIP_NETIF_STATUS_CALLBACK      1
#define LWIP_NETIF_EXT_STATUS_CALLBACK  1
#define LWIP_NETIF_LINK_CALLBACK        1
#define LWIP_NETIF_REMOVE_CALLBACK      1
#define LWIP_NETIF_HWADDRHINT           1

#define LWIP_HAVE_LOOPIF                1
#define LWIP_LOOPIF_MULTICAST           1
#define LWIP_NETIF_LOOPBACK             1
#define LWIP_LOOPBACK_MAX_PBUFS         16

#define LWIP_NETCONN_SEM_PER_THREAD     1
#define LWIP_NETCONN_FULLDUPLEX         1

#define LWIP_SOCKET                     1  /* default */
#define LWIP_COMPAT_SOCKETS             0
#define LWIP_POSIX_SOCKETS_IO_NAMES     0
#define LWIP_TCP_KEEPALIVE              1
#define LWIP_SO_SNDTIMEO                1
#define LWIP_SO_RCVTIMEO                1
#define LWIP_SO_RCVBUF                  1
#define LWIP_SO_LINGER                  1
#define SO_REUSE                        1
#define LWIP_SOCKET_SELECT              1  /* default */
#define LWIP_SOCKET_POLL                1  /* default */

#define LWIP_IPV6                       1
#define LWIP_IPV6_NUM_ADDRESSES         7
#define LWIP_IPV6_FORWARD               1
#define MEMP_NUM_MLD6_GROUP             16
#define LWIP_ND6_NUM_NEIGHBORS          127
#define LWIP_ND6_NUM_DESTINATIONS       127
#define LWIP_IPV6_DHCP6                 1

/* Only send complete packets to the device */
#define LWIP_NETIF_TX_SINGLE_PBUF 1
/* SLAAC support and other IPv6 stuff */
#define IPV6_FRAG_COPYHEADER          1
/* Throughput settings */
#define LWIP_CHECKSUM_ON_COPY   1
/* Don't abort the whole stack when an error is detected */
#define LWIP_NOASSERT_ON_ERROR   1


#if !defined(NO_SYS) || !NO_SYS /* default is 0 */
void sys_check_core_locking(void);
#define LWIP_ASSERT_CORE_LOCKED() sys_check_core_locking()
#endif

#ifndef LWIP_PLATFORM_ASSERT
/* Define LWIP_PLATFORM_ASSERT to something to catch missing stdio.h includes */
void lwip_example_app_platform_assert(const char *msg, int line, const char *file);
#define LWIP_PLATFORM_ASSERT(x) lwip_example_app_platform_assert(x, __LINE__, __FILE__)
#endif

#define LWIP_HOOK_IP4_ROUTE_SRC custom_ip4_route_src_hook

struct netif *custom_ip4_route_src_hook(const void *src, const void *dest);

#endif /* LWIP_LWIPOPTS_H */