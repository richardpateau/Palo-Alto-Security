# Custom App-ID Signature Engineering & Protocol Decoders

A production-grade implementation of **Custom Layer 7 Application Signature Engineering** on Palo Alto Networks PAN-OS 11.2.5. This project documents the complete reverse-engineering workflow: capturing unclassified network traffic, isolating Layer 7 protocol patterns in Wireshark, compiling a custom App-ID object (**`portquiz-8888`**) using transaction-scoped protocol decoders, and enforcing Zero Trust security policies restricted strictly to `application-default` ports.

When an internal client (`10.10.10.10`) communicates over non-standard service ports (such as HTTP on TCP port 8888), standard firewall policies drop the traffic as `not-applicable` / `DENY_TRAFFIC`. By extracting the raw packet stream from firewall-generated captures (`portquiz8888-drop.pcap`), a custom signature was engineered utilizing the **`http-req-host-header`** context with parent application **`web-browsing`**.

Every stage—from capture staging and Wireshark stream reconstruction to live hardware session tables (`show session all filter application portquiz-8888`), clean session teardowns (`tcp-fin`), and negative-test port evasion drops—was validated across the data plane.

---

## Architectural Workflow: PCAP-to-App-ID Pipeline

![Palo Alto](screenshots/custom-app-id-draw-io.png)

---

## Application & Protocol Decoder Specifications

| Parameter | Configuration Setting | Engineering Function & Rationale |
| :--- | :--- | :--- |
| **Application Name** | `portquiz-8888` | Custom enterprise Layer 7 application identifier. |
| **Category / Subcategory** | `general-internet` / `internet-utility` | Risk taxonomy and reporting classification. |
| **Parent Application** | **`web-browsing`** | **Critical:** Instructs the Single-Pass engine to initialize the HTTP protocol decoder before evaluating signature contexts. |
| **Standard Ports** | **`tcp/8888`** | Binds the custom application to port 8888 for `application-default` policy enforcement. |
| **Signature Name** | `portquiz-host-sig` | Container for the pattern-matching logic. |
| **Signature Scope** | **`Transaction`** | Evaluates individual client request / server response transactions. |
| **Context** | **`http-req-host-header`** | Scans the HTTP `Host:` header field within the decoded client request. |
| **Pattern Match (Regex)** | **`portquiz\.net:8888`** | Exact regular expression match ensuring escaped dot delimiter syntax. |

---

### Initial State: Unclassified Application Drop & Endpoint Timeout

#### A. Client-Side Experience: Connection Timeout (`curl`)
From the workstation (`10.10.10.10`), a standard HTTP request was sent to the test server over non-standard port 8888:

```bash
rich@mx:~$ curl http://portquiz.net:8888
curl: (28) Failed to connect to portquiz.net port 8888 after 134091 ms: Could not connect to server
```

* **Client Result:** The connection hung for over 2 minutes (134,091 ms) before failing with `curl error 28`. Because the firewall dropped the initial SYN packet without sending a TCP RST, the client OS repeatedly retransmitted until its socket timer expired.

![Palo Alto](screenshots/pc-curl-fail.png)

---

#### B. Firewall Telemetry: Pre-State Drop (`Monitor > Logs > Traffic`)
Inspecting the traffic monitor for destination IP `35.180.86.68` (portquiz.net) confirmed why the connection failed:

| Field | Monitored Metric | Technical Analysis |
| :--- | :--- | :--- |
| **Source Address** | `10.10.10.10` (`Trust`) | Internal workstation initiating connection. |
| **Destination Address** | `35.180.86.68` (`Untrust`) | Target server IP on the public internet. |
| **Destination Port** | `8888` / `8888` | Non-standard port. |
| **Application** | **`not-applicable`** | Handshake never completed; App-ID engine had zero payload to inspect. |
| **Action** | **`drop`** | Silently discarded. |
| **Matched Rule** | **`DENY_TRAFFIC`** | Failed `application-default` constraints of rule 1; fell to bottom cleanup. |
| **Session End Reason** | **`policy-deny`** | Blocked by security policy. |
| **Total Bytes** | **`78 bytes`** | **Critical Detail:** Exactly one 78-byte TCP SYN packet was evaluated. |

![Palo Alto](screenshots/monitor-traffic-logs-filter-port-quiz-888.png)

#### C. The Reverse-Engineering Dilemma & Temporary Capture Staging (`Temp-Capture-888`)

Because `DENY_TRAFFIC` dropped the session at the very first TCP SYN packet (78 bytes), **no Layer 7 HTTP payload reached the firewall**. A packet capture taken at this initial stage would contain only an unhelpful TCP SYN frame with zero payload bytes to write a signature against.

To resolve this problem  without creating a wide-open security vulnerability, a tightly scoped temporary rule was configured:

##### 1. Temporary Service Object Creation (`tcp-888`)
Under **Objects > Services**, a custom service object was created to isolate destination port 8888:
* **Name:** `tcp-888`
* **Protocol:** `TCP` | **Destination Port:** `8888`

![Palo Alto](screenshots/creating-temp-service-8888.png)

##### 2. Scoped Temporary Rule Construction (`Policies > Security`)
Under **Policies > Security**, rule **`Temp-Capture-888`** was positioned above cleanup rules:
* **General:** Name: `Temp-Capture-888` | Type: `universal`
* **Source:** Zone: `Trust` | Address: **`10.10.10.10`** *(Strictly locked to the test client IP to prevent network-wide exposure)*
* **Destination:** Zone: `Untrust` | Address: `any`
* **Application:** **`unknown-tcp`** *(Permits provisional TCP handshake before Layer 7 App-ID classification)*
* **Service:** **`tcp-888`** (Port 8888)
* **Action:** `Allow`

**Security Rule - General**

![Palo Alto](screenshots/temp-security-rule-general.png)

**Security Rule - Source**

![Palo Alto](screenshots/temp-security-rule-source.png)

**Security Rule - Destination**

![Palo Alto](screenshots/temp-security-rule-destination.png)

**Security Rule - Application**

![Palo Alto](screenshots/temp-security-rule-application.png)

**Security Rule - Service**

![Palo Alto](screenshots/temp-security-rule-service.png)

---

## Multi-Phase Implementation 

### Phase 1: Capture Staging & Baseline Drop
1. **Firewall Capture Filter Configuration (`Monitor > Packet Capture`):**
   * Filter 1: Source: `10.10.10.10` | Destination: `0.0.0.0` | Enabled: **`ON`**.
2. **Capture Stages Configured:**
   * Stage `receive` ➔ File: `portquiz8888-rx.pcap`
   * Stage `drop` ➔ File: `portquiz8888-drop.pcap`
   * Capture Engine: Toggled **`ON`**.
3. **Trigger Baseline Drop:**
   Client workstation (`10.10.10.10`) initiated an HTTP request to `http://portquiz.net:8888`.
4. **PCAP Extraction:**
   Capture was stopped and downloaded from the firewall to:
   `/home/rich/Documents/Palo-Alto-Security/Project 13 Custom App-ID Signature Engineering & Protocol Decoders/pcap/monitor-pcap-filter-configuring-capture.png`.

**Filter - Source (10.10.10.10)**

![Palo Alto](screenshots/monitor-pcap-filter-config.png)

**Packet Capture Overview**

![Palo Alto](screenshots/monitor-pcap-filter-configuring-capture.png)

**File Saved from Palo Alto GUI: monitor-pcap-filter-configuring-capture.png**

![Palo Alto](screenshots/pcap-file-saved.png)

---

### Phase 2: Reverse-Engineering Payload in Wireshark

> 📥 **[Download Raw PCAP: `portquiz8888-drop.pcap`](pcap/portquiz8888-drop.pcap)**

Opening `portquiz8888-drop.pcap` and following **TCP Stream 0** revealed the exact 81-byte unencrypted HTTP request:

```http
GET / HTTP/1.1
Host: portquiz.net:8888
User-Agent: curl/8.14.1
Accept: */*
```

* **Signature Anchor Selection:**
  The `Host: portquiz.net:8888` line provided a distinct, 17-byte Layer 7 pattern. By binding to the `http-req-host-header` context, the firewall inspects only the structured Host header field rather than running costly full-packet raw regex searches.

**Overview**

![Palo Alto](screenshots/pcap-overview.png)

**TCP Stream Output**

![Palo Alto](screenshots/pcap-follow-tcp-stream-output.png)

---

### Phase 3: Compiling Custom App-ID (`portquiz-8888`)

1. Navigate to **Objects > Applications** > Click **Add**:
   * **Configuration Tab:**
     * Name: `portquiz-8888`
     * Category: `general-internet` | Subcategory: `internet-utility`
     * Technology: `browser-based` | Risk: `1`
     * **Parent App:** **`web-browsing`**
   * **Advanced Tab:**
     * Defaults: Select **`Port`** ➔ Click **Add** ➔ Enter: **`tcp/8888`**.
   * **Signatures Tab:**
     * Click **Add** ➔ Name: `portquiz-host-sig` | Scope: **`Transaction`**.
     * Check: **`Ordered Condition Match`**.
     * Add Condition:
       * Operator: **`Pattern Match`**
       * Context: **`http-req-host-header`**
       * Pattern: **`portquiz\.net:8888`**
2. Click **OK** twice.

**Object > Applications > Configuration**

![Palo Alto](screenshots/configuring-custom-app.png)

**Configuring Signature Condition**

![Palo Alto](screenshots/configuring-custom-app-configuring-signature-condition.png)

![Palo Alto](screenshots/configuring-custom-app-creating-signature-overview.png)

**Object > Applications > Signature**

![Palo Alto](screenshots/configuring-custom-app-creating-signatures.png)

**Object > Applications > Advanced**

![Palo Alto](screenshots/configuring-custom-app-advanced.png)

---

### Phase 4: Deploying Security Policies with `application-default`

Configured a dedicated security rule placed above general cleanup drops:

1. Navigate to **Policies > Security** > Rule **`Allow-Port-Quiz-8888`**:
   * **Source Zone:** `Trust` | **Source Address:** `LAN 10.10.10.0/24`
   * **Destination Zone:** `Untrust` | **Destination Address:** `any`
   * **Application:** **`portquiz-8888`**
   * **Service:** **`application-default`** *(Enforces that portquiz-8888 is permitted ONLY on tcp/8888)*
   * **Action:** **`Allow`**
2. Click **Commit**.

**Security Rule - General**

![Palo Alto](screenshots/security-rule-1-general.png)

**Security Rule - Source**

![Palo Alto](screenshots/security-rule-1-source.png)

**Security Rule - Destination**

![Palo Alto](screenshots/security-rule-1-destination.png)

**Security Rule - Application**

![Palo Alto](screenshots/security-rule-1-application.png)

**Order**

![Palo Alto](screenshots/policy-security-overview.png)

---

## Empirical Verification & Technical Proof

### Hardware Session Table Verification (`show session all`)

While traffic was actively flowing from the client, the firewall session state table was queried from the CLI:

```text
admin@PA-VM> show session all filter application portquiz-8888

ID    Application   State  Type Flag Src[Sport]/Zone/Proto (translated IP[Port])
                                     Dst[Dport]/Zone (translated IP[Port])
--------------------------------------------------------------------------------
45392 portquiz-8888 ACTIVE FLOW NS   10.10.10.10[33228]/Trust/6 (192.168.1.200[26267])
                                     35.180.86.68[8888]/Untrust (35.180.86.68[8888])
45389 portquiz-8888 ACTIVE FLOW NS   10.10.10.10[33214]/Trust/6 (192.168.1.200[38508])
                                     35.180.86.68[8888]/Untrust (35.180.86.68[8888])
45363 portquiz-8888 ACTIVE FLOW NS   10.10.10.10[33190]/Trust/6 (192.168.1.200[63691])
                                     35.180.86.68[8888]/Untrust (35.180.86.68[8888])
45387 portquiz-8888 ACTIVE FLOW NS   10.10.10.10[33212]/Trust/6 (192.168.1.200[32396])
                                     35.180.86.68[8888]/Untrust (35.180.86.68[8888])
```

* **Dataplane Proof:** The application column actively displays **`portquiz-8888`** instead of `web-browsing` or `unknown-tcp`.
* **State & Flags:** Sessions are in state **`ACTIVE`** with flag **`NS`** (NAT + Proxy State active), confirming clean address translation to public IP `192.168.1.200`.

![Palo Alto](screenshots/show-session-all-filter-application-portquiz.png)

---

### Traffic Log Audit: Positive Match vs. Negative Port Evasion

#### A. Positive Match (Authorized Custom App on Port 8888)
* **Log Filter:** `( addr.src in '10.10.10.10' ) and ( rule eq 'Allow-Port-Quiz-8888' )`
* **Observed Metrics:**
  * **Application:** **`portquiz-8888`**
  * **Destination Port:** `8888`
  * **Action:** **`allow`**
  * **Session End Reason:** **`tcp-fin`** (Full bidirectional payload exchange; clean TCP teardown).
  * **Bytes Exchanged:** **`3.5 KB – 3.8 KB`** per session.

![Palo Alto](screenshots/monitor-traffic-logs-filter-port-quiz-8888.png)

#### B. Negative Test: Port Evasion Defense (Unauthorized Port 8889)
To prove that `application-default` prevents arbitrary traffic from hijacking custom rules, traffic was sent to port 8889 on the identical destination server:

* **Log Filter:** `( addr.src in '10.10.10.10' ) and ( port.dst eq '8889' )`
* **Observed Metrics:**
  * **Application:** `not-applicable`
  * **Destination Port:** `8889`
  * **Action:** **`drop`**
  * **Rule Matched:** **`DENY_TRAFFIC`**
  * **Session End Reason:** **`policy-deny`**
  * **Bytes:** **`78 bytes`** (Terminated at TCP SYN; zero payload admitted).

![Palo Alto](screenshots/zero-trust-monitor-traffic-logs-denied-port-quiz-8889.png)

---

## Key Artifact Index

| Artifact File | Category | Technical Proof & Validation |
| :--- | :--- | :--- |
| **`pcap/portquiz8888-drop.pcap`** | Raw PCAP | Raw packet capture containing the 81-byte HTTP payload used for reverse engineering. |
| **`pcap-follow-tcp-stream-output.png`** | Payload Analysis | Wireshark TCP Stream 0 displaying `Host: portquiz.net:8888` client header. |
| **`monitor-pcap-filter-configuring-capture.png`** | Packet Capture | PAN-OS capture settings configuring stages `receive` and `drop` filtered on client IP. |
| **`configuring-custom-app.png`** | Object Config | App-ID configuration setting Parent App to `web-browsing` and Risk to 1. |
| **`configuring-custom-app-advanced.png`** | Object Config | Advanced defaults setting standard listening port to `tcp/8888`. |
| **`configuring-custom-app-configuring-signature-condition.png`** | Signature Config | Regex pattern match definition (`portquiz\.net:8888`) under `http-req-host-header`. |
| **`security-rule-1-application.png`** | Security Policy | Rule `Allow-Port-Quiz-8888` permitting custom app on `application-default`. |
| **`show-session-all-filter-application-portquiz.png`** | Dataplane CLI | CLI session table verifying active flows classified as `portquiz-8888`. |
| **`monitor-traffic-logs-filter-port-quiz-8888.png`** | Telemetry Log | Traffic log confirming `portquiz-8888` sessions allowed with `tcp-fin` teardown. |
| **`zero-trust-monitor-traffic-logs-denied-port-quiz-8889.png`** | Security Proof | Traffic log proving port 8889 dropped by `DENY_TRAFFIC` under `application-default`. |

---
