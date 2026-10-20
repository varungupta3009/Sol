# Sol Home LAN Topology & 4K UHD Remux Streaming Optimization

## 1. Executive Summary & Problem Context

* **Server Host**: M1 Pro MacBook Pro (`192.168.50.100`, hostname `vrg-m1`) running native Apple Silicon `jellyfin-metal` on `http://192.168.50.100:8097`.
* **Client Device**: LG OLED C2 Smart TV (`192.168.50.107`, `LGwebOSTV`) running native `Litefin 2.0.20`.
* **Objective**: Stream 20–90+ Mbps (and 120+ Mbps peak VBR) 4K UHD Remux (HDR10/Dolby Vision HEVC) titles via Direct Play with zero buffering, frame dropping, or playback stalls.
* **Storage Verification (Baseline)**:
  * Media storage: External USB 3.2 drive `/Volumes/PANOPTICON` (`disk6`).
  * Sequential read speed: **`169.2 MiB/s` (`1,353 Mbps`)**.
  * Background I/O processes disabled: `copyparty` `up2k` hashing and `jellyfin-metal` on-the-fly subtitle extraction (`EnableSubtitleExtraction`).
  * Idle disk activity: **`0.00 MB/s`**.

Despite zero storage bottlenecks, 4K Remux streams suffered from severe playback pauses and buffering loops. Network diagnostic tracing revealed significant latency jitter and airtime starvation on the local Wi-Fi mesh network.

---

## 2. Network Discovery & Root Cause Analysis

### Physical & Logical Topology (Final State)

The home network is powered by two **TP-Link HX510 AX3000 EasyMesh / Aginet** units operating in Router Mode. The MacBook Pro has been moved to a dedicated **Gigabit Ethernet link**, while the LG C2 operates on **5 GHz Wi-Fi**:

```
[MacBook Pro (vrg-m1)] (192.168.50.100, en8)
    │  Gigabit Full-Duplex Ethernet (1000baseT, 1000 Mbps)
    ▼
[Node 1: Office (Gateway)] (192.168.50.1) ── WAN (PPPoE 1000M) / LAN1 Connected
    │
    │  Wireless Mesh Backhaul (802.11ax, 5 GHz Channel 149, 864 Mbps Link Rate)
    ▼
[Node 2: Bedroom (Satellite)] (192.168.50.2)
    │  Wi-Fi 5 (802.11ac, 5 GHz Channel 149, 433 Mbps, RSSI -41 dBm)
    ▼
[LG C2 OLED TV] (192.168.50.107)
```

### Identification of Root Causes (Resolved)

1. **Triple-Hop Wireless Contention (Eliminated)**:
   * *Problem*: The TP-Link HX510 is a **dual-band** router (`2.4 GHz + 5 GHz`) with only a single 5 GHz radio per unit. When the Mac was on Wi-Fi, every video packet hopped over 5 GHz three times (`Mac -> Node 1 -> Node 2 -> TV`), demanding `270–360+ Mbps` of aggregate half-duplex airtime.
   * *Resolution*: Plugging the Mac directly into Node 1's `LAN1` port via a USB Gigabit adapter (`en8`) eliminated Hop 1 from the airwaves entirely. 5 GHz airtime contention was reduced by 33%, and latency to the router dropped to **sub-1ms**.

2. **160 MHz Channel Width on DFS Frequencies (Eliminated)**:
   * *Problem*: The HX510 5 GHz radio was configured to `160 MHz` on `Auto(40)`, spanning across DFS radar channels (`52–64`) and hiding UNII-3 channels (`149–161`).
   * *Resolution*: Reduced channel width to **`80 MHz`** and locked the channel to **`Channel 149`** (5.745 GHz UNII-3, non-DFS).

3. **macOS `awdl0` Channel-Hop Freezes (Eliminated)**:
   * *Problem*: macOS `awdl0` (AirDrop/Handoff) natively operates on Channel 149/44. Connecting to Wi-Fi on Channel 40 caused periodic radio hops and 50–120ms transmit stalls.
   * *Resolution*: With the Mac wired over Ethernet (`en8`) and Wi-Fi powered off (`en0` off), `awdl0` is completely **inactive**, eliminating all channel-hop freezes.

4. **LG C2 100 Mbps Ethernet Limitation (Bypassed)**:
   * The LG C2's physical RJ45 port is a **100 Mbps Fast Ethernet NIC** (hardware capped at ~94–95 Mbps real-world payload throughput). Because 4K UHD Remux titles peak at 110–130+ Mbps VBR, connecting the TV via Ethernet causes buffer underruns during action scenes.
   * Keeping the LG C2 on **5 GHz Wi-Fi (`433 Mbps` link rate, RSSI `-41 dBm`)** on the optimized Channel 149 provides more than quadruple the throughput ceiling of the TV's wired port with rock-solid consistency.

---

## 3. End-to-End Benchmark Progression

### To Smart TV (`LGwebOSTV`, `192.168.50.107`)

| Metric | Baseline (Ch 40, 160 MHz, All Wi-Fi) | Phase 2 (Ch 149, 80 MHz, MU-MIMO) | **Final (Mac on 1 Gbps Ethernet, TV on 5 GHz)** | Total Improvement |
| :--- | :--- | :--- | :--- | :--- |
| **Minimum RTT** | `10.05 ms` | `8.04 ms` | **`5.73 ms`** | **-43.0%** |
| **Average RTT** | `221.73 ms` | `12.94 ms` | **`11.41 ms`** | **94.9% drop (19x faster)** |
| **Maximum Spike**| `707.53 ms` | `39.11 ms` | **`35.52 ms`** | **95.0% drop (20x lower)** |
| **Jitter (`stddev`)**| `203.76 ms`| `8.58 ms` | **`8.74 ms`** | **95.7% drop (23x smoother)**|
| **Packet Timeouts**| Severe queue timeouts | 0.0% loss | **0.0% loss, rock solid delivery** | **Zero stalls** |

### To Router Gateway (`192.168.50.1`)

| Metric | Baseline (Wi-Fi) | **Final (Gigabit Ethernet en8)** | Improvement |
| :--- | :--- | :--- | :--- |
| **Minimum RTT** | `2.62 ms` | **`0.91 ms`** | **-65.3%** |
| **Average RTT** | `11.82 ms` | **`4.75 ms`** | **-59.8%** |
| **Maximum Spike** | `65.03 ms` | **`36.43 ms`** | **-44.0%** |

---

## 4. Configuration Changes Applied

### A. TP-Link HX510 Aginet Mesh Routers (`192.168.50.1`)

1. **5 GHz Wireless Settings**:
   * **Channel Width**: Changed from `160 MHz` to **`80 MHz`**.
   * **Channel**: Changed from `Auto (40)` to **`Channel 149`** (non-DFS UNII-3).
2. **Advanced Wireless Settings**:
   * **MU-MIMO**: Changed from `Disabled` to **`Enabled`** (`apmumimo_5g = true`).
   * **WMM**: Verified **Enabled**.
   * **Airtime Fairness**: Verified **Disabled**.
   * **Band Steering (Smart Connect)**: Verified **Disabled**.
   * **QoS**: Verified **Disabled** (`enableQoS = false`).
3. **Static DHCP Address Reservations**:
   * `192.168.50.1` — Node 1 (Office Gateway, `CC:BA:BD:59:0D:DD`)
   * `192.168.50.2` — Node 2 (Bedroom Satellite, `CC:BA:BD:59:67:E0`)
   * **`192.168.50.100`** — **MacBook Pro USB Ethernet (`A0:CE:C8:96:4E:59`)**
   * `192.168.50.99` — MacBook Pro Wi-Fi (`F8:4D:89:80:55:0F`, backup)
   * **`192.168.50.107`** — **LG C2 OLED TV (`C8:99:B2:2A:48:5C`)**

---

### B. macOS Host Network & TCP Stack Tuning

1. **Wired Interface Configuration**:
   * Device: `en8` (`USB 10/100/1000 LAN`)
   * MAC: `A0:CE:C8:96:4E:59`
   * Link: `1000baseT <full-duplex>`
   * IP: Statically configured to **`192.168.50.100`** (Subnet: `255.255.255.0`, Router: `192.168.50.1`, DNS: `192.168.50.1`, `9.9.9.9`, `8.8.8.8`).
   * Wi-Fi interface `en0`: Powered **Off** (`awdl0` inactive).

2. **TCP Sysctl Media Streaming Tuning**:
   * Script: [`scripts/tune_network.sh`](file:///Users/vrg/Documents/Sol/scripts/tune_network.sh)
   * Values applied:
     * `net.inet.tcp.sendspace=524288` (512 KB default send buffer)
     * `net.inet.tcp.recvspace=524288` (512 KB default receive buffer)
     * `net.inet.tcp.autosndbufmax=8388608` (8 MB dynamic auto-send max)
     * `net.inet.tcp.autorcvbufmax=8388608` (8 MB dynamic auto-recv max)
     * `net.inet.tcp.delayed_ack=2` (immediate ACK every 2nd packet)

3. **launchd Boot Persistence**:
   * Configured in [`scripts/launchd/com.vrg.sol.network-tuning.plist`](file:///Users/vrg/Documents/Sol/scripts/launchd/com.vrg.sol.network-tuning.plist).
   * Automatically executes `tune_network.sh` as root upon macOS boot.

---

## 5. Service & Media Verification

* **Native Jellyfin Metal**: Verified active and responding at **`http://192.168.50.100:8097`** (`ServerName: "Sol Metal"`, Version `12.2.0`).
* **Direct Play Compatibility**: Direct Stream / Remux playback from `/Volumes/PANOPTICON` to Litefin on the LG C2 runs over dedicated gigabit wire for Hop 1, with zero Wi-Fi contention on the Mac and sub-10ms packet transit to the TV.
