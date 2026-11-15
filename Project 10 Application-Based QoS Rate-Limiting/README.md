# Application-Based QoS Rate-Limiting, Traffic Shaping & Priority Queueing

A production-grade implementation of **Layer 7 Application-Based Quality of Service (QoS)** and egress traffic shaping on Palo Alto Networks PAN-OS 11.2.5. This project documents the design, deployment, and live data-plane validation of hierarchical bandwidth management on the external perimeter interface (`ethernet1/1`).

By decoupling security policy inspection from hardware rate-limiting, the firewall classifies traffic via App-ID and enqueues flows into distinct priority queues (Classes 1–8). An aggressive bulk data stream (`iperf3`) simulating a "noisy neighbor" bandwidth hog was clamped to a **hard 2.0 Mbps ceiling**, dropping over **4.42 million excess packets** at the queue buffer. Concurrently, business web and interactive traffic (`Class 1`) was prioritized to consume up to its **10.0 Mbps maximum guarantee** with zero bufferbloat or starvation.

Every rate ceiling, queue plateau, and packet drop metric was verified using real-time Wireshark I/O throughput graphs, dataplane throughput monitors (`show qos interface ethernet1/1 throughput 0`), and hardware queue drop counters (`show qos interface ethernet1/1 counter`).

**Live PCAP I/O Graph**

---

## Architectural Workflow: Hierarchical Egress Shaping Pipeline

In PAN-OS, QoS operates on the **egress queues of existing data-plane interfaces**. Packets entering `ethernet1/2` (Trust) and exiting `ethernet1/1` (Untrust) are inspected by App-ID, tagged with a QoS Class, and scheduled through a Hierarchical Fair Service Curve (HFSC) queue engine.

![Palo Alto](screenshots/qos-draw-io.png)

---

## Bandwidth Allocation & Queue Specification

| QoS Queue Class | Priority Level | Target Application / Traffic | Guaranteed Bandwidth | Maximum Bandwidth (Ceiling) | Engineering Function |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Interface Ceiling**| Total Pipe | All egress traffic leaving `ethernet1/1` | **10.0 Mbps** | **10.0 Mbps** | Global interface shaping ceiling |
| **Class 1** | **Real-Time** | Critical Web & Management (`ssl`, `web-browsing`, `ping`, `ssh`) | **5.0 Mbps** (5,000 kbps) | **10.0 Mbps** (10,000 kbps) | Guaranteed transmission; bursts to 10M under load |
| **Class 4** | **Medium** | Default Fallback Class | **2.0 Mbps** (2,000 kbps) | **8.0 Mbps** (8,000 kbps) | Default PAN-OS unclassified traffic |
| **Class 8** | **Low** | Bulk Traffic / Synthetic Stress (`Any` / `iperf3`) | **0.0 Mbps** (0 kbps) | **2.0 Mbps** (2,000 kbps) | **Hard Clamped:** Discards packets exceeding 2.0 Mbps |

---

## Multi-Phase Implementation 

### Phase 1: Configure the Hierarchical QoS Profile
Defined the bandwidth ceiling and per-class rate limits:
* **Profile Name:** `Corp-Egress-Shaping-Profile`
* **Egress Max / Guaranteed:** `10 Mbps` / `10 Mbps`
* **Class Configuration:**
  * `Class 1`: Priority `Real-Time` | Egress Guaranteed: `5 Mbps` | Egress Max: `10 Mbps`
  * `Class 4`: Priority `Medium` | Egress Guaranteed: `2 Mbps` | Egress Max: `8 Mbps`
  * `Class 8`: Priority `Low` | Egress Guaranteed: `0 Mbps` | Egress Max: `2 Mbps`

![Palo Alto](screenshots/creating-qos-profile.png)

### Phase 2: Configure QoS Classification Policies (Refined for High-Load Validation)

During initial testing, standard ICMP (`ping`) payloads were too small to drive multi-megabit saturation. To properly stress-test Class 1, high-throughput web protocols (`ssl`, `web-browsing`) were added. Furthermore, because PAN-OS automatically places unclassified flows into Class 4 by default, the bulk clamping rule was set to match `Any` application to ensure `iperf3` was strictly locked into Class 8:

* **Rule 1 (`Prioritize-Mgmt-Voice`):**
  * Source: `Trust` (`LAN 10.10.10.0/24`) | Destination: `Untrust` (`any`)
  * Applications: **`ssl`**, **`web-browsing`**, **`ping`**, **`ssh`**
  * Action: Tag as **`Class 1`**
* **Rule 2 (`Clamp-Bulk-iPerf`):**
  * Source: `Trust` (`LAN 10.10.10.0/24`) | Destination: `Untrust` (`any`)
  * Applications: **`Any`** *(Catch-all to prevent bulk traffic defaulting to Class 4)*
  * Action: Tag as **`Class 8`**

**QOS Rule 1: General Tab**

![Palo Alto](screenshots/creating-qos-policy-rule-general.png)

**QOS Rule 1: Source**

![Palo Alto](screenshots/creating-qos-policy-rule-source.png)

**QOS Rule 1: Destination**

![Palo Alto](screenshots/creating-qos-policy-rule-destination.png)

**QOS Rule 1: Application**

![Palo Alto](screenshots/creating-qos-policy-rule-application.png)

**QOS Rule 1: Other**

![Palo Alto](screenshots/creating-qos-policy-rule-other.png)

**QOS Rule 2: General Tab**

![Palo Alto](screenshots/creating-qos-policy-rule-2-general.png)

**QOS Rule 2: Source**

![Palo Alto](screenshots/creating-qos-policy-rule-2-source.png)

**QOS Rule 2: Destination**

![Palo Alto](screenshots/creating-qos-policy-rule-2-destination.png)

**QOS Rule 2: Application**

![Palo Alto](screenshots/creating-qos-policy-rule-2-application.png)

**QOS Rule 2: Other**

![Palo Alto](screenshots/creating-qos-policy-rule-2-other.png)

### Phase 3: Bind QoS Profile to Physical Egress Port
Activated the hardware shaping engine on the WAN boundary:
* Navigate to **Network > QoS** > Click **Add**:
  * **Interface:** `ethernet1/1`
  * **Default Profile (Clear Text):** `Corp-Egress-Shaping-Profile`
  * **Turn on QoS feature on this interface:** Checked

![Palo Alto](screenshots/creating-qos-interface.png)

---

## Empirical Verification & Hardware Diagnostics

### 1. The 2.0 Mbps Hard Ceiling on Bulk Traffic (Class 8 Clamping)

An unconstrained bulk UDP stream was launched from the internal workstation (`10.10.10.10`) toward the external server targeting port 5201. 

Capturing packets on the external WAN bridge (`br-pa-wan`) in Wireshark produced empirical proof of egress clamping:

```text
Wireshark I/O Graph Analysis (Display Filter: _ws.col.protocol == "iPerf3"):
* Vertical Y-Axis  : Bits / 1 sec
* Horizontal X-Axis: Time (seconds)
* Rate Plateau      : Exactly 2.014e+06 bits/sec (2.014 Mbps)
```

* **Data-Plane Behavior:** Bulk traffic accelerated from zero, hit the configured rate limit at $t=4s$, and **flatlined at precisely 2.0 Mbps** for the remainder of the transfer.

![Palo Alto](screenshots/wireshark-io-graph-iperf3-2mbps.png)

---

### 2. Phase 1 Verification: 5.0 Mbps Class 1 Baseline Shaping

To verify that QoS classification and priority queueing were functioning before pushing maximum interface limits, high-priority web traffic (`ssl`/`web-browsing`) was introduced into **Class 1** with an initial rate limit of **5,000 kbps (5.0 Mbps)** alongside the saturated **Class 8 (2.0 Mbps)** bulk stream.

![Palo Alto](screenshots/testing-wireshark-io-graph-5mb.png)

#### Active Throughput Sampling (`show qos interface ethernet1/1 throughput 0`)

```text
admin@PA-VM> show qos interface ethernet1/1 throughput 0

QoS throughput for interface ethernet1/1, node default-group (Qid 0):
class 1:       5001 kbps    <-- Class 1 actively shaped to 5.0 Mbps baseline
class 8:       2003 kbps    <-- Class 8 pegged at 2.0 Mbps ceiling

admin@PA-VM> show qos interface ethernet1/1 throughput 0

QoS throughput for interface ethernet1/1, node default-group (Qid 0):
class 1:       4993 kbps
class 4:          2 kbps
class 8:       1999 kbps

admin@PA-VM> show qos interface ethernet1/1 throughput 0

QoS throughput for interface ethernet1/1, node default-group (Qid 0):
class 1:       5002 kbps
class 4:          2 kbps
class 8:       2003 kbps

admin@PA-VM> show qos interface ethernet1/1 throughput 0

QoS throughput for interface ethernet1/1, node default-group (Qid 0):
class 1:       4986 kbps
class 4:          0 kbps
class 8:       1999 kbps
```

* **Data-Plane Proof:** Class 1 stabilized at **`5,001 kbps`** while Class 8 remained locked at **`1,999 kbps`**, confirming that both queues were independently shaped according to policy.
* **Wireshark Wire Verification:** The I/O graph captured a steady plateau at **~4.4 Mbps**, matching effective payload delivery at the 5 Mbps queue limit.

![Palo Alto](screenshots/testing-5-mb-show-qos-interface-ethernet-throughput.png)

---

### 3. Phase 2 Verification: 10.0 Mbps Full Pipe Saturation & Priority Preemption

With baseline shaping confirmed, Class 1 was granted permission to burst up to the **full 10,000 kbps (10.0 Mbps) interface ceiling**. High-volume web traffic was generated concurrently with the 20 Mbps iPerf3 bulk stream to test queue preemption under maximum link contention.

#### Active Throughput Sampling (`show qos interface ethernet1/1 throughput 0`)

```text
admin@PA-VM> show qos interface ethernet1/1 throughput 0

QoS throughput for interface ethernet1/1, node default-group (Qid 0):
class 1:       9953 kbps    <-- Class 1 scaling up to consume available bandwidth
class 4:          1 kbps
class 8:       1999 kbps    <-- Class 8 held strictly at 1,999 kbps

admin@PA-VM> show qos interface ethernet1/1 throughput 0

QoS throughput for interface ethernet1/1, node default-group (Qid 0):
class 1:       9954 kbps
class 4:          3 kbps
class 8:       1999 kbps

admin@PA-VM> show qos interface ethernet1/1 throughput 0

QoS throughput for interface ethernet1/1, node default-group (Qid 0):
class 1:      10002 kbps    <-- Class 1 reaches full 10.0 Mbps interface ceiling
class 4:          2 kbps
class 8:       1999 kbps    <-- Zero bandwidth leakage permitted to Class 8

admin@PA-VM> show qos interface ethernet1/1 throughput 0

QoS throughput for interface ethernet1/1, node default-group (Qid 0):
class 1:          0 kbps    <-- Class 1 stream finishes
class 8:       1999 kbps    <-- Class 8 continues running at its 2.0 Mbps cap
```

* **Preemption Proof:** The HFSC scheduler allocated the full interface bandwidth to **Class 1 (`10,002 kbps`)**, while **Class 8** remained restricted to **`1,999 kbps`**.
* **Wireshark Wire Verification:** The I/O graph captured the combined saturation peak near **~8.8 Mbps wire rate**, proving maximum link utilization without starving high-priority traffic.

![Palo Alto](screenshots/show-qos-interface-ethernet-throughput.png)

**TCP - Class 1**

![Palo Alto](screenshots/wireshark-tcp-io-grapgh.png)

---

### 4. Hardware Queue Drop Telemetry (4.42 Million Discarded Packets)

Inspecting the underlying hardware queue counters confirmed that packets exceeding the Class 8 bandwidth ceiling were discarded at the interface buffer:

```text
admin@PA-VM> show qos interface ethernet1/1 counter

QoS counter for interface ethernet1/1:
number of queued packets: 106
Parent Qid node          base-bw ldshare max-bw  pass-pak  drop-pak time-out delay vtime qlen qlmt
-------------------------------------------------------------------------------------------------
  3      0 default-group   10000   10000  10000         0         0        0     0 31866112 0 150
            -Class 1        5000    5000  10000    124311       278        0     0 631942903 0 150
            -Class 4        2000    1500   8000      3946         0        0     0 798384777 0 150
            -Class 8           1     124   2000     38741   4429576      467   618 806375579 106 150
```

* **Hardware Metrics Analysis:**
  * **Class 1 (Real-Time / Critical):** Transmitted **124,311 packets** with minimal drops (`drop-pak: 278`), confirming near-zero loss under link saturation.
  * **Class 8 (Bulk / Noisy Neighbor):** Transmitted **38,741 packets** while **4,429,576 packets were dropped** (`drop-pak: 4429576`), confirming active queue truncation at the 2.0 Mbps rate limit.

![Palo Alto](screenshots/show-qos-interface-ethernet-counter.png)

## Key Artifact Index

| Artifact File | Category | Technical Proof & Validation |
| :--- | :--- | :--- |
| **`wireshark-io-graph-2mbps-plateau.png`** | Wire Telemetry | Wireshark I/O graph confirming bulk iPerf3 throughput clamped at a flat **2.01 Mbps**. |
| **`wireshark-io-graph-concurrent-streams.png`** | Wire Telemetry | Wireshark I/O graph documenting multi-class burst behavior and shaping transitions. |
| **`pa-cli-qos-throughput-5mbps-guarantee.png`** | Dataplane CLI | CLI telemetry showing Class 1 operating at `5,001 kbps` and Class 8 at `2,003 kbps`. |
| **`pa-cli-qos-throughput-10mbps-burst.png`** | Dataplane CLI | CLI telemetry showing Class 1 bursting to `10,002 kbps` while Class 8 is pinned to `1,999 kbps`. |
| **`pa-cli-qos-hardware-counters-4m-drops.png`** | Dataplane CLI | `show qos interface ethernet1/1 counter` confirming **4,429,576 packets dropped** on Class 8. |
| **`qos-profile-configuration-classes.png`** | Profile Config | GUI definition of `Corp-Egress-Shaping-Profile` configuring Classes 1, 4, and 8. |
| **`qos-policy-rule-prioritize-mgmt.png`** | Policy Config | QoS classification rule matching `ssl`, `web-browsing`, `ping`, `ssh` targeting **Class 1**. |
| **`qos-policy-rule-clamp-iperf.png`** | Policy Config | QoS classification rule matching `Any` targeting **Class 8** to prevent Class 4 default leakage. |
| **`qos-interface-attachment-eth1-1.png`** | Interface Config | Binding `Corp-Egress-Shaping-Profile` to egress WAN port `ethernet1/1`. |
| **`wireshark-iperf3-packet-stream.png`** | Wire Trace | Raw packet capture documenting high-rate 1490-byte iPerf3 UDP payloads on WAN. |

---
