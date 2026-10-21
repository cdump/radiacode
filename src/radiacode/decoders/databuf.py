from __future__ import annotations

import datetime
import struct

from radiacode.bytes_buffer import BytesBuffer
from radiacode.types import DoseCounter, DoseRateDB, Event, EventId, RareData, RawData, RealTimeData, RecordFlags, RealTimeFlags

# Alarm / off-scale events carry an extra rate + error field after the usual
# event header (ev, mask, flags).  Count-rate events carry a count rate, the
# others carry a dose rate.
_RATE_EVENTS = {
    EventId.DOSE_RATE_ALARM1: 'dose',
    EventId.DOSE_RATE_ALARM2: 'dose',
    EventId.DOSE_RATE_OFFSCALE: 'dose',
    EventId.DOSE_ALARM1: 'dose',
    EventId.DOSE_ALARM2: 'dose',
    EventId.DOSE_OFFSCALE: 'dose',
    EventId.COUNT_RATE_ALARM1: 'count',
    EventId.COUNT_RATE_ALARM2: 'count',
    EventId.COUNT_RATE_OFFSCALE: 'count',
}

# Event ids that carry the extra rate + error payload after the base header.
_RATE_EVENT_IDS = {int(e) for e in _RATE_EVENTS}

# Per-gid body size for single-sample groups (after the 7-byte record header).
_SINGLE_SIZE = {0: 15, 1: 8, 2: 16, 3: 14, 4: 6}
# Per-gid body size for multi-sample groups (after header + samples_num/smpl_time).
_MULTI_SIZE = {1: 8, 2: 16, 3: 14, 4: 6}


def decode_VS_DATA_BUF(
    br: BytesBuffer, base_time: datetime.datetime, ignore_errors: bool = True
) -> list[RealTimeData | DoseRateDB | DoseCounter | RareData | RawData | Event]:
    """Decode a data buffer into a flat list of records.

    Multi-sample groups (eid=1) are expanded so each sample becomes its own
    single record, letting consumers process records one at a time.

    Timestamps: `ts_offset` is in 0.01-second units; `base_time` should be the
    host wall-clock time at the moment the buffer was read.

    Malformed / truncated records are skipped and decoding resumes at the next
    plausible record boundary, so a single glitch does not discard the rest of
    the buffer. With `ignore_errors=False` the first malformed record raises
    instead.
    """
    ret: list[RealTimeData | DoseRateDB | DoseCounter | RareData | RawData | Event] = []
    next_seq = None
    while br.size() >= 7:
        seq, eid, gid, ts_offset = br.unpack('<BBBi')
        dt = base_time + datetime.timedelta(milliseconds=ts_offset * 10)
        if next_seq is not None and next_seq != seq:
            # A discontinuity (a record was dropped by the device) is not fatal:
            # the records present are still valid, so keep decoding.
            if not ignore_errors:
                print(f'seq jump while processing {eid=} {gid=}, expect:{next_seq}, got:{seq} {br.size()=}')
        next_seq = (seq + 1) % 256

        try:
            # Validate multi-sample blocks before decoding them: a corrupt
            # samples_num would otherwise greedily consume the rest of the
            # buffer as samples. If the block body doesn't fit, treat it as a
            # malformed record so we skip past it instead.
            if eid == 1 and gid in _MULTI_SIZE:
                if br.size() < 6:
                    raise ValueError('truncated multi-block header')
                samples_num = struct.unpack_from('<H', br.data(), 0)[0]
                if br.size() < 6 + _MULTI_SIZE[gid] * samples_num:
                    raise ValueError(f'multi-block body does not fit ({samples_num=})')
            ret.extend(_decode_entry(br, eid, gid, dt))
        except ValueError:
            # truncated / malformed record: skip it and re-sync to the next record
            if not ignore_errors:
                print(f'BytesBuffer error while decoding {eid=}/{gid=} [{br.data().hex(" ")}]')
                raise
            if not _resync(br):
                break
            next_seq = None

    return ret


def _record_size(data: bytes, off: int) -> int | None:
    """Return the body size (after the 7-byte header) of the record at `off`,
    or None if it doesn't look like a plausible record."""
    n = len(data)
    if off + 7 > n:
        return None
    eid = data[off + 1]
    gid = data[off + 2]
    if eid == 0:
        if gid in _SINGLE_SIZE:
            size = _SINGLE_SIZE[gid]
        elif gid == 7:
            event = data[off + 7]
            size = 4 + (6 if event in _RATE_EVENT_IDS else 0)
        else:
            return None
    elif eid == 1:
        if gid in _MULTI_SIZE:
            if off + 13 > n:
                return None
            samples_num = struct.unpack_from('<H', data, off + 7)[0]
            size = 6 + _MULTI_SIZE[gid] * samples_num
        else:
            return None
    else:
        return None
    if off + 7 + size > n:
        return None
    return size


def _resync(br: BytesBuffer, max_scan: int = 512) -> bool:
    """After a malformed record, scan forward for the next plausible record
    header and reposition the buffer there. Returns True if a re-sync point was
    found, leaving the buffer positioned at that record's header.

    A candidate is only accepted if the record parses *and* is followed by
    another plausible record, which rejects most false positives in garbage.
    """
    start = br._pos
    data = br._data
    # scan from start+1 so we always make progress and never re-pick the malformed record
    limit = min(start + max_scan, len(data) - 7)
    for off in range(start + 1, limit):
        size = _record_size(data, off)
        if size is None:
            continue
        end = off + 7 + size
        if _record_size(data, end) is not None:
            br._pos = off
            return True
    return False


def _decode_entry(
    br: BytesBuffer, eid: int, gid: int, dt: datetime.datetime
) -> list[RealTimeData | DoseRateDB | DoseCounter | RareData | RawData | Event]:
    """Decode one record group; multi-sample groups are expanded per sample."""
    ret: list[RealTimeData | DoseRateDB | DoseCounter | RareData | RawData | Event] = []

    if eid == 0:  # single-sample groups
        if gid == 0:  # GRP_RealTimeData
            count_rate, dose_rate, count_rate_err, dose_rate_err, flags, rt_flags = br.unpack('<ffHHHB')
            ret.append(
                RealTimeData(
                    dt=dt,
                    count_rate=count_rate,
                    count_rate_err=count_rate_err / 10,
                    dose_rate=dose_rate,
                    dose_rate_err=dose_rate_err / 10,
                    flags=RecordFlags(flags),
                    real_time_flags=RealTimeFlags(rt_flags),
                )
            )
        elif gid == 1:  # GRP_RawData
            count_rate, dose_rate = br.unpack('<ff')
            ret.append(RawData(dt=dt, count_rate=count_rate, dose_rate=dose_rate))
        elif gid == 2:  # GRP_DoseRateDB
            count, count_rate, dose_rate, dose_rate_err, flags = br.unpack('<IffHH')
            ret.append(
                DoseRateDB(
                    dt=dt,
                    count=count,
                    count_rate=count_rate,
                    dose_rate=dose_rate,
                    dose_rate_err=dose_rate_err / 10,
                    flags=RecordFlags(flags),
                )
            )
        elif gid == 3:  # GRP_RareData
            duration, dose, temperature, charge_level, flags = br.unpack('<IfHHH')
            ret.append(
                RareData(
                    dt=dt,
                    duration=duration,
                    dose=dose,
                    temperature=(temperature - 2000) / 100,
                    charge_level=charge_level / 100,
                    flags=RecordFlags(flags),
                )
            )
        elif gid == 4:  # GRP_DoseCounter
            dose_counter, flags = br.unpack('<IH')
            ret.append(DoseCounter(dt=dt, dose_counter=dose_counter, flags=RecordFlags(flags)))
        elif gid == 7:  # GRP_Event
            event, mask, flags = br.unpack('<BBH')
            kwargs: dict = {'event': EventId(event), 'event_param1': mask, 'flags': RecordFlags(flags)}
            rate_type = _RATE_EVENTS.get(EventId(event))
            if rate_type is not None:
                rate, rate_err = br.unpack('<fH')
                if rate_type == 'count':
                    kwargs['count_rate'] = rate
                    kwargs['count_rate_err'] = rate_err / 10
                else:
                    kwargs['dose_rate'] = rate
                    kwargs['dose_rate_err'] = rate_err / 10
            ret.append(Event(dt=dt, **kwargs))
        else:
            raise ValueError(f'Unknown eid:{eid} gid:{gid}')

    else:  # eid == 1: multi-sample groups, expanded into per-sample records
        samples_num, smpl_time_ms = br.unpack('<HI')
        if gid == 1:  # GRP_RawData
            for _ in range(samples_num):
                count_rate, dose_rate = br.unpack('<ff')
                ret.append(RawData(dt=dt, count_rate=count_rate, dose_rate=dose_rate))
        elif gid == 2:  # GRP_DoseRateDB
            for _ in range(samples_num):
                count, count_rate, dose_rate, dose_rate_err, flags = br.unpack('<IffHH')
                ret.append(
                    DoseRateDB(
                        dt=dt,
                        count=count,
                        count_rate=count_rate,
                        dose_rate=dose_rate,
                        dose_rate_err=dose_rate_err / 10,
                        flags=RecordFlags(flags),
                    )
                )
        elif gid == 3:  # GRP_RareData
            for _ in range(samples_num):
                duration, dose, temperature, charge_level, flags = br.unpack('<IfHHH')
                ret.append(
                    RareData(
                        dt=dt,
                        duration=duration,
                        dose=dose,
                        temperature=(temperature - 2000) / 100,
                        charge_level=charge_level / 100,
                        flags=RecordFlags(flags),
                    )
                )
        elif gid == 4:  # GRP_DoseCounter
            for _ in range(samples_num):
                dose_counter, flags = br.unpack('<IH')
                ret.append(DoseCounter(dt=dt, dose_counter=dose_counter, flags=RecordFlags(flags)))
        else:
            raise ValueError(f'Unknown eid:{eid} gid:{gid}')

    return ret
