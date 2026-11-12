# Enterprise Identity Fabric – Active Directory LDAP Integration, Captive Portal & Role-Based Access Control (RBAC)

A production-grade implementation of Palo Alto Networks' **User-ID** and **Authentication Portal (Captive Portal)** architecture running PAN-OS 11.2.5. This project documents the complete transition from static IP-based filtering to dynamic, identity-aware **Zero Trust Role-Based Access Control (RBAC)** integrated with a Windows Server 2022 Active Directory Domain Controller (`meridian.local` at `172.16.109.133`).

Traffic is intercepted before internet egress, forcing unauthenticated workstations to authenticate against Active Directory via an inline HTTPS Captive Portal. Once authenticated, the firewall enforces differential security policies—granting privileged access to `Network-Admins`, standard access to `Network-Users`, and dropping traffic for `Contractors`—across the **exact same endpoint IP address (`10.10.10.10`)**.

Every authentication handshake, LDAP directory query, IP-to-user mapping table, and policy transition was verified using live browser redirections, Windows Server PowerShell audits, CLI state table inspections (`show user ip-user-mapping`), authentication telemetry, and deterministic policy simulations (`test security-policy-match`).

**Live Execution: AD User 'richard.palo' Verified**

https://github.com/user-attachments/assets/4b6ed171-bf69-413c-8666-0297c39b66f0

**Live Execution: AD User 'contractor.test' packets being DROPPED**

https://github.com/user-attachments/assets/c364c0c3-90b8-48c4-98d5-ccb11600b33a

**Live Execution: AD User 'netadmin.test' Verified after new Security Policy (Network-Admins-Allow)**

https://github.com/user-attachments/assets/6566b337-a9b1-4e42-9089-cead5c8bcfe0

---

## Architecture & Identity Lifecycle

![Palo Alto](screenshots/palo-authentication-lucid-chart.png)

---

## Implementation Phases

### Active Directory Directory Services (AD DS) Structure
On Windows Server 2022 (`172.16.109.133`), a dedicated organizational structure was provisioned in `meridian.local`:
* **Base DN:** `DC=meridian,DC=local`
* **Bind Account:** `CN=Administrator,CN=Users,DC=meridian,DC=local`
* **Organizational Units:**
  * `OU=Meridian Groups`:
    * `cn=network-admins`
    * `cn=network-users`
    * `cn=vpn-users`
    * `cn=contractors`
  * `OU=Meridian Users`:
    * `netadmin.test` (Member of `network-admins`)
    * `richard.palo` (Member of `network-users`)
    * `contractor.test` (Member of `contractors`)
    
![Palo Alto](screenshots/get-ad-cn.png)

![Palo Alto](screenshots/active-directory-groups.png)

![Palo Alto](screenshots/active-directory-users.png)

---

### LDAP Directory Sync & Group Mapping
To import the Active Directory hierarchy without hardcoding usernames:

1. **LDAP Server Profile (Corp-AD-LDAP):**
   * Server: `172.16.109.133` | Port: `389`
   * Type: `active-directory`
   * Base DN: `DC=meridian,DC=local`
   * Bind DN: `CN=Administrator,CN=Users,DC=meridian,DC=local`
2. **Authentication Profile (Corp-AD-Auth):**
   * Type: `LDAP` | Server Profile: `Corp-AD-LDAP`
   * Login Attribute: `sAMAccountName`
3. **Group Mapping Profile (Corp-Group-Mapping):**
   * Profile: `Corp-AD-LDAP`
   * Object Class: `group` | User Class: `person`
   * Group Include List: Enrolled `network-admins`, `network-users`, `vpn-users`, and `contractors`.

![Palo Alto](screenshots/creating-ldap-profile.png)

![Palo Alto](screenshots/creating-authentication-profile.png)

![Palo Alto](screenshots/configuring-group-mapping.png)

![Palo Alto](screenshots/configuring-group-mapping-group-list.png)

**Group Map Overview**

![Palo Alto](screenshots/user-identification-overview.png)

**Applying User Identification to Trust Zone**

![Palo Alto](screenshots/zone-enabling-user-identification.png)

---

### Active Directory Group Enumeration & User Membership Resolution

Before the firewall can enforce identity-based security policies, the User-ID daemon (`useridd`) must successfully query the Active Directory LDAP catalog, parse group Distinguished Names (DNs), and resolve domain accounts into their corresponding security groups### 2. Active Directory Group Enumeration & User-to-Group Resolution.

#### Active Directory Group Enumeration (`show user group list`)
Verifies that the firewall discovered (CLI)

Before identity-based security policies can evaluate user traffic, the firewall's User-ID engine (`useridd`) must successfully parse the LDAP catalog and map each domain account to its corresponding Active Directory security group.

#### Active Directory Group and cached the four target security groups from OU=Meridian Groups:

```text
admin@PA-VM> show user group list

cn=network-users,ou=meridian groups,dc=meridian,dc=local
cn Discovery
Confirming the firewall retrieved the 4 provisioned security groups from `OU=Meridian Groups`:

```text
admin@=network-admins,ou=meridian groups,dc=meridian,dc=local
cn=vpn-users,PA-VM> show user group list

cn=network-users,ou=meridian groups,dc=merou=meridian groups,dc=meridian,dc=local
cn=contractors,ou=meridianidian,dc=local
cn=network-admins,ou=meridian groups,dc=meridian,dc=local
cn=vpn-users,ou=meridian groups,dc=meridian,dc=local
 groups,dc=meridian,dc=local

Total: 4
* : Custom Group
```
![Palo Alto](screenshots/show-user-group-list.png)

#### User-to-Group Resolution Table (`show user user-ids all`)
Verifies that individual domain user accounts are dynamically mappedcn=contractors,ou=meridian groups,dc=meridian,dc=local

Total: 4
* : Custom Group
```

#### B. Active Directory User-to-Group Resolution
Confirming domain user accounts are actively mapped to to their respective security groups inside the firewall's local User-ID cache:

```text
admin@PA-VM> show user user-ids all

User Name                     Vsys    Groups
--------------------------------------------------------------------------------
meridian\vpn.test             vsys1   cn=vpn-users,ou=meridian groups,dc= their respective security groups in the User-ID state table:

```text
admin@PA-VM> show user user-ids all

meridian,dc=local
meridian\8021x.test           vsys1   cn=networkUser Name                     Vsys    Groups
--------------------------------------------------------------------------------
meridian\vpn.test             vsys1   cn=vpn-users,ou=meridian groups,dc=meridian,dc=local
meridian\802-users,ou=meridian groups,dc=meridian,dc=local
meridian\contractor.1x.test           vsys1   cn=network-users,ou=meridian groups,dc=mertest      vsys1   cn=contractors,ou=meridian groups,dc=meridian,dc=local
meridianidian,dc=local
meridian\contractor.test      vsys1   cn=contractors,ou\richard.palo         vsys1   cn=network-users,ou=meridian groups,dc==meridian groups,dc=meridian,dc=local
meridian\richard.palo         vsys1   cn=network-users,ou=meridian groups,dc=meridian,dc=local
meridian,dc=local
meridian\netadmin.test        vsys1   cn=network-admins,ou=meridian groups,dc=meridian,dc=local

Total: 5
* : Custommeridian\netadmin.test        vsys1   cn=network-admins,ou=meridian groups,dc=mer Group
```

> **Key Architectural Takeaway:** This in-memory resolution table powers **Role-Based Access Controlidian,dc=local

![Palo Alto](screenshots/show-user-user-ids-all.png)

### Dedicated Captive Portal PKI & SSL/TLS Profile
Forcing an HTTPS redirect requires the portal server certificate to match the redirect hostname (`authportal`) and contain the interface IP as a Subject Alternative Name (SAN) to eliminate browser trust errors:
* **Root CA:** `AUTH-PORTAL-ROOT-CA` (Self-signed, trusted by client browser).
* **Server Certificate:** `AUTH-PORTAL-CERT` (Signed by `AUTH-PORTAL-ROOT-CA`, Common Name: `authportal`, IP SAN: `10.10.10.1`).
* **SSL/TLS Service Profile:** `AUTH-PORTAL-TLS` (Enforcing **TLSv1.2** minimum).

**AUTH-PORTAL-ROOT-CA**

![Palo Alto](screenshots/auth-portal-root-ca.png)

**AUTH-PORTAL-CERT**

![Palo Alto](screenshots/auth-portal-ca.png)

**SSL/TLS Profile**

![Palo Alto](screenshots/ssl-service-profile.png)

**Device Certificate Overview**

![Palo Alto](screenshots/certificate-overview.png)

---

### Interface & Authentication Portal Configuration
1. **Interface Management Profile (TRUST-AUTH-PORTAL):**
   * Bound to `ethernet1/2` (Trust Gateway `10.10.10.1`).
   * Enabled Services: **`Response Pages`** and **`User-ID`**.
2. **Authentication Enforcement Object (`AD-WEB-FORM`):**
   * Method: `web-form`
   * Authentication Profile: `Corp-AD-Auth`
   * Message: *"Enter your corporate AD credentials to access the network."*
3. **Authentication Portal Settings:**
   * Mode: `Redirect` | Redirect Host: `authportal` (resolves to `10.10.10.1`)
   * SSL/TLS Profile: `AUTH-PORTAL-TLS` | Auth Profile: `Corp-AD-Auth`
   * Timers: Idle Timeout `15 min`, Max Timeout `60 min`.
4. **Authentication Policy (`AUTH-PORTAL-TRUST`):**
   * Source: `Trust` (`10.10.10.10`) | Destination: `Untrust` (`any`)
   * Action: `Allow` | Enforcement: `AD-WEB-FORM`.

**Interface Managemenet Profile**

![Palo Alto](screenshots/interface-management-profile.png)

**Applying Interface Management to Ethernet1/2**

![Palo Alto](screenshots/applying-management-interface-profile.png)

**Authentication Portal**

![Palo Alto](screenshots/creating-authentication-portal.png)

**Auhtentication Policy**

![Palo Alto](screenshots/creating-authentication-policy-1.png)

![Palo Alto](screenshots/creating-authentication-policy-2.png)

---

### Role-Based Access Control (RBAC) Security Rulebase

The security rulebase was refactored to evaluate identity groups before application inspection:

```text
! Priority Rulebase Hierarchy:
Rule 1: Contractors-DENY     (Source User: meridian\contractors   | Action: Drop)
Rule 2: Network-Admins-Allow (Source User: meridian\network-admins | Action: Allow)
Rule 3: Allow-ICMP-Test      (Source: any                        | Action: Allow)
Rule 4: Allow-DNS-NTP        (Source: any                        | Action: Allow)
Rule 5: Allow-Web-Browsing   (Source: any                        | Action: Allow)
Rule 6: DENY_TRAFFIC         (Source: any                        | Action: Drop)
```
![Palo Alto](screenshots/show-rulebase-security-rules.png)

![Palo Alto](screenshots/security-rules-gui.png)

**Source User: meridian\network-admins**

![Palo Alto](screenshots/source-user-network-admins.png)

**Source User: meridian\contractors**

![Palo Alto](screenshots/source-user-contractors.png)
---

## Empirical Verification & Live Identity Demonstrations

#### Control-Plane Policy Simulations (test security-policy-match)
Evaluating identical traffic parameters (**Source:** `10.10.10.10`, **Destination:** `8.8.8.8:443`, **Protocol:** `6`) against three different authenticated user identities:

##### 1. Contractor Evaluation (meridian\contractor.test) - Action: DROP
```text
admin@PA-VM> test security-policy-match from Trust to Untrust source 10.10.10.10 destination 8.8.8.8 destination-port 443 source-user meridian\contractor.test protocol 6

"Contractors-DENY; index: 1" {
        from Trust;
        source any;
        source-region none;
        to Untrust;
        destination any;
        destination-region none;
        user "cn=contractors,ou=meridian groups,dc=meridian,dc=local";
        source-device any;
        destination-device any;
        category any;
        application/service 0:any/any/any/any;
        action drop;
        icmp-unreachable: no
        terminal no;
}
```
![Palo Alto](screenshots/security-policy-match-test-contractor-fail.png)

##### 2. Network Admin Evaluation (meridian\netadmin.test) - Action: ALLOW
```text
admin@PA-VM> test security-policy-match from Trust to Untrust source 10.10.10.10 destination 8.8.8.8 destination-port 443 source-user meridian\netadmin.test protocol 6

"Network-Admins-Allow; index: 2" {
        from Trust;
        source any;
        source-region none;
        to Untrust;
        destination any;
        destination-region none;
        user "cn=network-admins,ou=meridian groups,dc=meridian,dc=local";
        source-device any;
        destination-device any;
        category any;
        application/service 0:any/any/any/app-default;
        action allow;
        icmp-unreachable: no
        terminal yes;
}
```
![Palo Alto](screenshots/security-policy-match-test-netadmin-pass.png)

##### 3. Standard User Evaluation (meridian\richard.palo) - Action: ALLOW (Web-Browsing Fallback)
```text
admin@PA-VM> test security-policy-match from Trust to Untrust source 10.10.10.10 destination 8.8.8.8 destination-port 443 source-user meridian\richard.palo protocol 6

"Allow-Web-Browsing; index: 5" {
        from Trust;
        source any;
        source-region none;
        to Untrust;
        destination any;
        destination-region none;
        user any;
        source-device any;
        destination-device any;
        category any;
        application/service [0:ssl/tcp/any/443 1:web-browsing/tcp/any/80 2:web-browsing/tcp/any/443 3:youtube-base/tcp/any/80 4:youtube-base/tcp/any/443 ... ];
        action allow;
        icmp-unreachable: no
        terminal yes;
}
```
![Palo Alto](screenshots/security-policy-match-test-richard-palo.png)

> **Zero Trust Engineering Proof:** Across identical Layer 3 and Layer 4 coordinates (`10.10.10.10` ➔ `8.8.8.8:443/TCP`), the security decision completely changes based on the user's Active Directory security group membership:
> * **`Contractors`** hit Rule 1 (`Contractors-DENY`) and are dropped immediately.
> * **`Network-Admins`** hit Rule 2 (`Network-Admins-Allow`) with unrestricted application-default access.
> * **`Standard Users`** fall through to Rule 5 (`Allow-Web-Browsing`), restricted strictly to business web applications.


Verifying active group mapping state:
```text
admin@PA-VM> show user group-mapping state all

Group Mapping(vsys1, type: active-directory): Corp-Group-Mapping
Bind DN   : CN=Administrator,CN=Users,DC=meridian,DC=local
Base      : DC=meridian,DC=local
Servers   : configured 1 servers (172.16.109.133:389)
Number of Groups: 4
cn=network-admins,ou=meridian groups,dc=meridian,dc=local
cn=network-users,ou=meridian groups,dc=meridian,dc=local
cn=vpn-users,ou=meridian groups,dc=meridian,dc=local
cn=contractors,ou=meridian groups,dc=meridian,dc=local
```
![Palo Alto](screenshots/active-directory-structure-phase-1.png)

---

### Live Captive Portal Interception & User Authentication
From client `10.10.10.10`:
1. Navigated to an external HTTP site (`http://neverssl.com`).
2. The firewall intercepted the connection and redirected the browser to:
   `https://authportal:6082/php/uid.php?vsys=1&rule=0...`
3. The custom PAN-OS **Authentication Portal** was rendered:
   * Tested invalid credentials: The portal returned an inline validation error: `* Invalid username or password`.
   * Tested valid domain credentials (`richard.palo` / `netadmin.test`): Successfully authenticated.

**Please enlarger for clearer video**

![Palo Alto](screenshots/login-required.png)

https://github.com/user-attachments/assets/4b6ed171-bf69-413c-8666-0297c39b66f0

---

### IP-to-User State Table Binding (show user ip-user-mapping)
Inspecting the active User-ID table confirmed that `10.10.10.10` dynamically bound to the authenticated identity:

```text
admin@PA-VM> show user ip-user-mapping all

IP              Vsys    From    User           IdleTimeout(s)  MaxTimeout(s)
----------------------------------------------------------------------------
10.10.10.10     vsys1   CP      richard.palo   899             3565
Total: 1 users
```

```text
admin@PA-VM> show user ip-user-mapping ip 10.10.10.10

IP address:      10.10.10.10 (vsys1)
User:            richard.palo
From:            CP (Captive Portal)
Idle Timeout:    872s
Max. TTL:        3457s
Group(s):        cn=network-users,ou=meridian groups,dc=meridian,dc=local
```
![Palo Alto](screenshots/show-user-mapping-all.png)

![Palo Alto](screenshots/show-user-mapping-10.10.10.10.png)

---

### Zero Trust RBAC Enforcement: Permitted Admin vs. Denied Contractor Videos
Using the exact same workstation IP (`10.10.10.10`), policy evaluation was tested under different authenticated user contexts:

#### Test A: Privileged Admin Access (netadmin.test)

**Source User: meridian/network-admins**

![Palo Alto](screenshots/source-user-network-admins.png)

* User authenticated as `meridian\netadmin.test`.

* **Traffic Log Result:** Outbound sessions to Google, Chase, and Wikipedia permitted cleanly with `SOURCE USER: netadmin.test`.

**Please enlarge for clearer video**

https://github.com/user-attachments/assets/6566b337-a9b1-4e42-9089-cead5c8bcfe0

#### Test B: Restricted Contractor Drop (contractor.test)
**Source User: meridian/contractors**

![Palo Alto](screenshots/source-user-contractors.png)

* User authenticated as `meridian\contractor.test`.

* **Traffic Log Result (Monitor > Logs > Traffic):**
  Filtering on `( action eq 'drop' )` confirmed all outbound sessions were terminated:
  * *Source IP:* `10.10.10.10`
  * *Source User:* **`meridian\contractor.test`**
  * *Matched Rule:* **`Contractors-DENY`**
  * *Session End Reason:* **`policy-deny`**

**Please enlarge for clearer video**

https://github.com/user-attachments/assets/c364c0c3-90b8-48c4-98d5-ccb11600b33a

## Test C: DROP vs DENY: Client-Side Connection Behavior

### Browser Behavior: PR_CONNECT_RESET_ERROR Explained

When the Palo Alto firewall denies HTTPS traffic with a TCP Reset action, Firefox displays:

```
Secure Connection Failed
Error code: PR_CONNECT_RESET_ERROR

The page you are trying to view cannot be shown because 
the authenticity of the received data could not be verified.
```

This error occurs because:
1. Client initiates TCP handshake to `neverssl.com:443`
2. Firewall matches the **Contractors-DENY** security policy rule
3. Firewall immediately sends a **TCP RST** packet to terminate the connection
4. Firefox receives the reset before SSL/TLS negotiation completes
5. Browser interprets this as a potential security threat or connection tampering

![Palo Alto](screenshots/drop-to-deny-difference.png)

![Palo Alto](screenshots/drop-to-deny-secure-connection-failed.png)

---

### Identity Telemetry Audit Trails

#### User-ID Log Audit (Monitor > Logs > User-ID)
Audited the dynamic logon tracking:
* *IP:* `10.10.10.10` | *User:* `richard.palo` / `netadmin.test` / `contractor.test`
* *Data Source:* `captive-portal` | *Source Type:* `authenticate` | *Timeout:* `3600s`.

![Palo Alto](screenshots/monitor-traffic-with-user-id.png)

#### Authentication Log Audit (Monitor > Logs > Authentication)
Audited the raw authentication transactions:
* *Event:* `Authentication Success` vs. `User Password Failure`.
* *Server Profile:* `Corp-AD-LDAP` | *Server Address:* `172.16.109.133`.
* *Normalized User:* `meridian\netadmin.test`.

![Palo Alto](screenshots/monitor-authentication-logs.png)

#### Traffic Log Verification (SOURCE USER Populated)
In `Monitor > Logs > Traffic`, sessions that previously displayed `[blank]` now explicitly log the authenticated domain identity:
* `10.10.10.10` ➔ `SOURCE USER: netadmin.test` ➔ `Action: allow` (Rule: `Network-Admins-Allow`).
* `10.10.10.10` ➔ `SOURCE USER: meridian\contractor.test` ➔ `Action: drop` (Rule: `Contractors-DENY`).

![Palo Alto](screenshots/monitor-traffic-logs-contractor-drops.png)

![Palo Alto](screenshots/monitor-traffic-netadmin-test.png)

---

## Key Artifact Index

A curated index of the primary engineering proofs, telemetry audits, and verification artifacts:

| Artifact File | Category | Technical Proof & Validation |
| :--- | :--- | :--- |
| **`active-directory-ou-users.png`** | AD DS Core | Windows Server ADUC displaying `Meridian Users` and `Meridian Groups` OUs. |
| **`ldap-profile-config.png`** | Identity Config | LDAP Server Profile configuring bind to domain controller `172.16.109.133`. |
| **`group-mapping-include-list.png`** | Identity Config | Group mapping setting enrolling `network-admins`, `network-users`, and `contractors`. |
| **`auth-portal-pki-certs.png`** | PKI Infrastructure | Table verifying `AUTH-PORTAL-ROOT-CA` and server cert with IP SAN `10.10.10.1`. |
| **`interface-mgmt-profile-auth.png`** | Network Config | Management profile on `ethernet1/2` enabling `Response Pages` and `User-ID`. |
| **`captive-portal-login-screen.png`** | Browser Interception | Branded PAN-OS Authentication Portal prompting for corporate AD credentials. |
| **`cli-test-auth-success.png`** | CLI Diagnostic | `test authentication` confirming successful LDAP bind for `netadmin.test`. |
| **`cli-show-user-ip-mapping.png`** | Dataplane State | `show user ip-user-mapping` verifying `10.10.10.10` mapped to `richard.palo` via `CP`. |
| **`cli-show-user-ids-groups.png`** | Dataplane State | `show user user-ids all` displaying active AD group-to-user membership mapping. |
| **`cli-policy-match-contractor-drop.png`** | Control Plane CLI | `test security-policy-match` proving `contractor.test` matches `Contractors-DENY`. |
| **`cli-policy-match-admin-allow.png`** | Control Plane CLI | `test security-policy-match` proving `netadmin.test` matches `Network-Admins-Allow`. |
| **`monitor-logs-authentication.png`** | Telemetry Log | Authentication log auditing success and password failure events against AD. |
| **`monitor-logs-traffic-user-populated.png`** | Telemetry Log | Traffic log confirming `SOURCE USER` populated with authenticated domain identity. |
| **`monitor-logs-traffic-contractor-drop.png`** | Telemetry Log | Traffic log proving mid-flow drop of `contractor.test` under `Contractors-DENY`. |

---












## Understanding DROP vs DENY: Client-Side Connection Behavior

### Browser Behavior: PR_CONNECT_RESET_ERROR Explained

When the Palo Alto firewall denies HTTPS traffic with a TCP Reset action, Firefox displays:

```
Secure Connection Failed
Error code: PR_CONNECT_RESET_ERROR

The page you are trying to view cannot be shown because 
the authenticity of the received data could not be verified.
```

This error occurs because:
1. Client initiates TCP handshake to `neverssl.com:443`
2. Firewall matches the **Contractors-DENY** security policy rule
3. Firewall immediately sends a **TCP RST** packet to terminate the connection
4. Firefox receives the reset before SSL/TLS negotiation completes
5. Browser interprets this as a potential security threat or connection tampering






