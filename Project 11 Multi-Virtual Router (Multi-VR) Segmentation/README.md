# Multi-Virtual Router (Multi-VR) Segmentation & Inter-VR Route Leaking (`next-vr`)

A production-grade implementation of **Routing Virtualization (Virtual Routers / VRF-lite)** and controlled **Inter-VR Route Leaking (`next-vr`)** on Palo Alto Networks PAN-OS 11.2.5. This project documents the complete architectural partitioning of a single physical firewall into three independent routing domains servicing an **802.1Q VLAN Trunk**:

1. **`VR-Perimeter` (External / Untrust):** Anchors physical WAN interface `ethernet1/1` (`192.168.1.200/24` and VIP `192.168.1.201`) and upstream ISP default routes.
2. **`VR-Corporate` (Internal / Trust):** Anchors internal corporate workloads on subinterface `ethernet1/2.10` (VLAN 10: `10.10.10.1/24`).
3. **`VR-Guest` (Isolated Tenant / DMZ):** Anchors untrusted guest workstations on subinterface `ethernet1/2.50` (VLAN 50: `10.50.50.1/24`).

The design proves **strict architectural tenant isolation**: `VR-Guest` and `VR-Corporate` maintain separate Forwarding Information Bases (FIB) with zero internal route visibility. Both tenants dynamically leak default routes to `VR-Perimeter` via internal **`next-vr`** pointers to access the internet, while cross-tenant lateral movement between Guest and Corporate is blocked at the routing layer before security policies are even evaluated.

---

## Architecture & Multi-VR Routing Topology

![Palo Alto](screenshots/vrf-draw-io.png)

---

## Routing Virtualization Specifications

| Virtual Router | Subnet / Role | Interface Binding | Security Zone | Default Egress Route | Return Route Pointers |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`VR-Perimeter`** (ID: 2) | `192.168.1.0/24` (WAN) | `ethernet1/1` | `Untrust` | `0.0.0.0/0` via IP `192.168.1.1` | `10.10.10.0/24` ➔ `next-vr: VR-Corporate`<br>`10.50.50.0/24` ➔ `next-vr: VR-Guest` |
| **`VR-Corporate`** (ID: 3) | `10.10.10.0/24` (Corp LAN) | `ethernet1/2.10` (Tag 10) | `Trust` | `0.0.0.0/0` ➔ `next-vr: VR-Perimeter` | Connected local routes only (No Guest route) |
| **`VR-Guest`** (ID: 4) | `10.50.50.0/24` (Guest LAN) | `ethernet1/2.50` (Tag 50) | `Guest` | `0.0.0.0/0` ➔ `next-vr: VR-Perimeter` | Connected local routes only (No Corporate route) |

---

## Multi-Phase Implementation

### Phase 1: Cisco Physical Switch 802.1Q Trunking
Configured the physical switch (`PHYSICAL-SW`) to multiplex both corporate and guest VLANs across an 802.1Q trunk into the firewall:

```cisco
PHYSICAL-SW# show running-config | section interface
interface GigabitEthernet1/0/1
 switchport trunk allowed vlan 1,10,50
 switchport mode trunk
!
interface GigabitEthernet1/0/3
 switchport access vlan 50
 switchport mode access
 spanning-tree portfast
!
interface GigabitEthernet1/0/4
 switchport access vlan 10
 switchport mode access
 spanning-tree portfast
```
![Palo Alto](screenshots/switch-show-run-section-interface.png)

### Phase 2: PAN-OS Subinterfaces & Security Zones
1. **Corporate Subinterface (`ethernet1/2.10`):**
   * Tag: `10` | IP: `10.10.10.1/24` | Virtual Router: `VR-Corporate` | Zone: `Trust`.
2. **Guest Subinterface (`ethernet1/2.50`):**
   * Tag: `50` | IP: `10.50.50.1/24` | Virtual Router: `VR-Guest` | Zone: `Guest`.
3. **Perimeter Interface (`ethernet1/1`):**
   * Untagged | IP: `192.168.1.200/24`, VIP `192.168.1.201/32` | Virtual Router: `VR-Perimeter` | Zone: `Untrust`.

**Creating Subinterface - Corporate**

![Palo Alto](screenshots/creating-sub-interface-corporate.png)

**Creating Subinterface - Corporate IPv4**

![Palo Alto](screenshots/creating-sub-interface-corporate-ipv4.png)

**Creating Subinterface - Guest**

![Palo Alto](screenshots/creating-sub-interface-guest.png)

**Creating Subinterface - Guest IPv4**

![Palo Alto](screenshots/creating-sub-interface-guest-ipv4.png)

**Creating Zone - Guest**

![Palo Alto](screenshots/creating-zone-layer-3-.png)

### Phase 3: Virtual Router Partitioning & `next-vr` Leaking
1. **`VR-Corporate` (Routing Table ID: 3):**
   * Created static route `Corp-to-Perimeter-VR`:
     * Destination: `0.0.0.0/0` ➔ Next Hop: **`Next VR: VR-Perimeter`**.
2. **`VR-Guest` (Routing Table ID: 4):**
   * Created static route `Guest-to-Perimeter-VR`:
     * Destination: `0.0.0.0/0` ➔ Next Hop: **`Next VR: VR-Perimeter`**.
3. **`VR-Perimeter` (Routing Table ID: 2):**
   * Route `Default-to-ISP`: `0.0.0.0/0` ➔ Next Hop IP: `192.168.1.1` (`ethernet1/1`).
   * Route `Return-to-Corp-LAN`: `10.10.10.0/24` ➔ Next Hop: **`Next VR: VR-Corporate`**.
   * Route `Return-to-Guest-LAN`: `10.50.50.0/24` ➔ Next Hop: **`Next VR: VR-Guest`**.

**VR-Corporate - Router Settings**

![Palo Alto](screenshots/creating-vr-corporate-router-settings.png)

**VR-Corporate - Static Route**

![Palo Alto](screenshots/creating-vr-corporate-static-route-1.png)

**VR-Perimeter - Routing Settings**

![Palo Alto](screenshots/creating-vr-perimeter-router-settings.png)

**Creating VR-Perimeter - Static Route 1**

![Palo Alto](screenshots/creating-vr-perimeter-static-route-1.png)

**Creating VR-Perimeter - Static Route 2**

![Palo Alto](screenshots/creating-vr-perimeter-static-route-2.png)

**Creating VR-Perimeter - Static Route 3**

![Palo Alto](screenshots/creating-vr-perimeter-static-route-3.png)

**Creating VR-Perimeter - Route Overview**

![Palo Alto](screenshots/creating-vr-perimeter-static-route-overview.png)

**VR-Guest - Routing Settings**

![Palo Alto](screenshots/creating-vr-guest-routing-settings.png)

**VR-Guest - Static Route**

![Palo Alto](screenshots/creating-vr-guest-static-route.png)


### Phase 4: Inter-VR NAT & Security Policies
* **Dynamic PAT (`Policies > NAT`):** Rule `LAN-to-Internet-NAT` updated with Source Zones: **`Trust`** and **`Guest`** ➔ Destination Zone: **`Untrust`**, translating to `ethernet1/1` (`192.168.1.200`).
* **Security Rulebase:**
  * `Allow-Web-Browsing`: Permits `Trust` ➔ `Untrust` and `Guest` ➔ `Untrust` for `ssl` and `web-browsing`.
  * `Test-Guest-to-Corporate-DENY`: Defense-in-depth rule explicitly denying `Guest` ➔ `Trust` with action `Deny`.

![Palo Alto](screenshots/adding-guest-to-nat-policy.png)

---

## Empirical Verification & Data-Plane Proof

### 1. Independent Routing Table (FIB) Audits

Verifying the routing tables from the PA-VM CLI confirmed complete separation across the three Virtual Routers:

#### A. Corporate Virtual Router (`VR-Corporate`)
```text
admin@PA-VM> show routing route virtual-router VR-Corporate

VIRTUAL ROUTER: VR-Corporate (id 3)
==========
destination      nexthop           metric flags age interface          next-AS
0.0.0.0/0        vr VR-Perimeter   10     A S       VR-Corporate/i3
10.10.10.0/24    10.10.10.1        0      A C       ethernet1/2.10
10.10.10.1/32    0.0.0.0           0      A H
total routes shown: 3
```
* **Proof:** `VR-Corporate` possesses zero routes for `10.50.50.0/24` (Guest).

![Palo Alto](screenshots/show-routing-route-virtual-router-vr-corporate.png)

#### B. Guest Virtual Router (`VR-Guest`)
```text
admin@PA-VM> show routing route virtual-router VR-Guest

VIRTUAL ROUTER: VR-Guest (id 4)
==========
destination      nexthop           metric flags age interface          next-AS
0.0.0.0/0        vr VR-Perimeter   10     A S       VR-Guest/i3
10.50.50.0/24    10.50.50.1        0      A C       ethernet1/2.50
10.50.50.1/32    0.0.0.0           0      A H
total routes shown: 3
```
* **Proof:** `VR-Guest` possesses zero routes for `10.10.10.0/24` (Corporate).

![Palo Alto](screenshots/show-routing-route-virtual-router-vr-guest.png)

#### C. Perimeter Gateway Virtual Router (`VR-Perimeter`)
```text
admin@PA-VM> show routing route virtual-router VR-Perimeter

VIRTUAL ROUTER: VR-Perimeter (id 2)
==========
destination      nexthop           metric flags age interface          next-AS
0.0.0.0/0        192.168.1.1       10     A S       ethernet1/1
10.10.10.0/24    vr VR-Corporate   10     A S       VR-Perimeter/i3
10.50.50.0/24    vr VR-Guest       10     A S       VR-Perimeter/i3
192.168.1.0/24   192.168.1.200     0      A C       ethernet1/1
total routes shown: 6
```

![Palo Alto](screenshots/show-routing-route-virtual-router-vr-permiter.png)

---

### 2. Control-Plane Recursive FIB Lookups (`test routing fib-lookup`)

Testing the kernel forwarding lookup confirmed that both isolated tenant routers resolve external public destinations through `VR-Perimeter`:

```text
admin@PA-VM> test routing fib-lookup virtual-router VR-Guest ip 8.8.8.8

runtime route lookup
virtual-router:   VR-Guest
destination:      8.8.8.8
result:
  via 192.168.1.1 interface ethernet1/1, source 192.168.1.200, metric 10

admin@PA-VM> test routing fib-lookup virtual-router VR-Corporate ip 8.8.8.8

runtime route lookup
virtual-router:   VR-Corporate
destination:      8.8.8.8
result:
  via 192.168.1.1 interface ethernet1/1, source 192.168.1.200, metric 10
```
![Palo Alto](screenshots/test-routing-fib-lookup-virtual-router-guest-and-corporate.png)

---

### 3. Outbound Internet Transit via `next-vr` Leaking

Both isolated tenants successfully communicated with external internet targets through `next-vr` route leaking and NAT:

* **Corporate Workstation (`10.10.10.10` in `VR-Corporate`):**
  ```bash
  rich@rich-iMac:~$ curl -I https://www.google.com
  HTTP/2 200
  server: gws
  ```
  
![Palo Alto](screenshots/corporate-pc-curl-google-successful.png)
  
* **Guest Workstation (`10.50.50.10` in `VR-Guest`):**
  ```bash
  rich@mx:~$ ping 8.8.8.8
  PING 8.8.8.8 (8.8.8.8) 56(84) bytes of data.
  64 bytes from 8.8.8.8: icmp_seq=1 ttl=116 time=11.0 ms
  64 bytes from 8.8.8.8: icmp_seq=2 ttl=116 time=14.2 ms
  --- 8.8.8.8 ping statistics ---
  56 packets transmitted, 56 received, 0% packet loss
  ```
  
![Palo Alto](screenshots/10.50.50.10-ping-to-google-successful.png)

**Guest** `curl -I https://www.google.com`

![Palo Alto](screenshots/guest-pc-successful-curl.png)

* **Traffic Log Verification:** Monitor logs confirmed bidirectional sessions:
  * `10.10.10.10` ➔ `Trust` to `Untrust` (Rule: `Allow-Web-Browsing`, Action: `allow`).
  * `10.50.50.10` ➔ `Guest` to `Untrust` (Rule: `Allow-Web-Browsing`, Action: `allow`).

**Corporate**

![Palo Alto](screenshots/monitor-traffic-logs-corporate-pc.png)

**Guest**

![Palo Alto](screenshots/monitor-traffic-logs-guest-pc.png)

---

### 4. Architectural Tenant Isolation Proof (FIB Drop vs. Policy Deny)

To prove that tenant isolation is enforced at the routing architecture layer before security policy processing, cross-tenant lateral movement was tested:

**Corporate PC IP address verification**

![Palo Alto](screenshots/corporate-ip-address-verification.png)

**Guest PC IP address verification**

![Palo Alto](screenshots/10.50.50.10-ip-verification.png)

#### A. Routing-Layer Failure (No Route to Host)
Prior to evaluating any security rules, lateral probes from `VR-Guest` targeting `VR-Corporate` failed completely:

* **CLI Simulation from Guest Gateway (`10.50.50.1`):**
  ```text
  admin@PA-VM> ping source 10.50.50.1 host 10.10.10.10
  PING 10.10.10.10 (10.10.10.10) from 10.50.50.1 : 56(84) bytes of data.
  ^C
  --- 10.10.10.10 ping statistics ---
  26 packets transmitted, 0 received, 100% packet loss, time 612ms
  ```
  *(Simultaneous ping to local gateway `10.50.50.10` confirmed 0% loss / 1.2ms RTT).*

![Palo Alto](screenshots/ping-source-10.50.50.50.1-host-10.10.10.10.png)

* **Endpoint Probes from Guest Host (`10.50.50.10`):**
  ```bash
  rich@mx:~$ ping 10.10.10.10
  --- 10.10.10.10 ping statistics ---
  79 packets transmitted, 0 received, 100% packet loss

  rich@mx:~$ traceroute 10.10.10.10
  1  * * *
  2  * * *
  3  * * *

  rich@mx:~$ nc -vz 10.10.10.10 22
  (UNKNOWN) [10.10.10.10] 22 (ssh) : Connection timed out
  ```
**ping**

![Palo Alto](screenshots/guest-pc-ping-fails.png)

**ssh**

![Palo Alto](screenshots/guest-pc-ssh-failed.png)

**traceroute**

![Palo Alto](screenshots/guest-pc-traceroute-fails.png)

#### B. Wire-Level Verification (802.1Q Wireshark Capture)
Capturing traffic on the internal bridge (`br-pa-lan`) filtered on `ip.dst == 10.10.10.10`:
* Captured frames tagged with **`802.1Q Virtual LAN, ID: 50`** transmitting ICMP echo requests from `10.50.50.10` targeting `10.10.10.10`.
* **Result:** Every frame was marked `(no response found!)`. The packet entered subinterface `ethernet1/2.50`, was evaluated in `VR-Guest`, and was discarded at the routing layer because `VR-Guest` has no forwarding entry for `10.10.10.0/24`.

**Source 10.50.50.10 - Destination 10.10.10.10**

![Palo Alto](screenshots/wireshark-filter-src-10.50.50.10-dst-10.10.10.10.png)

**Source 10.10.10.10 - Destination 10.50.50.10**

![Palo Alto](screenshots/wireshark-filter-src-10.10.10.10-dst-10.50.50.10.png)

#### C. Defense-in-Depth Policy Logging (`Monitor > Logs > Traffic`)
When rule `Test-Guest-to-Corporate-DENY` was evaluated for logged telemetry:
* Traffic monitor recorded:
  * *Source Zone:* `Guest` (`10.50.50.10`) ➔ *Destination Zone:* `Trust` (`10.10.10.10`)
  * *Application:* `ping`, `not-applicable` (SSH port 22)
  * *Action:* **`deny`** | *Rule:* **`Test-Guest-to-Corporate-DENY`**
  * *Session End Reason:* **`policy-deny`**

**Security Rule - General Tab**

![Palo Alto](screenshots/security-rule-general.png)

**Security Rule - Source**

![Palo Alto](screenshots/security-rule-source.png)

**Security Rule - Destination**

![Palo Alto](screenshots/security-rule-destination.png)

**Security Rule - Actions**

![Palo Alto](screenshots/security-rule-actions.png)

**Mointor Traffic Logs**

![Palo Alto](screenshots/monitor-log-traffic-proof-of-denial.png)

---

### Key Artifact Index

| Artifact File | Category | Technical Proof & Validation |
| :--- | :--- | :--- |
| **`switch-show-run-section-interface.png`** | Switch Config | Cisco IOS `sh run` displaying Gig1/0/1 trunking VLANs 1, 10, and 50 to PA-VM. |
| **`creating-sub-interface-corporate.png`** | Interface Config | PAN-OS subinterfaces `ethernet1/2.10` (Trust) and `ethernet1/2.50` (Guest). |
| **`show-routing-route-virtual-router-vr-permiter.png`** | Dataplane Routing | `show routing route` confirming `VR-Perimeter` holds default route and `next-vr` pointers. |
| **`show-routing-route-virtual-router-vr-corporate.png`** | Dataplane Routing | `show routing route` proving `VR-Corporate` holds only local LAN and `next-vr` default. |
| **`show-routing-route-virtual-router-vr-guest.png`** | Dataplane Routing | `show routing route` proving `VR-Guest` has zero visibility into `10.10.10.0/24`. |
| **`test-routing-fib-lookup-virtual-router-guest-and-corporate.png`** | Control Plane CLI | `test routing fib-lookup` proving both VRs resolve `8.8.8.8` via `VR-Perimeter`. |
| **`10.50.50.10-ping-to-google-successful.png`** | Endpoint Proof | Guest client (`10.50.50.10`) maintaining 0% loss to `8.8.8.8` via `next-vr` leaking. |
| **`corporate-pc-curl-google-successful.png`** | Endpoint Proof | Corporate client (`10.10.10.10`) fetching `google.com` (HTTP/2 200 OK) via `next-vr`. |
| **`ping-source-10.50.50.50.1-host-10.10.10.10.png`** | Routing Isolation | `ping source 10.50.50.1 host 10.10.10.10` confirming 100% packet loss at FIB layer. |
| **`guest-pc-ssh-failed.png`** | Endpoint Isolation | Guest client `nc -vz 10.10.10.10 22` timing out with zero response. |
| **`wireshark-filter-src-10.50.50.10-dst-10.10.10.10.png`** | Wire Trace | Wireshark trace showing 802.1Q Tag 50 ICMP requests dropped with no reply. |
| **`monitor-traffic-logs-guest-pc.png`** | Telemetry Log | Monitor log auditing permitted guest sessions from `Guest` to `Untrust`. |
| **`monitor-traffic-logs-corporate-pc.png`** | Telemetry Log | Monitor log auditing permitted corporate sessions from `Trust` to `Untrust`. |
| **`monitor-log-traffic-proof-of-denial.png`** | Security Policy | Monitor log confirming defense-in-depth drop under `Test-Guest-to-Corporate-DENY`. |

---
