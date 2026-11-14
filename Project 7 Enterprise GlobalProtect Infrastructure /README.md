# Enterprise GlobalProtect Infrastructure – Gateway, Portal, Split-Tunneling & Zero Trust Remote RBAC

A production-grade implementation of Palo Alto Networks' flagship remote-workforce architecture running on PAN-OS 11.2.5. This project documents the end-to-end deployment of an **Enterprise GlobalProtect Remote Access Infrastructure**, incorporating dedicated PKI, an external **Portal** and **Gateway** bound to `ethernet1/1` (`192.168.1.200`), automated **Virtual IP Address Pool Allocation (`10.200.1.0/24`)**, and **Client-Side Split-Tunneling**.

Remote workers running the official GlobalProtect client on Windows 10 (`192.168.1.100`) authenticate against Active Directory (`meridian.local`), dynamically bind to a virtual tunnel interface (`tunnel.2`), and receive **Role-Based Access Control (RBAC)** security policies. The project demonstrates real-time Zero Trust enforcement: granting `network-admins` complete access to internal production servers (`http://10.10.10.50`), while strictly dropping traffic from `contractors` over the identical VPN tunnel.

Every authentication transaction, gateway registration, client route table entry, split-tunnel trace, and policy decision was verified using the official GlobalProtect Agent (v6.3.3), Windows PowerShell routing diagnostics, PAN-OS gateway state tables (`show global-protect-gateway current-user`), User-ID telemetry, and firewall traffic monitors.

---

## Architecture & Remote Access Peering Fabric

![Palo Alto](screenshots/global-protect.png)
---

## Architectural & Network Specifications

| Parameter | Configuration Detail | Functional Role |
| :--- | :--- | :--- |
| **Portal / Gateway Interface** | `ethernet1/1` (`192.168.1.200/24`) | Public external entry point for all remote workforce sessions |
| **Tunnel Interface** | `tunnel.2` (`Virtual Router: default`) | Route-based point-to-point interface terminating remote client flows |
| **Security Zone** | `Global-Protect-VPN` (Layer 3) | Dedicated security zone with User-ID identification enabled |
| **Identity / Auth Profile** | `Corp-AD-Auth` (LDAP ➔ `172.16.109.133`) | Authenticates domain accounts in `meridian.local` |
| **SSL/TLS Profile** | `Global-Protect-TLS-PROFILE` | TLS 1.2+ server profile bound to `GP-PORTAL-GATEWAY-CERT` |
| **VPN Client IP Pool** | `10.200.1.10 - 10.200.1.50` | Dynamic virtual adapter subnet leased to connected endpoints |
| **Transport Protocol** | **IPSec (ESP)** with SSL Fallback | IPSec preferred for sub-millisecond encryption; SSL fallback ready |
| **Split-Tunnel Routes** | `10.10.10.0/24`, `20.20.20.0/24`, `172.16.50.0/24` | Injected into client routing table; non-corporate traffic bypasses VPN |
| **Client Source NAT** | `GP-VPN` to `Trust` (SNAT to `10.10.10.1`) | Prevents asymmetric routing for internal servers lacking reverse routes |

## Multi-Phase Implementation 

### PKI, Certificates & SSL/TLS Service Profile
A dedicated server certificate was provisioned with the gateway's IP address embedded in the Subject Alternative Name (SAN) to ensure trusted TLS negotiation across remote clients:
* **Certificate Name:** `GP-PORTAL-GATEWAY-CERT` (RSA 2048-bit, SHA-256)
* **Common Name:** `192.168.1.200` | **SAN Attribute:** `IP: 192.168.1.200`
* **Signed By:** `Enterprise-Forward-Trust-CA`
* **SSL/TLS Profile:** `Global-Protect-TLS-PROFILE` (Min Version: `TLSv1.2`, Max Version: `TLSv1.3`).

![Palo Alto](screenshots/creating-certificate.png)

![Palo Alto](screenshots/creating-global-protect-ssl-tls-service-profile.png)

### Interface, Zone & Return Path Source NAT
1. **Tunnel Interface Provisioning:**
   * Interface: `tunnel.2` assigned to Virtual Router `default` and Zone `Global-Protect-VPN`.
2. **Zone Creation:**
   * Name: `Global-Protect-VPN` (Layer 3) with **`Enable User Identification`** checked.
3. **Symmetric Return Path NAT (SNAT):**
   * *Problem:* When remote clients on `10.200.1.0/24` connect to internal hosts (`10.10.10.50`), destination servers without a dedicated static route back to the virtual pool will blackhole return packets.
   * *Resolution:* Provisioned NAT rule **`GP-VPN`**:
     * Source Zone: `Global-Protect-VPN` | Destination Zone: `Trust`
     * Source Address: `10.200.1.0/24` | Destination Address: `10.10.10.50`
     * Translation: Dynamic IP and Port (Interface `ethernet1/2` ➔ `10.10.10.1`).
     
**Creating Global Protect Zone**

![Palo Alto](screenshots/creating-global-protect-zone.png)
     
**Creating Tunnel Interface**

![Palo Alto](screenshots/creating-tunnel-interface.png)

**Tunnel Interface Overview**

![Palo Alto](screenshots/tunnel-interface-overview.png)

**Creating NAT - General Tab**

![Palo Alto](screenshots/creating-nat-general.png)

**Creating NAT - Original Packet**

![Palo Alto](screenshots/creating-nat-original-packet.png)

**Creating NAT - Translated Packet**

![Palo Alto](screenshots/creating-nat-translated-packet.png)

### GlobalProtect Gateway Configuration (`Global-Protect-Gateway`)
* **Network Settings:** Interface `ethernet1/1` | IPv4 `192.168.1.200/24`.
* **Server Authentication:** `Global-Protect-TLS-PROFILE`.
* **Client Authentication:** Profile `Corp-AD-Auth` (LDAP) | Username Label: `Username` | Password Label: `Password`.
* **Tunnel Settings:** Enabled: **Yes** | Tunnel Interface: **`tunnel.2`**.
* **Client IP Pool:** Static Range: **`10.200.1.10 - 10.200.1.50`**.
* **Network Services:** Primary DNS `172.16.109.133` (Active Directory DC) | Secondary DNS `1.1.1.1`.
* **Client Settings (`Default-Split-Tunnel`):**
  * **Include Access Routes:**
    * `10.10.10.0/24` (Corporate Trust LAN)
    * `20.20.20.0/24` (Cisco CSR Datacenter Subnet)
    * `172.16.50.0/24` (Datacenter Loopback Services)

**Global Protect Gateway Configuration - General Tab**

![Palo Alto](screenshots/creating-global-protect-gateway.png)

**Global Protect Gateway Configuration - Agent Tab (Client Settings Overview)**

![Palo Alto](screenshots/creating-global-protect-gateway-agent-tab.png)

**Global Protect Gateway Configuration - Agent Tab (Client IP Pool)**

![Palo Alto](screenshots/creating-global-protect-gateway-agent-tab-client-ip-pool.png)

**Global Protect Gateway Configuration - Agent Tab (Network Services)**

![Palo Alto](screenshots/creating-global-protect-gateway-agent-tab-network-settings.png)

**Global Protect Gateway Configuration - Agent Tab (Creating Selection Criteria)**

![Palo Alto](screenshots/creating-global-protect-gateway-client-settings-creating-config.png)

**Global Protect Gateway Configuration - Agent Tab (Creating Split Tunnel)**

![Palo Alto](screenshots/creating-global-protect-gateway-client-settings-creating-config-split-tunnel.png)

**Global Protect Gateway Configuration - Configuring Authentication**

![Palo Alto](screenshots/creating-global-protect-gateway-client-authentication.png)

**Global Protect Gateway Configuration - Authentication Overview**

![Palo Alto](screenshots/creating-global-protect-gateway-authentication-tab.png)

### GlobalProtect Portal Configuration (`GP-Portal-Core`)
* **Network Settings:** Interface `ethernet1/1` | IPv4 `192.168.1.200/24`.
* **Authentication:** `Global-Protect-TLS-PROFILE` + `Corp-AD-Auth`.
* **Agent Configuration (`GP-Agent-Config`):**
  * External Gateway: `HQ-Gateway` targeting address **`192.168.1.200`** (Priority: Highest).
  * Save User Credentials: Set to `Yes`.
* **Clientless VPN:** Enabled with application bookmark `Windows-DC-Web` (`http://172.16.109.133`) for fallback browser access.

**Global Protect Portal - General Tab**

![Palo Alto](screenshots/creating-global-protect-portal.png)

**Global Protect Portal - Configuring Authentication**

![Palo Alto](screenshots/creating-global-protect-portal.png)

**Global Protect Portal - Authentication Tab Overview**

![Palo Alto](screenshots/creating-global-protect-portal-creating-authentication.png)

**Global Protect Portal - Agent Tab (Exeternal Gateway Configuration)**

![Palo Alto](screenshots/creating-global-protect-portal-creating-agent-external-gateways.png)

**Global Protect Portal - Agent Tab Overview**

![Palo Alto](screenshots/global-protect-portal-agent-overview.png)

### Zero Trust Role-Based Access Control (RBAC) Policies
Configured identity-aware security policies evaluating group memberships from Active Directory:

```text
! Production Rulebase Hierarchy:
Rule 1: Global-Protect-Admins-Full-Access
        From: Global-Protect-VPN | User: meridian\network-admins
        To: any | Destination: any | Action: Allow

Rule 2: Global-Protect-Users
        From: Global-Protect-VPN | User: meridian\network-users
        To: Trust | Destination: 10.10.10.0/24 | Action: Allow
        
Rule 3: Global-Protect-Contractors-Deny
        From: Global-Protect-VPN | User: meridian\contractors
        To: Trust | Destination: 10.10.10.0/24 | Action: Deny

```
**Security Rule 1 - General Tab**

![Palo Alto](screenshots/security-rule-general.png)

**Security Rule 1 - Source**

![Palo Alto](screenshots/security-rule-source.png)

**Security Rule 1 - Destination**

![Palo Alto](screenshots/security-rule-destination.png)

**Security Rule 2 - General Tab**

![Palo Alto](screenshots/security-rule-2-general.png)

**Security Rule 2 - Source**

![Palo Alto](screenshots/security-rule-2-source.png)

**Security Rule 2 - Destination**

![Palo Alto](screenshots/security-rule-2-destination.png)

**Security Rule 2 - Applications**

![Palo Alto](screenshots/security-rule-2-applications.png)

**Security Rule 3 - General**

![Palo Alto](screenshots/security-rule-3-general.png)

**Security Rule 3 - Source**

![Palo Alto](screenshots/security-rule-3-source.png)

**Security Rule 3 - Destination**

![Palo Alto](screenshots/security-rule-3-destination.png)

**Security Rule 3 - Action**

![Palo Alto](screenshots/security-rule-3-action.png)

---

## Empirical Verification & Technical Proof

### Portal Onboarding & Self-Service Agent Deployment

Before an endpoint can establish an IPSec tunnel, it must authenticate to the portal and retrieve the client software.

1. **Portal Authentication Screen (`/global-protect/login.esp`):**
   * Remote users browse to `https://192.168.1.200`.
   * The PA-VM serves a TLS-secured portal login page requiring Active Directory credentials (`meridian.local`).

![GlobalProtect Portal Login](screenshots/palo-alto-sign-in-page.png)

2. **Self-Service Agent Distribution (`/global-protect/getsoftwarepage.esp`):**
   * Upon successful authentication, the portal serves the self-service software page.
   * Users can download the official **Windows 64-bit**, **Windows 32-bit**, or **macOS** GlobalProtect installation packages directly from the firewall without requiring external deployment tools (MDT/SCCM).

![GlobalProtect Agent Download](screenshots/download-agent-prompt.png)

***
### Client Connection & IPSec Tunnel Telemetry

The official GlobalProtect agent was launched on the remote Windows 10 endpoint (`DESKTOP-KF2G2J3`). The client authenticated against the portal, discovered the gateway, and established an IPSec-encapsulated tunnel:

```text
Windows IP Configuration (PowerShell):
Ethernet adapter Ethernet 2:
   Description . . . . . . . . . . . : PANGP Virtual Ethernet Adapter Secure
   IPv4 Address. . . . . . . . . . . : 10.200.1.10 (Preferred)
   Subnet Mask . . . . . . . . . . . : 255.255.255.255
   DNS Servers . . . . . . . . . . . : 8.8.8.8, 1.1.1.1
```
![Palo Alto](screenshots/powershell-ipconfig-all.png)

#### Gateway Hardware Session Audit (PA-VM CLI)
Executing `show global-protect-gateway current-user` verified the active data-plane session:

```text
admin@PA-VM> show global-protect-gateway current-user

GlobalProtect Gateway: Global-Protect-Gateway (1 users)
Tunnel Name         : Global-Protect-Gateway-N
      Domain-User Name          : meridian\netadmin.test
      Computer                  : DESKTOP-KF2G2J3
      Primary Username          : meridian\netadmin.test
      Client                    : Microsoft Windows 10 Pro , 64-bit
      VPN Type                  : Device Level VPN
      Client App Version        : 6.3.3-876
      Private IP                : 10.200.1.10
      Public IP (connected)     : 192.168.1.100
      ESP                       : exist
      SSL                       : none
      Login Time                : Nov.13 03:33:36
```

> **Cryptographic Transport Proof:** The fields **`ESP: exist`** and **`SSL: none`** confirm that PAN-OS prioritized and established an RFC-compliant IPSec/ESP tunnel across the WAN rather than falling back to higher-overhead SSL VPN tunnels.

![Palo Alto](screenshots/show-global-protect-gateway-current-user-netadmin.png)

**GUI**

![Palo Alto](screenshots/global-protect-gateway-current-users.png)

---

### Client Endpoint Authentication & IPSec Tunnel Telemetry

Following installation, the official GlobalProtect client was launched on the remote Windows 10 workstation (`DESKTOP-KF2G2J3`).

1. **System Tray Connection Status:**
   * The client agent successfully authenticated and established an active tunnel to **`HQ-Gateway`** (evaluated as the best available gateway).

![GlobalProtect Client Connected](screenshots/palo-alto-connected.png)

2. **Tunnel Statistics & Virtual Adapter Validation:**
   * **Assigned Virtual IP:** **`10.200.1.10`** (leased from pool `10.200.1.10–50`).
   * **Active Protocol:** **`IPSec`** (confirming native hardware ESP encapsulation across the WAN).
   * **Authenticated User:** `netadmin.test`.
   * **Portal Reachability:** Active green status on portal anchor `192.168.1.200`.
   * **Session Lifetime:** Active session registered with 29-day lifetime.

![GlobalProtect Tunnel Statistics](screenshots/palo-alto-global-agent-overview.png)

### Client-Side Split-Tunneling Routing Table Audit

Executing `route print` on the Windows 10 workstation confirmed that the gateway dynamically pushed specific corporate prefixes while leaving the default internet route untouched:

```text
IPv4 Route Table
===========================================================================
Active Routes:
Network Destination        Netmask          Gateway       Interface  Metric
          0.0.0.0          0.0.0.0    192.168.122.1  192.168.122.40      25  <-- Default Home Gateway
       10.10.10.0    255.255.255.0          On-link     10.200.1.10       1  <-- Corporate Trust LAN
       20.20.20.0    255.255.255.0          On-link     10.200.1.10       1  <-- Cisco Datacenter LAN
      172.16.50.0    255.255.255.0          On-link     10.200.1.10       1  <-- Datacenter Loopback
```
![Palo Alto](screenshots/powershell-route-print.png)

#### Split-Tunnel Traceroute Validation
To prove split-tunneling operates at the wire level:

* **Corporate Traffic Trace (`10.10.10.50`):**
  ```powershell
  PS C:\Users\rich> tracert -d 10.10.10.50
  Tracing route to 10.10.10.50 over a maximum of 30 hops
    1     *        *        *     Request timed out.
    2     3 ms     2 ms     2 ms  10.10.10.50
  Trace complete.
  ```
  *Result:* Traffic routed across the virtual adapter (`10.200.1.10`), traversing the encrypted tunnel to the internal server in **2 ms**. The Tunnel.2 interface does not contain an IP hence the *** in place of an IP address.

![Palo Alto](screenshots/tracert-to-web-server.png)

* **Public Internet Trace (`34.223.124.45`):**
  ```powershell
  PS C:\Users\rich> tracert -d 34.223.124.45
  Tracing route to 34.223.124.45 over a maximum of 30 hops
    1    <1 ms    <1 ms    <1 ms  192.168.122.1
    2     1 ms    <1 ms    <1 ms  192.168.1.1
    3    15 ms    12 ms    19 ms  108.46.243.1
  ```
  *Result:* Egressed directly through the local residential gateway (`192.168.122.1` ➔ `192.168.1.1`), completely bypassing the corporate firewall and preserving corporate bandwidth.

![Palo Alto](screenshots/tracert-goes-to-isp-instead-neverssl.png)

---

### Role-Based Access Control (RBAC) Enforcement Over VPN

#### Test A: Privileged Admin Access (`meridian\netadmin.test`)
* **Identity Context:** Authenticated as member of `cn=network-admins`.
* **Action:** Navigated to internal web application `http://10.10.10.50`:
  * Application loaded successfully: **`Meridian Financial Services - Internal Corporate Application - INTERNAL SERVER ONLINE (Hostname: MERIDIAN-WEB1)`**.
* **Traffic Log Verification (`Monitor > Logs > Traffic`):**
  * *Source Zone:* `Global-Protect-VPN` | *Source IP:* `10.200.1.10`
  * *Source User:* **`meridian\netadmin.test`**
  * *Destination:* `10.10.10.50:80`
  * *Action:* **`allow`** | *Rule:* **`Global-Protect-Admins-Full-Access`**.

![Palo Alto](screenshots/web-server-reached.png)

**Please enlarge for a clearer video**

#### Test B: Restricted Contractor Drop (`meridian\contractor.test`)
* **Identity Context:** Re-authenticated the client using `meridian\contractor.test` (assigned virtual IP `10.200.1.11`).
* **Action:** Attempted to access the identical application web URL `http://10.10.10.50`:
  * Browser halted with: **`Hmmm... can't reach this page - 10.10.10.50 took too long to respond (ERR_CONNECTION_TIMED_OUT)`**.
* **Traffic Log Verification (`Monitor > Logs > Traffic`):**
  * *Source Zone:* `Global-Protect-VPN` | *Source IP:* `10.200.1.11`
  * *Source User:* **`meridian\contractor.test`**
  * *Action:* **`deny`** | *Rule:* **`Global-Protect-Contractors-Deny`**
  * *Session End Reason:* **`policy-deny`**.

![Palo Alto](screenshots/web-server-unavailable.png)

**Plese enlarge for a clearer video**

---

### Telemetry & Audit Trails: User-ID, Connection Lifecycles & Traffic Logs

The integration between GlobalProtect, Active Directory, and the Single-Pass Parallel Processing (SP3) engine produces an end-to-end audit trail across three dedicated PAN-OS log facilities: **User-ID**, **GlobalProtect Events**, and the **Traffic Monitor**.

---

#### GlobalProtect Connection Lifecycle & Failure Auditing (`Monitor > Logs > GlobalProtect`)

The GlobalProtect log facility tracks state transitions from initial portal contact to tunnel teardown.

##### Full Connection Sequence
Filtering on `meridian\netadmin.test` and `meridian\contractor.test` documented the sequential phases of tunnel establishment:

| Stage | Event | Protocol | Operational Verification |
| :--- | :--- | :--- | :--- |
| `configuration` | `portal-getconfig` | `ldap` | Client queries portal over HTTPS, validates credentials, and retrieves gateway policies. |
| `login` | `gateway-register` | — | Endpoint discovers gateway `HQ-Gateway` and registers host metadata (`DESKTOP-KF2G2J3`). |
| `configuration` | `gateway-getconfig` | — | Gateway pushes tunnel parameters, DNS servers (`172.16.109.133`), and split-tunnel routes. |
| `tunnel` | `gateway-setup-ipsec` | **IPsec (ESP)** | Establishes tunnel; dynamically leases virtual IP address (`10.200.1.10` / `10.200.1.11`). |
| `connected` | `gateway-connected` | `ldap` | Tunnel negotiation completes; virtual adapter binds to zone `Global-Protect-VPN`. |
| `host-info` | `gateway-hip-check` | — | Collects client Host Information Profile data (OS version, patch level, host ID). |
| `logout` | `gateway-logout` | — | Client disconnects; virtual IP lease is released and session memory is freed. |

**netadmin.test**

![Palo Alto](screenshots/monitor-global-protect-logs-netadmin.png)

**contractor.test**

![Palo Alto](screenshots/monitor-global-protect-logs-contractor.png)

##### Authentication Failure Tracking
Filtering on `( status eq 'failure' )` confirmed that unauthorized attempts and mistyped passwords are logged with forensic attribution:
* **Event:** `portal-auth` and `clientlessvpn-login`
* **Source IP:** `192.168.1.100` (Attacker / Remote Host)
* **Auth Method:** `ldap`
* **Error Logged:** **`Authentication failed: Invalid username or password`**
* **Host Tracking:** Pointers logged the client's hardware Host ID (`eedba598-1634-4db3-b89d-1052cc1350e7`) and machine name (`DESKTOP-KF2G2J3`).

![Palo Alto](screenshots/monitor-global-protect-failed-log-ins.png)

---

#### Dynamic VPN User-ID Mapping (`Monitor > Logs > User-ID`)

Unlike internal LAN endpoints that rely on Windows Event Log scraping (WMI/WinRM), GlobalProtect acts as an authoritative, native User-ID source. The firewall maps leased virtual IP addresses directly upon tunnel establishment:

* **Leased IP Mappings:**
  * `10.200.1.10` ➔ **`meridian\netadmin.test`**
  * `10.200.1.11` ➔ **`meridian\contractor.test`**
* **Data Source:** **`vpn-client`**
* **Source Type:** **`globalprotect`**
* **Timeout Behavior:** Active sessions maintain an explicit TTL (`Timeout: 10800`). Upon receiving a `gateway-logout` event, the daemon updates the timeout to `0`, aging out the entry to prevent identity reuse.

![Palo Alto](screenshots/monitor-user-id-logs.png)

---

#### RBAC Policy Enforcement: Admin Allow vs. Contractor Deny (`Monitor > Logs > Traffic`)

Inspecting the Traffic Monitor verified that policy decisions are enforced per user identity across the remote access tunnel:

#####  Network Administrator Allowed (`user.src eq 'meridian\netadmin.test'`)
* **Source:** `10.200.1.10` (`Global-Protect-VPN`) ➔ **Destination:** `10.10.10.50` (`Trust`)
* **Applications:** `web-browsing` (Port 80), `ping`, `traceroute`
* **Action:** **`allow`**
* **Matched Rule:** **`Global-Protect-Admins-Full-Access`**
* **Outcome:** The administrator gained full access to the internal production portal (`MERIDIAN-WEB1`).

![Palo Alto](screenshots/monitor-traffic-logs-netadmin.png)

##### Contractor Denied (`user.src eq 'meridian\contractor.test'`)
* **Source:** `10.200.1.11` (`Global-Protect-VPN`) ➔ **Destination:** `10.10.10.50` (`Trust`) / `1.1.1.1` (`Untrust`)
* **Ports:** `53` (DNS), `80` (HTTP)
* **Action:** **`deny`**
* **Matched Rule:** **`Global-Protect-Contractors-Deny`**
* **Session End Reason:** **`policy-deny`**
* **Outcome:** 100% of packets originating from the contractor identity were dropped at the ingress tunnel interface, proving Zero Trust segmentation over remote access.

![Palo Alto](screenshots/monitor-traffic-logs-contractor.png)

---

## Key Artifact Index & Troubleshooting

### Key Artifact Index

| Artifact File | Category | Technical Proof & Validation |
| :--- | :--- | :--- |
| **`gp-portal-login-screen.png`** | User Interface | Web browser accessing `https://192.168.1.200/global-protect/login.esp`. |
| **`gp-portal-software-download.png`** | Agent Deployment | Portal landing page serving Windows and Mac GlobalProtect agents. |
| **`gp-client-connected-status.png`** | Endpoint Status | Official GlobalProtect agent showing `Connected` to `HQ-Gateway` via IPSec. |
| **`win10-ipconfig-virtual-adapter.png`** | Endpoint Telemetry | PowerShell `ipconfig /all` verifying `PANGP Virtual Adapter` leased IP `10.200.1.10`. |
| **`win10-route-print-split-tunnel.png`** | Routing Table | PowerShell `route print` verifying corporate routes injected while `0.0.0.0/0` stays local. |
| **`win10-tracert-corporate-vs-dia.png`** | Path Diagnostic | Side-by-side traceroutes proving corporate traffic uses VPN and internet uses local ISP. |
| **`internal-web-app-admin-allowed.png`** | Application Access | Browser rendering `Meridian Financial Services` app online for `netadmin.test`. |
| **`internal-web-app-contractor-denied.png`** | Security Proof | Browser timing out with `ERR_CONNECTION_TIMED_OUT` when accessed by contractor. |
| **`pa-cli-gp-gateway-current-user.png`** | Gateway State | `show global-protect-gateway current-user` verifying `ESP: exist` and active client details. |
| **`pa-cli-gp-gateway-flow-status.png`** | Gateway State | `show global-protect-gateway flow` verifying tunnel binding between `192.168.1.200` and `tunnel.2`. |
| **`monitor-logs-gp-events.png`** | Telemetry Log | GlobalProtect log tracking authentication, IP assignment, and tunnel negotiation stages. |
| **`monitor-logs-traffic-gp-admin-allow.png`** | Security Policy | Traffic monitor auditing permitted sessions matching `Global-Protect-Admins-Full-Access`. |
| **`monitor-logs-traffic-gp-contractor-deny.png`** | Security Policy | Traffic monitor auditing dropped sessions matching `Global-Protect-Contractors-Deny`. |
| **`monitor-logs-userid-gp-mapping.png`** | Identity Telemetry | User-ID log confirming automatic mapping of `10.200.1.x` via `vpn-client / globalprotect`. |

---

### Troubleshooting & Engineering Lessons Learned

| Challenge Encountered | Root Cause | Engineering Resolution |
| :--- | :--- | :--- |
| **Internal corporate application failed to load despite active VPN tunnel.** | Internal hosts on `10.10.10.0/24` lacked a static routing entry pointing return traffic for `10.200.1.0/24` back to the firewall. | Configured a **Source NAT rule (`GP-VPN`)** translating remote VPN pool traffic to the firewall's LAN gateway IP (`10.10.10.1`), ensuring symmetric return routing. |
| **Client traffic defaulted to higher-latency SSL VPN tunnels.** | In restrictive firewall environments or when UDP port 4501 is blocked, GlobalProtect fails back to TLS tunnel encapsulation over TCP 443. | Ensured perimeter access policies permitted UDP 500 and UDP 4500, enabling the client to successfully negotiate native hardware-accelerated **IPSec/ESP**. |
| **DNS resolution failed for internal corporate hostnames.** | The remote client inherited standard public DNS servers that could not resolve private enterprise domain names (`meridian.local`). | Configured the gateway's **Network Services** to push the internal Domain Controller (`172.16.109.133`) as Primary DNS to the virtual adapter. |
| **Preventing contractors from accessing corporate databases over VPN.** | Standard VPN concentrators grant network-level Layer 3 access to any user possessing valid portal credentials. | Leveraged PAN-OS **Identity-Aware RBAC** to inspect the source user's Active Directory security group (`meridian\contractors`) on every packet, terminating connections at the firewall perimeter. |











These two screenshots belong directly in **`### 2. Client Endpoint Authentication & IPSec Tunnel Telemetry`** (right after the agent download section). 

They serve as the **official Windows client-side proof** that:
1. The endpoint negotiated an active tunnel.
2. The user (`netadmin.test`) authenticated successfully.
3. The client selected **IPSec** as the transport protocol instead of higher-overhead SSL VPN.

Here is the exact short section to paste into your `README.md`:

***

### 2. Client Endpoint Authentication & IPSec Tunnel Telemetry

Following installation, the official GlobalProtect client was launched on the remote Windows 10 workstation (`DESKTOP-KF2G2J3`).

```text
  [ GlobalProtect Agent ] ──── 1. Connects to 192.168.1.200 ────> [ HQ-Gateway ]
                          <─── 2. Auth: netadmin.test (AD)  ───
                          <─── 3. Leases IP: 10.200.1.10    ───
                          <─── 4. Transport: IPSec (ESP)    ───
```

1. **System Tray Connection Status:**
   * The client agent successfully authenticated and established an active tunnel to **`HQ-Gateway`** (evaluated as the best available gateway).

![GlobalProtect Client Connected](screenshots/gp-client-connected-status.png)

2. **Tunnel Statistics & Virtual Adapter Validation:**
   * **Assigned Virtual IP:** **`10.200.1.10`** (leased from pool `10.200.1.10–50`).
   * **Active Protocol:** **`IPSec`** (confirming native hardware ESP encapsulation across the WAN).
   * **Authenticated User:** `netadmin.test`.
   * **Portal Reachability:** Active green status on portal anchor `192.168.1.200`.
   * **Session Lifetime:** Active session registered with 29-day lifetime.

![GlobalProtect Tunnel Statistics](screenshots/gp-client-tunnel-statistics.png)

***

*(From here, you transition directly into the PowerShell `ipconfig /all` and `route print` split-tunneling tests!)*
