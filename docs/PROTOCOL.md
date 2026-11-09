# RadiaCode Device Protocol Reference

This document describes the wire protocol used by RadiaCode radiation detectors
(RC-10x / RC-110 family, firmware 4.14–4.15). It is intended as a complete
reference for implementing the protocol on other platforms and languages.

The canonical Python implementation lives in `src/radiacode/`. The wire formats
described here were verified against debug logs captured from the Android app
(`radiacode` for Android).

## 1. Framing

Every request and response is wrapped in a **4-byte little-endian length
prefix**:

```
┌──────────────────┬──────────┬──────────┐
│ 4 bytes          │ 4 bytes  │  payload │
│ length (u32, LE) │ header   │  ...     │
└──────────────────┴──────────┴──────────┘
```

- `length` = size of everything **after** the length prefix (header + payload),
  as a little-endian `uint32`. Example: `00000008` = 8.
- The payload is command-specific (see below).

## 2. Header (requests AND responses)

The header is **4 bytes**, identical in format for requests and responses:

```
Byte 0-1 : command id (uint16, little-endian)
Byte 2   : 0x00 (reserved / always zero)
Byte 3   : sequence number (uint8)
```

Example: `25 08 00 8A` = command `0x0825`, reserved `0`, sequence `0x8A`.

> **Debug-log note:** The Android app's debug logs *display* the header as
> `seq 00 cmd_be` (e.g. `8A 00 08 25`), which is a display normalization.
> The actual bytes on the wire are `cmd_le 00 seq`, as confirmed by the raw
> received-bytes dump. Do not copy the display order.

**Sequence numbers:** the reference implementation numbers requests starting at
`0x80` and increments by one for each request, wrapping modulo 32 - so sequence
values cycle through `0x80`..`0x9F`. It is safe for other implementations to
start anywhere and simply increment.

**Response echo:** every response echoes the *complete* request header - command
id, reserved byte, and sequence number - not just the sequence. The reference
implementation asserts the four header bytes match exactly; a response whose
header does not echo the request should be treated as a protocol error.

## 3. Common response layout

The header is echoed back in every response; beyond that the layout is
command-specific:

- **Scalar / fixed-structure commands** (`GET_STATUS`, `GET_VERSION`,
  `GET_SERIAL`, `FW_SIGNATURE`, `SET_EXCHANGE`, `SET_TIME`) return their
  fields immediately after the header - **no `retcode`**. `SET_TIME` returns
  only the echoed header, with no body at all.
- **Register / virtual-string operations** (`RD_VIRT_SFR`, `WR_VIRT_SFR`,
  `RD_VIRT_SFR_BATCH`, `WR_VIRT_SFR_BATCH`, `RD_VIRT_STRING`,
  `WR_VIRT_STRING`) begin with a `retcode (u32)` that is `1` on success and
  `0` on failure.
- Some commands add a `flen` field (see string reads below).

The sequence number is echoed back in the response header; implementations
should match it.

## 4. Commands

The `COMMAND` enum in `types.py` lists all known command ids. Key ones:

| Name                 | Id     | Payload                          | Response                           |
|----------------------|--------|----------------------------------|------------------------------------|
| SET_EXCHANGE         | 0x0007 | `01 FF 12 FF`                    | TARGET_ID(u32) TX(u16) RX(u16) IF_READY(u8) IF_TYPE(u8) - no retcode |
| GET_STATUS           | 0x0005 | -                                | status flags (u32) - no retcode    |
| GET_VERSION          | 0x000A | -                                | see §5                            |
| GET_SERIAL           | 0x000B | -                                | see §5                            |
| FW_SIGNATURE         | 0x0101 | -                                | signature + 2 strings              |
| FW_IMAGE_GET_INFO    | 0x0012 | -                                | image info - see §4.3             |
| FW_IMAGE_WRITE       | 0x0013 | signature offset count data      | retcode(u32) - see §4.3           |
| FW_IMAGE_UPDATE      | 0x0014 | exchange_target zero signature   | retcode(u32) value(u32) - see §4.3 |
| RD_FLASH_AREA        | 0x081C | area index (u32)                 | header + status(u32) seed(u32) enc_size(u32) encrypted area |
| RD_HW_CONFIG         | 0x0807 | -                                | hardware config                    |
| RD_VIRT_SFR          | 0x0824 | vsfr_id (u32)                    | retcode(u32) value(u32) - see §5   |
| WR_VIRT_SFR          | 0x0825 | vsfr_id (u32) + value (u32)      | retcode(u32) - no further body    |
| RD_VIRT_SFR_BATCH    | 0x082A | count(u32) + ids(u32...)         | valid-flags + values               |
| WR_VIRT_SFR_BATCH    | 0x082B | count + ids + values             | valid-flags(u32)                   |
| RD_VIRT_STRING_BATCH | 0x082C | count(u32) + ids(u32...)         | -                                  |
| WR_VIRT_STRING_BATCH | 0x082D | count + ids + data               | -                                  |
| SET_BT_EXCHANGE_ID   | 0x0903 | -                                | -                                  |
| RD_VIRT_STRING       | 0x0826 | vs_id (u32)                      | see §6                             |
| WR_VIRT_STRING       | 0x0827 | vs_id + data                     | retcode(u32) - no further body    |
| SET_LOCAL_TIME       | 0x0A04 | day month year-2000 0 sec min hr | header only - no retcode, no data  |

> **Init sequence (observed):** on connect, the reference implementation sends
> `SET_EXCHANGE` (`01 FF 12 FF`), then `SET_TIME` with the host's current local
> time, then `WR_VIRT_SFR` `DEVICE_TIME=0x0504` with value `0`, then reads
> `GET_VERSION` to check the firmware is >= 4.8, and finally reads the
> `CONFIGURATION` virtual string to discover `SpecFormatVersion`. The order is
> not strictly required by the wire protocol, but it is the canonical bootstrap
> used by the library.

A few ids in the `COMMAND` enum have not been observed in any captured session
and are listed above only for completeness (`WR_VIRT_SFR_BATCH`, `RD_VIRT_STRING_BATCH`,
`WR_VIRT_STRING_BATCH`, `SET_BT_EXCHANGE_ID`); their layouts follow the patterns
of the observed batch/register commands. `FW_SIGNATURE` (0x0101) is logged by the
app under the name `RD_SIGNAT`; the two share the same command id and format.

### SET_EXCHANGE: interface type and connect status

`SET_EXCHANGE` negotiates the transport and reports the device's **active
physical interface** and whether it is **ready for a new client**. The response
body is:

```
TARGET_ID(u32)  TX(u16)  RX(u16)  IF_READY(u8)  IF_TYPE(u8)
```

- `IF_TYPE` - the physical interface the device is currently exchanging over:
  `1` = **USB**, `2` = **BLE**. A host that connects over USB sees `1`; the
  Android app over Bluetooth sees `2`.
- `IF_READY` - whether that interface is ready for this client: `1` = ready,
  `0` = **busy** (the device is already in operation with another application
  on a different interface, e.g. the Android app tries Bluetooth while a
  desktop app holds the USB interface). When busy, the response still reports
  the *active* interface's `IF_TYPE`.

The negotiated buffer sizes also differ by interface: observed `TX=8224
RX=4096` over USB vs `TX=4128 RX=4096` over BLE.

Observed values across the captured sessions:

| Connection                          | IF_TYPE | IF_READY | TX size |
|-------------------------------------|---------|----------|---------|
| Desktop app over USB                | 1 (USB) | 1 (ready) | 8224  |
| Android app over BLE, FW<4.15       | 2 (BLE) | 1 (ready) | 4128  |
| Android app over BLE, FW 4.15       | 2 (BLE) | 1 (ready) | 5152  |
| Android app over BLE, USB occupied  | 1 (USB) | 0 (busy)  | 4128  |

### Firmware update

A firmware-update session renegotiates the exchange after writing the image.
The three commands are used together (observed on BLE sessions):

- **`FW_IMAGE_GET_INFO` (0x0012)** - request is header only; response is
  `image_size(u32) buffer_size(u32) signature(u32) crc32(u32)`.
  `buffer_size` is the chunk size used by `FW_IMAGE_WRITE` (observed 4096).
- **`FW_IMAGE_WRITE` (0x0013)** - request is `signature(u32) offset(u32)
  count(u32) data(count bytes)`; writes `count` bytes at `offset` for the image
  identified by `signature`, in `buffer_size` blocks (observed 4096). Response
  is `retcode(u32)` only (0 = OK).
- **`FW_IMAGE_UPDATE` (0x0014)** - request is `exchange_target(u32) zero(u32)
  signature(u32)`; the `exchange_target` field is the same `01 FF 12 FF` magic
  used by `SET_EXCHANGE`. Response is `retcode(u32) value(u32)`; the meaning of
  `value` is unknown (observed 8197/8199/8413).

After `FW_IMAGE_UPDATE` completes, the host re-issues `SET_EXCHANGE`.


### RD_FLASH_AREA and the firmware descriptor

`RD_FLASH_AREA` reads a flash region; the payload is an area index (`u32`,
observed value `1`). The response body is:

```
status(u32)  seed(u32)  enc_size(u32)  encrypted_area(enc_size bytes)
```

- `status` is the flash status code (`0` = `FLASH_OK`).
- `seed` is the plaintext seed for the PRNG keystream that decrypts the rest.
- `enc_size` and the area bytes are **encrypted** with a simple self-seeded LCG
  keystream - an obfuscation, not a real cipher:

```
seed = (seed * 22695477 + 1) mod 2^32
decrypted_byte = enc_byte ^ ((seed >> 16) & 0xFF)
```

The stream is threaded across the 4-byte size header *and* the area bytes (the
running seed continues between the two), then the whole thing decrypts to the
firmware descriptor:

* PublicSignat(u32)
* StructLen(u32)
* BootSignat(u32)
* ProdSerNumber(32 bytes)
* TrgFileName(32 bytes)
* ProdName(64 bytes)
* CalibBP0(u32)
* CalibBP290(u32)
* VID(u16)
* PID(u16)
* MnfctName(32 bytes)
* Target_ID(u32)
* TargetStartTimeOut(u32)
```

All integer fields are little-endian. The string fields are fixed-size,
NUL-padded ASCII. Real RC-110 values (verified against a live capture):

```
PublicSignat=0x19601217 StructLen=448 BootSignat=0x591E437D
ProdSerNumber="RC-110-001068" TrgFileName="rc-110.bin" ProdName="RadiaCode-110"
CalibBP0=1476 CalibBP290=3095 VID=0x0483 PID=0xF123 MnfctName="RadiaCode"
Target_ID=0xDADA0105 TargetStartTimeOut=3000
```

`BootSignat` is a **bit-packed date/time**, not a plain timestamp. The high
16 bits pack `((year-1980)<<9 | month<<5 | day)` and the low 16 bits pack
`(hour<<11 | minute<<5 | seconds/2)`. The app renders it as a UTC date -
e.g. `0x591E437D` = `Aug 30, 2024 08:27:58`.

### GET_STATUS flags

`GET_STATUS` returns a single `u32` status word. The named bits below are the
ones that plausibly apply to a radiation detector; the Android app's flag
table also carries generic platform bits (SpO2, valves, pumps, pressure) from
other AlmaCode devices that are never set on a detector and are omitted here.

| Bit  | Name                     |
|------|--------------------------|
| 0    | BOOT_BIT                 |
| 1    | INIT_BIT                 |
| 2    | RUN_BIT                  |
| 3    | DEBUG_BIT                |
| 4    | LCD_BIT                  |
| 5    | SDC_BIT                  |
| 6    | EMU_BIT                  |
| 7    | USB_TIMEOUT              |
| 8    | IR1_LED_BIT              |
| 9    | IR2_LED_BIT              |
| 10   | FRAME_BIT                |
| 11   | ACC_BIT                  |
| 16   | Ch1 Enabled              |
| 17   | Ch1 Not Connected        |
| 18   | Ch1 High Freq            |
| 19   | Ch1 Read Overflow        |
| 24   | Ch2 Enabled              |
| 25   | Ch2 Not Connected        |
| 26   | Ch2 High Freq            |
| 27   | Ch2 Read Overflow        |

### Data-buffer record `flags` and `real_time_flags`

The u16 `flags` field of every record is a *different* bit table from the
GET_STATUS word. Per the Android app's record decoder (`cs1`), it packs:

- **Power source** (bits 13-14): `0x0000`=Accum, `0x2000`=USB,
  `0x4000`=USB, Chrg, `0x6000`=Accum, Low. Bit 14 alone (`0x4000`) indicates
  USB with the battery charging - a desktop USB session shows `0x4000` on
  every record while the battery charges.
- **Temperature state** (bits 6-7): `0x0000`=Not defined, `0x0080`=Too low,
  `0x00C0`=Too high (`0x0040` is an undefined combo, not displayed).
- **Flags**: bit 12 = "Save to database", bit 15 = "Old data".
- **Instantaneous alarm state**: bits 0-1 carry the current dose-rate alarm
  level (`0x0001`=Alarm 1, `0x0002`=Alarm 2) and bits 8-9 the count-rate
  alarm level (`0x0100`=Alarm 1, `0x0200`=Alarm 2). These are set on
  `DoseRateDB` and `Event` records while a dose/count alarm is active -
  verified against a USB-capture alarm sequence:

  | Flags  | Decoded alarms |
  |--------|----------------|
  | 0x5041 | Dose rate: Alarm 1 |
  | 0x5042 | Dose rate: Alarm 2 |
  | 0x5142 | Dose rate: Alarm 2, Count rate: Alarm 1 |
  | 0x5242 | Dose rate: Alarm 2, Count rate: Alarm 2 |

The `real_time_flags` u8 (only on RealTimeData) carries alarm-sound and
background-change state: bit 0 = dose-rate alarm sound, bit 1 = dose alarm
sound, bit 2 = count-rate alarm sound, bit 3 = alarm active, bit 5 = reliable
background change, bit 6 = background change start.

## 5. String / scalar reads

- **GET_VERSION** response: `boot_minor(u16) boot_major(u16) <string>
  target_minor(u16) target_major(u16) <string>`. A `<string>` is a length byte
  followed by that many ASCII bytes.
- **GET_SERIAL**: `len(u32)` then `len/4` × `u32` hardware-serial groups,
  formatted as `%08X-%08X-%08X` (hex, uppercase).
- **FW_SIGNATURE**: `signature(u32) <string:filename> <string:idstring>`.
- **RD_VIRT_SFR** response: `retcode(u32) value(u32)` - the `retcode` comes
  first (1 on success), followed by the raw `u32` register value.

## 6. Virtual strings (RD_VIRT_STRING, 0x0826)

Request payload is the VS id (`u32`). Response:

```
header  retcode(u32)  flen(u32)  data(flen bytes)
```

`flen` is the data length in bytes. Some firmware versions append a stray `0x00`
after the data; implementations should tolerate it.

Common VS ids (see `VS` enum): `CONFIGURATION=2`, `FW_DESCRIPTOR=3`,
`SERIAL_NUMBER=8`, `TEXT_MESSAGE=0xF`, `MEM_SNAPSHOT=0xE0`, `SFR_FILE=0x101`,
`DATA_BUF=0x100`, `SPECTRUM=0x200`, `ENERGY_CALIB=0x202`, `SPEC_ACCUM=0x205`,
`SPEC_DIFF=0x206`, `SPEC_RESET=0x207`.

## 7. Virtual string file registers (VSFR)

A VSFR is addressed by a `u32` id (`VSFR` enum). Single read/write use
`RD_VIRT_SFR`/`WR_VIRT_SFR` with `vsfr_id + value` (u32 each).

The **batch read** (`RD_VIRT_SFR_BATCH`) payload is `count(u32)` then `count`
ids (`u32` each). The response is `valid-flags(u32)` (bit *i* set if id *i*
responded) then `count` raw `u32` values in request order.

Each value must be re-interpreted using a per-register format - **the
significant byte(s) are in the low end of the `u32`**, e.g.:

| VSFR                 | Id      | Format      | Example value |
|----------------------|---------|-------------|---------------|
| SOUND_CTRL           | 0x0520  | `u16` (low) | 8191          |
| VIBRO_CTRL           | 0x0530  | `u16` (low) | 7423          |
| DEVICE_CTRL          | 0x0500  | `u8` (low)  | 43            |
| DS_UNITS             | 0x8004  | `bool`      | 1             |
| CR_UNITS             | 0x8013  | `bool`      | 0             |
| TEMP_UNITS           | 0x8016  | `bool`      | 0             |
| CR_LEV1_cp10s        | 0x8008  | `u32`       | 200           |
| CR_LEV2_cp10s        | 0x8009  | `u32`       | 600           |
| DR_LEV1_uR_h         | 0x8000  | `u32`       | 40            |
| DR_LEV2_uR_h         | 0x8001  | `u32`       | 120           |
| DS_LEV1_uR / LEV2   | 0x8014/15 | `u32`    | 999999999     |

Count-rate limits are stored in counts-per-10-seconds; divide by 10 for cps.
Dose limits are in `µR/h`. Dose/count unit flags gate the Sv/R and cps/cpm
display conversions.

## 8. Data buffer (VS_DATA_BUF, 0x100)

The buffer is a sequence of **records**. Each record header is 7 bytes:

```
seq(u8)  eid(u8)  gid(u8)  ts_offset(i32 LE)
```

`ts_offset` is in **0.01-second (10 ms) units**. Absolute record time is:

```
record_time = base_time + ts_offset * 10 ms
```

`base_time` is the host wall-clock time at the moment the buffer is read (the
device timestamps are relative to "now"). Refresh it on **every** read - a
fixed connect-time base drifts on long sessions, and a +128 s offset
(unnecessarily introduced during early reverse-engineering) pushes timestamps
~128 s too far into the future.

**`eid` is a single/multi flag:** `eid=0` = one record; `eid=1` = a multi-sample
block (`samples_num(u16) smpl_time(u32)` then `samples_num` records).
Implementations should **expand multi-sample blocks into individual records**.
`smpl_time` is the interval between consecutive samples, in the **same 10 ms
units as `ts_offset`** (not milliseconds despite some tooling's naming). The
samples run oldest→newest starting at the block's `ts_offset`, so sample `i` is
timestamped `ts_offset + i*smpl_time*10 ms`. (Verified against DoseRateDB blocks
that tile the single-sample logging grid exactly.)

**`gid` selects the record type** (same for single and multi):

| gid | Type        | Per-record payload                          |
|-----|-------------|---------------------------------------------|
| 0   | RealTimeData| `cr(f) dr(f) cr_err(u16) dr_err(u16) flags(u16) rt_flags(u8)` (+1 byte on FW 4.15) |
| 1   | RawData     | `count_rate(f) dose_rate(f)`                |
| 2   | DoseRateDB  | `count(u32) cr(f) dr(f) err(u16) flags(u16)`|
| 3   | RareData    | `duration(u32) dose(f) temp(u16) charge(u16) flags(u16)` |
| 4   | DoseCounter | `dose_counter(u32) flags(u16)`              |
| 7   | Event       | `event(u8) mask(u8) flags(u16)` + optional alarm rate (below) |

**RealTimeData size change (FW 4.15):** on firmware <= 4.14 the gid 0 body is 15
bytes as listed. Firmware 4.15 appends **one further byte after `rt_flags`**
(16 bytes total); the first 15 bytes keep the identical layout, so only the
record length changes. The added byte has been observed as `0x00` on every RC-102
/ RC-103G / RC-110 capture to date and its meaning is undetermined; the decoder
consumes it to keep subsequent records aligned. Because the buffer carries no
framing, the body size is auto-detected per buffer (the two sizes are mutually
exclusive: a buffer containing RealTimeData records parses end-to-end under
exactly one of them).

The buffer has no framing/lengths, so a corrupt record can only be recovered by
heuristics. The reference decoder **skips a malformed record and re-syncs** to
the next plausible record (a candidate is accepted only if it is followed by
another plausible record), so a single glitch does not discard the rest of the
buffer. Multi-sample blocks are pre-validated against the remaining buffer
before decoding, so a corrupt `samples_num` doesn't greedily consume the tail.

Units: `count_rate` is cps; `dose_rate` raw value × 1e7 ≈ nSv/h; `dose_rate_err`
and `count_rate_err` are stored in tenths of percent (divide by 10);
`temperature`/`charge_level` are `(raw - 2000)/100` / `raw/100`.

**Event variable length:** Alarm / off-scale events (event id 9–14, 20–22) carry
an extra `rate(f) err(u16)` after the base `event(u8) mask(u8) flags(u16)`.
Count-rate events populate `count_rate`; dose-rate events populate `dose_rate`.

## 9. Spectrum formats (VS_SPECTRUM family)

The device config `SpecFormatVersion` selects the count encoding:
- **version 0**: raw `u32` per channel (1024 channels).
- **version 1**: run-length compressed (see §10). **Confirmed on every device
  in the captured Android-app logs: SPEC_ACCUM, SPEC_RESET, SPECTRUM and
  SPEC_DIFF all use version 1.**

> Only versions 0 and 1 are supported. A device reporting a higher
> `SpecFormatVersion` is treated as version 1, since no other encoding has
> been observed in any captured session.

Headers:

| VS         | Header                                       |
|------------|----------------------------------------------|
| SPECTRUM (0x200)  | `ts(u32) a0(f) a1(f) a2(f)`            |
| SPEC_ACCUM (0x205)| `ts(u32) a0(f) a1(f) a2(f)`            |
| SPEC_RESET (0x207)| `ts(u32)` only - **no calibration**     |
| SPEC_DIFF (0x206) | `duration_sec(u32) 0(u32)` - see §11    |

`ts` / `duration_sec` are **seconds** (verified against wall-clock). `a0,a1,a2`
are the energy-calibration coefficients. The `ts` values are **cumulative
live-time since the last reset** - not elapsed since boot. With multi-month
accumulators the values reach tens of millions of seconds, which is expected.
Channel 1023 is the **overflow / upper bin**: it accumulates above the
detector's energy range and visibly exceeds its neighbours on both SPEC_* and
SPEC_DIFF reads.

## 10. Version-1 count compression (run-length)

Each 16-bit word: `cnt` = top 12 bits, `vlen` = low 4 bits. Then `cnt` samples,
each encoded per `vlen`:

| vlen | bytes | value                        |
|------|-------|------------------------------|
| 0    | 0     | 0                            |
| 1    | 1     | unsigned byte                |
| 2    | 1     | last + signed i8             |
| 3    | 2     | last + signed i16            |
| 4    | 3     | last + 24-bit signed         |
| 5    | 4     | last + signed i32            |

`last` is the previous emitted value (0 initially). Values above `vlen=5` are
not yet supported by the reference decoder.

## 11. SPEC_DIFF (0x206) - spectrogram diff

`SPEC_DIFF` is the per-channel **count change** since the previous spectrum
read, used by the app's spectrogram. Header is `(duration_sec, 0)` where
`duration_sec` is the **cumulative** spectrogram live-time since it started
(the difference between successive reads is the ~1-minute sampling interval;
verified against a 360-sample, ~1-min-interval plane-spectrogram capture).

The body is a v1-compressed **full 1024-channel** count diff (see §10).
**Confirmed on every captured Android-app session.** The cumulative diff profile
matches the corresponding SPEC_RESET / SPEC_ACCUM spectrum shape (same low-energy
peak), and the overflow channel 1023 accumulates visibly on both.

## 12. Unit conversions

- `dose_rate` (all records): raw float × 1e7 → nSv/h.
- `count_rate_err` / `dose_rate_err`: stored ×10 (divide by 10 for %).
- Spectrum counts: per channel, arbitrary units.
- Energy per channel: `E = a0 + a1·ch + a2·ch²`.

## 13. Time synchronization

Two mechanisms keep the device clock aligned with the host Android clock:

- **`SET_LOCAL_TIME` (0x0A04)** - sent **once at connect**. The payload is the
  host's local time packed as `day month (year-2000) 0 sec min hour 0` (8 bytes,
  e.g. `0C 0A 14 00 1E 07 0F 00`). This sets the device's wall-clock RTC.
- **`WR_VIRT_SFR DEVICE_TIME (0x0504) = 0`** - sent **periodically, every ~60 s,
  for the whole session** (confirmed across the captured Android-app logs). The
  register is never read back; it is a write-only reassertion that keeps the
  device's internal timestamp base pinned to host "now" so the data-buffer
  `ts_offset` values stay small and don't drift.

The data-buffer records are timestamped relative to host "now" at each read
(`record_time = base_time + ts_offset·10 ms`, §8). Without the periodic
`DEVICE_TIME=0` reassertion the device clock would drift and the newest offsets
would grow; with it, the **newest** records land within ±~10 s. The buffer can
also hold older history (offsets minutes to hours in the past), which is
expected and unrelated to drift.
