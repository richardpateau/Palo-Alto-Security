# Multi-Vendor Route-Based IPsec VPN & Dynamic BGP Peering (PAN-OS ➔ Cisco IOS)

A production-grade implementation of a multi-vendor, route-based site-to-site Virtual Private Network interconnecting **Palo Alto Networks PAN-OS 11.2.5** and a **Cisco IOS / CSR1000v Router**. 

This project documents the deployment of a **Route-Based Virtual Tunnel Interface (VTI)** secured via **IKEv2 (AES-256-CBC / SHA-256 / DH Group 14)** with automated NAT-Traversal (UDP 4500), combined with dynamic **External BGP (eBGP AS 65001 ➔ AS 65000)** route exchange. Local connected subnets are dynamically redistributed, advertised, and installed into kernel forwarding tables (FIB) across zone boundaries without static routes.

Every cryptographic handshake, Security Parameter Index (SPI), BGP state machine transition, and bidirectional data-plane session was validated using live CLI state tables, kernel FIB lookups, firewall traffic logs, continuous ICMP stress testing, and wire-level Wireshark packet captures.

---

## Architecture & Multi-Vendor Peering Fabric

![Palo Alto](screenshots/vpn-draw-io.png)

| Infrastructure Node | Interface | IP Address | Security Zone / VRF | Routing Role & Autonomous System |
| :--- | :--- | :--- | :--- | :--- |
| **Palo Alto (PA-VM)** | `ethernet1/1` | `192.168.1.200/24` | `Untrust` (default VR) | Egress WAN Endpoint (IKEv2 Responder/Initiator) |
| **Palo Alto (PA-VM)** | `tunnel.1` | `10.255.255.1/30` | `VPN` (default VR) | Route-Based VTI Gateway (eBGP **AS 65001**) |
| **Palo Alto (PA-VM)** | `ethernet1/2` | `10.10.10.1/24` | `Trust` (default VR) | Corporate LAN Gateway (Advertised: `10.10.10.0/24`) |
| **Cisco Router (CSR)** | `GigabitEthernet0/0`| `192.168.254.10/24` | Global Routing Table | Remote WAN Endpoint (NAT-T UDP 4500) |
| **Cisco Router (CSR)** | `Tunnel1` | `10.255.255.2/30` | Global Routing Table | Route-Based VTI Gateway (eBGP **AS 65000**) |
| **Cisco Router (CSR)** | `Loopback0` / LAN | `172.16.50.1/24`<br>`20.20.20.1/24` | Global Routing Table | Remote Datacenter LANs (Target: `20.20.20.10`) |

---

## Cryptographic & Routing Specification

| Phase / Protocol | Parameter | Configured Value | Operational Detail |
| :--- | :--- | :--- | :--- |
| **IKEv2 (Phase 1)** | Encryption / Hash | `AES-256-CBC` / `SHA-256` | Symmetric bulk encryption & packet integrity |
| **IKEv2 (Phase 1)** | Diffie-Hellman Group | **Group 14 (2048-bit MODP)** | Secure key exchange anchor |
| **IKEv2 (Phase 1)** | Authentication | Pre-Shared Key (PSK) | `PaloAltoCiscoVPN2026!` |
| **IKEv2 (Phase 1)** | Lifetime | 28,800 seconds (8 Hours) | Re-authentication / Rekey window |
| **IPsec (Phase 2)** | Encapsulation | **ESP (Tunnel Mode)** | Payload encryption via RFC 4303 |
| **IPsec (Phase 2)** | Transform Set | `AES-256-CBC` / `HMAC-SHA256` | Data-plane encapsulation suite |
| **IPsec (Phase 2)** | Perfect Forward Secrecy | **PFS Group 14** | Ephemeral per-child-SA session keys |
| **IPsec (Phase 2)** | Lifetime | 3,600 seconds (1 Hour) | Phase 2 renegotiation window |
| **Transport** | NAT-Traversal (NAT-T) | **UDP Port 4500** | Auto-detected; floating ESP over UDP |
| **Dynamic Routing** | BGP Protocol | **eBGP (RFC 4271)** | AS 65001 (PA-VM) ➔ AS 65000 (Cisco CSR) |
| **Prefix Filtering** | Redistribution | Connected ➔ BGP Local-RIB | Injected via Redistribution Profile & Export Rule |

---

## Implementation 

### Phase 1: Cisco IOS configuration

**Interfaces**

```cisco
enable
configure terminal

interface Loopback0
 ip address 172.16.50.1 255.255.255.0
 no shutdown
exit

interface GigabitEthernet0/0
 ip address 192.168.254.10 255.255.255.0
 no shutdown
exit

interface GigabitEthernet0/1
 ip address 20.20.20.1 255.255.255.0
 no shutdown
exit
```
![Palo Alto](screenshots/cisco-ios-interfaces.png)

**IKEv2 Proposal & Policy (Phase 1)**
```cisco
crypto ikev2 proposal IKEV2-PROPOSAL
 encryption aes-cbc-256
 integrity sha256
 group 14
exit

crypto ikev2 policy IKEV2-POLICY
 proposal IKEV2-PROPOSAL
exit
```

![Palo Alto](screenshots/cisco-ios-ikev2-policy.png)

**IKEv2 Keyring & Profile**

```cisco
crypto ikev2 keyring IKEV2-KEYRING
 peer PALO-ALTO
  address 192.168.1.200
  pre-shared-key local PaloAltoCiscoVPN2026!
  pre-shared-key remote PaloAltoCiscoVPN2026!
 exit
exit

crypto ikev2 profile IKEV2-PROFILE
 match identity remote address 192.168.1.200 255.255.255.255
 identity local address 192.168.254.10
 authentication local pre-share
 authentication remote pre-share
 keyring local IKEV2-KEYRING
 lifetime 28800
exit
```
![Palo Alto](screenshots/cisco-ios-key-ring.png)

**IPsec Transform-Set & Profile (Phase 2)**

```cisco
crypto ipsec transform-set IPSEC-TS esp-aes 256 esp-sha256-hmac
 mode tunnel
exit

crypto ipsec profile IPSEC-PROFILE
 set transform-set IPSEC-TS
 set ikev2-profile IKEV2-PROFILE
 set pfs group14
exit
```

![Palo Alto](screenshots/cisco-ios-crypto-transform-set.png)

**Route-Based Virtual Tunnel Interface (VTI)**

```cisco
interface Tunnel1
 description VTI-TO-PALO-ALTO
 ip address 10.255.255.2 255.255.255.252
 ip tcp adjust-mss 1360
 tunnel source GigabitEthernet0/0
 tunnel destination 192.168.1.200
 tunnel mode ipsec ipv4
 tunnel protection ipsec profile IPSEC-PROFILE
 no shutdown
exit
```
![Palo Alto](screenshots/cisco-ios-tunnel-1.png)

**Dynamic Routing: eBGP Configuration**

```cisco
router bgp 65000
 bgp router-id 10.255.255.2
 bgp log-neighbor-changes
 network 20.20.20.0 mask 255.255.255.0
 network 172.16.50.0 mask 255.255.255.0
 neighbor 10.255.255.1 remote-as 65001
exit
```
![Palo Alto](screenshots/cisco-ios-show-router-bgp.png)

---

### Phase 2: Palo Alto Networks (PAN-OS 11.2.5) Configuration

**Create Dedicated VPN Security Zone & Tunnel Interface**

```text
set zone VPN network layer3 tunnel.1
set network interface tunnel units tunnel.1 ip 10.255.255.1/30
set network virtual-router default interface [ ethernet1/1 ethernet1/2 tunnel.1 ]
```
![Palo Alto](screenshots/creating-zone-vpn.png)

![Palo Alto](screenshots/creating-tunnel-interface-1.png)

![Palo Alto](screenshots/creating-tunnel-interface-2.png)

**Phase 1: IKE Crypto Profile & Gateway**

```text
set network profiles ike-crypto-profiles IKEV2_CSR_PROFILE hash sha256 dh-group group14 encryption aes-256-cbc lifetime hours 8
set network ike gateway IKE_GATEWAY_CSR protocol version ikev2-only
set network ike gateway IKE_GATEWAY_CSR protocol ikev2 ike-crypto-profile IKEV2_CSR_PROFILE
set network ike gateway IKE_GATEWAY_CSR authentication pre-shared-key key "PaloAltoCiscoVPN2026!"
set network ike gateway IKE_GATEWAY_CSR local-address interface ethernet1/1 ip 192.168.1.200/24
set network ike gateway IKE_GATEWAY_CSR peer-address ip 192.168.254.10
set network ike gateway IKE_GATEWAY_CSR protocol ikev2 dpd enable yes
```

![Palo Alto](screenshots/creating-ike-profile.png)

![Palo Alto](screenshots/creating-ike-gateway.png)

**Phase 2: IPsec Crypto Profile & Tunnel Object**

```text
set network profiles ipsec-crypto-profiles IPSEC_CSR_PROFILE esp authentication sha256 encryption aes-256-cbc dh-group group14 lifetime hours 1
set network ipsec tunnel IPSEC_TUNNEL_CSR tunnel-interface tunnel.1
set network ipsec tunnel IPSEC_TUNNEL_CSR auto-key ike-gateway IKE_GATEWAY_CSR
set network ipsec tunnel IPSEC_TUNNEL_CSR auto-key ipsec-crypto-profile IPSEC_CSR_PROFILE
```
![Palo Alto](screenshots/creating-ipsec-profile.png)

![Palo Alto](screenshots/creating-ip-sec-tunnel.png)

**Connected Subnet Redistribution into BGP Local-RIB**
```text
set network virtual-router default redistribution-profile LAN-REDIST priority 1 action redist filter type connect interface ethernet1/2 destination 10.10.10.0/24
set network virtual-router default protocol bgp redist-rules LAN-REDIST enable yes address-family-identifier ipv4 route-table unicast metric 10
```
![Palo Alto](screenshots/network-redistribution-profile.png)

![Palo Alto](screenshots/creating-bgp-redist.png)

**eBGP Peering Configuration (AS 65001 -> AS 65000)**
```text
set network virtual-router default protocol bgp enable yes
set network virtual-router default protocol bgp router-id 10.255.255.1
set network virtual-router default protocol bgp as 65001
set network virtual-router default protocol bgp peer-group CSR-EBGP-GROUP enable yes type external
set network virtual-router default protocol bgp peer-group CSR-EBGP-GROUP peer CSR-PEER enable yes peer-as 65000
set network virtual-router default protocol bgp peer-group CSR-EBGP-GROUP peer CSR-PEER local-address interface tunnel.1 ip 10.255.255.1/30
set network virtual-router default protocol bgp peer-group CSR-EBGP-GROUP peer CSR-PEER peer-address ip 10.255.255.2
set network virtual-router default protocol bgp peer-group CSR-EBGP-GROUP peer CSR-PEER connection-options keep-alive-interval 10 hold-time 30
set network virtual-router default protocol bgp export-rule EXPORT-PA-LAN enable yes match address-prefix 10.10.10.0/24 exact yes action allow
```
**BGP - General Tab**

![Palo Alto](screenshots/creating-bgp-peer-group.png)

**BGP Peer Group**

![Palo Alto](screenshots/creating-bgp-peer-group.png)

![Palo Alto](screenshots/creating-bgp.png)

![Palo Alto](screenshots/creating-bgp-overview.png)

**Export Rule** 

![Palo Alto](screenshots/creating-bgp-export-rule.png)

![Palo Alto](screenshots/creating-bgp-export-rule-1.png)

**Inter-Zone Security Policies**

```text
# 6. Inter-Zone Security Policies
set rulebase security rules CSR-VPN-TO-VPN from VPN to VPN source 10.255.255.0/30 destination 10.255.255.0/30 application bgp service any action allow
set rulebase security rules PA-LAN-TO-CSR-LAN from Trust to VPN source 10.10.10.0/24 destination [ 20.20.20.0/24 172.16.50.0/24 ] application any service any action allow
set rulebase security rules CSR-LAN-TO-PA-LAN from VPN to Trust source [ 20.20.20.0/24 172.16.50.0/24 ] destination 10.10.10.0/24 application any service any action allow
```
**Security Rule Overview**

![Palo Alto](screenshots/security-rule-overview.png)

**Security Rule: Palo Alto LAN ---> CSR LAN**

![Palo Alto](screenshots/creating-security-rule.png)

**Palo Alto LAN ---> CSR LAN - Source: 10.10.10.0/24**

![Palo Alto](screenshots/creating-security-rule-source.png)

**Palo Alto LAN ---> CSR LAN - Destination 20.20.20.0/24, 172.16.50.0**

![Palo Alto](screenshots/creating-security-rule-destination.png)

**Security Rule: CSR LAN ---> Palo Alto LAN**

![Palo Alto](screenshots/creating-2-security-rule.png)

**CSR LAN ---> Palo Alto LAN - Source 20.20.20.0/24, 172.16.50.0/24**

![Palo Alto](screenshots/creating-2-security-rule-source.png)

**CSR LAN ---> Palo Alto - Destination 10.10.10.10/24**

![Palo Alto](screenshots/creating-2-security-rule-destination.png)

**Security Rule: VPN Zone to VPN Zone**

![Palo Alto](screenshots/security-rule-3-general.png)

**Source: VPN Zone - Destination: VPN Zone**

![Palo Alto](screenshots/security-rule-3-source.png)

![Palo Alto](screenshots/creating-security-3-destination.png)

---

## Empirical Verification & Technical Proof

### Cryptographic Security Associations & Wire SPI Synchronization

Verifying cryptographic negotiation on both endpoints confirmed matching Security Parameter Indexes (SPIs) across the data plane:

#### Cisco IOS Crypto Telemetry (`show crypto ikev2 session` & `show crypto ipsec sa`)
```text
Router# show crypto ikev2 session
IPv4 Crypto IKEv2 Session

Session-id:1, Status:UP-ACTIVE, IKE count:1, CHILD count:1
Tunnel-id Local                 Remote                fvrf/ivrf   Status
1         192.168.254.10/4500   192.168.1.200/4500    none/none   READY
      Encr: AES-CBC, keysize: 256, PRF: SHA256, Hash: SHA256, DH Grp:14, Auth sign: PSK, Auth verify: PSK
      Child sa: local selector  0.0.0.0/0 - 255.255.255.255/65535
                remote selector 0.0.0.0/0 - 255.255.255.255/65535
                ESP spi in/out: 0xB4E8D71F / 0xBD359D70
```

![Palo Alto](screenshots/cisco-ios-show-crypto-ikev2-session.png)

```text
Router# show crypto ipsec sa 
interface: Tunnel1
    Crypto map tag: Tunnel1-head-0, local addr 192.168.254.10
   #pkts encaps: 839, #pkts encrypt: 839, #pkts digest: 839
   #pkts decaps: 514, #pkts decrypt: 514, #pkts verify: 514
   current outbound spi: 0xBD359D70
   inbound esp sas:
      spi: 0xB4E8D71F(3035158303)
        transform: esp-256-aes esp-sha256-hmac, in use settings ={Tunnel UDP-Encaps, }
        Status: ACTIVE(ACTIVE)
```
![Palo Alto](screenshots/cisco-ios-show-crypto-ipsec-sa.png)

#### Palo Alto PAN-OS Crypto Telemetry (`show vpn ike-sa` & `show vpn ipsec-sa`)
```text
admin@PA-VM> show vpn ike-sa

IKEv2 SAs
Gateway ID   Peer-Address   Gateway Name      Role SN  Algorithm           Status
--------------------------------------------------------------------------------------
1            192.168.1.172  IKE_GATEWAY_CSR   Resp 22  PSK/DH14/A256/SHA256 Established

IKEv2 IPsec Child SAs
Gateway Name     TnID  Tunnel            SPI(in)   SPI(out)  ST
--------------------------------------------------------------------------------------
IKE_GATEWAY_CSR  1     IPSEC_TUNNEL_CSR  BD359D70  B4E8D71F  Mature
```

![Palo Alto](screenshots/palo-cli-show-vpn-ike-sa.png)

```text
admin@PA-VM> show vpn ipsec-sa

GwID/client IP  TnID  Peer-Address       Tunnel(Gateway)                 SPI(in)   SPI(out)  life(Sec)
-------------------------------------------------------------------------------------------------------
1               1     192.168.1.172:4500 IPSEC_TUNNEL_CSR(IKE_GW_CSR)    BD359D70  B4E8D71F  3600
```
![Palo Alto](screenshots/palo-cli-show-vpn-ipsec-sa.png)

> **Cryptographic Synchronization Proof:** 
> * **Cisco Inbound SPI:** `0xB4E8D71F` = **Palo Alto Outbound SPI:** `B4E8D71F`
> * **Cisco Outbound SPI:** `0xBD359D70` = **Palo Alto Inbound SPI:** `BD359D70`
> * Both peers negotiated **NAT-Traversal over UDP port 4500**, ensuring zero dropped ESP frames across intermediate transit devices.

**Palo Alto GUI Tunnel Status**

![Palo Alto](screenshots/network-ipsec-tunnels-status.png)

**Palo Alto GUI Tunnel Info**

![Palo Alto](screenshots/network-ipsec-tunnels-info.png)

---

### Dynamic eBGP Peering & Route Distribution

#### BGP Session Establishment (Cisco CSR)
```text
Router# show ip bgp summary
BGP router identifier 10.255.255.2, local AS number 65000
BGP table version is 8, main routing table version 8
3 network entries using 432 bytes of memory

Neighbor        V    AS    MsgRcvd MsgSent   TblVer  InQ OutQ Up/Down  State/PfxRcd
10.255.255.1    4    65001      40      39        8    0    0 00:15:49            1
```
![Palo Alto](screenshots/cisco-ios-sh-bgp-summary.png)

```text
Router# show ip bgp
   Network          Next Hop            Metric LocPrf Weight Path
*> 10.10.10.0/24    10.255.255.1                             0 65001 i
*> 20.20.20.0/24    0.0.0.0                  0         32768 i
*> 172.16.50.0/24   0.0.0.0                  0         32768 i
```
* **Result:** Cisco CSR successfully established eBGP with neighbor `10.255.255.1` and learned `10.10.10.0/24` with AS-Path `65001`.

![Palo Alto](screenshots/cisco-ios-sh-ip-bgp.png)

#### BGP Advertisement & Forwarding Table Installation (Palo Alto)
Verifying prefix advertisement to the Cisco peer:
```text
admin@PA-VM> show routing protocol bgp rib-out

VIRTUAL ROUTER: default (id 1)
Prefix          Nexthop         Peer      Originator  Adv Status  Aggr Status  AS-Path
10.10.10.0/24   10.255.255.1    CSR-PEER  0.0.0.0     advertised  no aggr      65001
total routes shown: 1
```
Verifying FIB table installation in the PAN-OS kernel (`show routing fib`):
* `20.20.20.0/24` ➔ Next Hop: **`10.255.255.2`** | Interface: **`tunnel.1`** | Flags: **`ug`** (Up, Gateway)
* `172.16.50.0/24` ➔ Next Hop: **`10.255.255.2`** | Interface: **`tunnel.1`** | Flags: **`ug`** (Up, Gateway)

![Palo Alto](screenshots/palo-cli-show-routing-protocol-bgp-rib-out.png)

**GUI**

![Palo Alto](screenshots/palo-alto-virtual-router-routers.png)

**System Logs**

![Palo Alto](screenshots/monitor-system-logs-bgp-established.png)

---

### Wire-Level Protocol Analysis (Wireshark Traces)

Live packet sniffing was executed on the transit link to document cryptographic and routing frames:

#### A. IKEv2 Negotiation Handshake
* **Frames 78–125:** `IKE_SA_INIT` request/response exchanges negotiating crypto suites, nonces, and Diffie-Hellman Group 14 key exchange parameters.
* **Frames 181–182:** `IKE_AUTH` encrypted exchanges validating Pre-Shared Key identities (`PaloAltoCiscoVPN2026!`) and instantiating the Child IPsec SA.
* **Frames 198+:** `INFORMATIONAL` keepalive exchanges maintaining session liveness.

![Palo Alto](screenshots/wireshark-init-auth-exchange.png)

#### B. ESP Tunnel Encapsulation
* Packet captures filtered on `esp` confirmed all transit payload traffic (BGP keepalives and ICMP test streams) was encapsulated inside IP protocol 50 headers.
* Wireshark decodes confirmed the active SPI field: **`SPI=0xb4e8d71f`**, matching the established child SA.

![Palo Alto](screenshots/wireshark-esp-filter.png)

---

### End-to-End Data Plane Verification

From the internal corporate workstation (`10.10.10.10`), continuous ICMP echo streams were initiated across the fabric to the remote datacenter network (`20.20.20.10`):

```bash
rich@rich-iMac:~$ ping 20.20.20.10
PING 20.20.20.10 (20.20.20.10) 56(84) bytes of data.
64 bytes from 20.20.20.10: icmp_seq=3087 ttl=62 time=21.1 ms
64 bytes from 20.20.20.10: icmp_seq=3088 ttl=62 time=19.4 ms
64 bytes from 20.20.20.10: icmp_seq=3089 ttl=62 time=19.7 ms
64 bytes from 20.20.20.10: icmp_seq=3090 ttl=62 time=10.7 ms
...
64 bytes from 20.20.20.10: icmp_seq=3127 ttl=62 time=27.5 ms
```
* **Performance:** Sustained zero packet loss across 40+ consecutive sequences with sub-30ms round-trip times.

![Palo Alto](screenshots/10.10.10.10-pings-20.20.20.10.png)

### Hop-by-Hop Encrypted Path Verification (Traceroute Diagnostics)

To verify deterministic packet transit and prove traffic traverses the encrypted VTI tunnel rather than leaking onto the public underlay, a traceroute was executed from the remote datacenter client (**Alpine Linux PC** on `20.20.20.0/24`) targeting the internal corporate workstation (**`10.10.10.10`** in the `Trust` zone):

```bash
localhost:~# traceroute 10.10.10.10
traceroute to 10.10.10.10 (10.10.10.10), 30 hops max, 46 byte packets
 1  20.20.20.1 (20.20.20.1)  7.868 ms  9.108 ms  8.581 ms
 2  10.255.255.1 (10.255.255.1)  23.218 ms  19.400 ms  14.790 ms
 3  10.10.10.10 (10.10.10.10)  15.738 ms  28.775 ms  22.132 ms
```
![Palo Alto](screenshots/traceroute-20.20.20.20-to-10.10.10.10.png)

**Tunnel IP Address Verification**

![Palo Alto](screenshots/palo-tunnel-1-ip-address.png)

---

| Hop | IP Address | Device & Interface | Architectural Role & Proof |
| :---: | :--- | :--- | :--- |
| **1** | `20.20.20.1` | **Cisco CSR (`GigabitEthernet2`)** | **Local Default Gateway:** Packet egresses the remote client LAN and enters the Cisco router's routing table. |
| **2** | `10.255.255.1` | **Palo Alto PA-VM (`tunnel.1`)** | **Encrypted VTI Ingress:** Proves the Cisco router matched the dynamic BGP prefix (`10.10.10.0/24 via 10.255.255.1`), encapsulated the frame inside ESP (`0xB4E8D71F`), and delivered it across the IPsec tunnel to the Palo Alto's tunnel interface. |
| **3** | `10.10.10.10` | **Corporate Workstation (`eth0`)** | **Final Destination:** The PA-VM evaluated security policy `CSR-LAN-TO-PA-LAN` (Zone `VPN` ➔ Zone `Trust`), permitted the transit, and forwarded the packet out `ethernet1/2` to the host. |

#### Traffic Monitor Log Verification
* **Outbound (`Trust` ➔ `VPN`):** `10.10.10.10` ➔ `20.20.20.10` | App: `ping` | Action: `allow` | Rule: **`PA-LAN-TO-CSR-LAN`**.
* **Inbound (`VPN` ➔ `Trust`):** `20.20.20.10` ➔ `10.10.10.10` | App: `ping` / `traceroute` | Action: `allow` | Rule: **`CSR-LAN-TO-PA-LAN`**.
* **Control-Plane (`VPN` ➔ `VPN`):** `10.255.255.1:179` ➔ `10.255.255.2:179` | App: `bgp` | Action: `allow` | Rule: **`CSR-VPN-TO-VPN`**.

**Outbound (Trust to VPN)**

![Palo Alto](screenshots/monitor-traffic-logs-trust-to-vpn.png)

**Inbound (VPN to Trust)**

![Palo Alto](screenshots/monitor-traffic-logs-vpn-to-trust.png)

**Control-Plane (VPN to VPN)**

![Palo Alto](screenshots/monitor-traffic-logs-vpn-to-vpn.png)

**(VPN to VPN) Detailed Log**

![Palo Alto](screenshots/monitor-traffic-logs-vpn-to-vpn-detailed-logs.png)

---

## Key Artifact Index

A curated index of the primary engineering proofs, packet traces, and configuration captures:

| Artifact File | Category | Technical Proof & Validation |
| :--- | :--- | :--- |
| **`cisco-crypto-ikev2-session.png`** | Cisco Telemetry | `show crypto ikev2 session` displaying active IKEv2 SA, DH Group 14, and SPIs. |
| **`cisco-crypto-ipsec-sa.png`** | Cisco Telemetry | `show crypto ipsec sa` displaying 839 encrypted and 514 decrypted packets on Tunnel1. |
| **`cisco-bgp-summary-established.png`**| Cisco Telemetry | `show bgp sum` confirming peer `10.255.255.1` (AS 65001) in state `Established`. |
| **`cisco-ip-bgp-table-pfx.png`** | Cisco Routing | `show ip bgp` displaying route `10.10.10.0/24` learned dynamically from Palo Alto. |
| **`pa-ike-crypto-profile.png`** | PAN-OS Config | IKE Crypto Profile `IKEV2_CSR_PROFILE` enforcing AES-256-CBC, SHA-256, DH Group 14. |
| **`pa-ipsec-crypto-profile.png`** | PAN-OS Config | IPsec Crypto Profile `IPSEC_CSR_PROFILE` enforcing ESP, AES-256, SHA-256, PFS DH14. |
| **`pa-tunnel-interface-config.png`** | PAN-OS Config | Assigning `tunnel.1` (`10.255.255.1/30`) to virtual router `default` and zone `VPN`. |
| **`pa-ipsec-tunnel-active-gui.png`** | PAN-OS Status | IPsec Tunnels monitor displaying green operational indicators for IKE and Tunnel status. |
| **`pa-cli-show-vpn-ike-sa.png`** | PAN-OS CLI | `show vpn ike-sa` confirming mature child SA and SPIs `BD359D70` / `B4E8D71F`. |
| **`pa-cli-show-vpn-ipsec-sa.png`** | PAN-OS CLI | `show vpn ipsec-sa` confirming active SA lifetime and hardware tunnel binding. |
| **`pa-bgp-redistribution-lan.png`** | PAN-OS Routing | Redistribution profile `LAN-REDIST` injecting connected LAN `10.10.10.0/24` into BGP. |
| **`pa-cli-bgp-rib-out-adv.png`** | PAN-OS CLI | `show routing protocol bgp rib-out` verifying prefix `10.10.10.0/24` advertised to peer. |
| **`pa-fib-routes-installed.png`** | PAN-OS Routing | Forwarding table confirming dynamic BGP routes `20.20.20.0/24` installed via `tunnel.1`. |
| **`pa-security-rules-vpn-lan.png`** | Security Policy | Inter-zone policies permitting bidirectional traffic between `Trust` and `VPN`. |
| **`wireshark-ikev2-handshake.png`** | Wire Trace | Packet trace capturing `IKE_SA_INIT` and `IKE_AUTH` exchange sequences. |
| **`wireshark-esp-encapsulation.png`**| Wire Trace | Packet trace capturing ESP-encapsulated payloads matching `SPI=0xb4e8d71f`. |
| **`traffic-log-interzone-traffic.png`**| Telemetry Log | Traffic monitor confirming end-to-end ping flows between `Trust` and `VPN` zones. |
| **`client-ping-continuous-proof.png`** | Data Plane Proof | Workstation terminal confirming continuous ping to `20.20.20.10` with zero packet loss. |

---
