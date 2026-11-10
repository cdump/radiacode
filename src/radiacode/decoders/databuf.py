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

# RealTimeData (gid 0) body size. Firmware <= 4.14 uses 15 bytes
# (`cr(f) dr(f) cr_err(u16) dr_err(u16) flags(u16) rt_flags(u8)`); firmware 4.15
# appends one further byte (observed always 0x00, meaning undetermined), making
# the body 16 bytes. The extra byte sits after `rt_flags`, so the first 15 bytes
# keep the same layout in both versions. The size is auto-detected per buffer.
_RT_LEGACY_SIZE = 15
_RT_NEW_SIZE = 16

# Per-gid body size for single-sample groups (after the 7-byte record header).
# gid 0 (RealTimeData) is overridden by the detected `realtime_size`.
_SINGLE_SIZE = {0: _RT_LEGACY_SIZE, 1: 8, 2: 16, 3: 14, 4: 6}
# Per-gid body size for multi-sample groups (after header + samples_num/smpl_time).
_MULTI_SIZE = {1: 8, 2: 16, 3: 14, 4: 6}


def _single_size(gid: int, realtime_size: int) -> int:
    return realtime_size if gid == 0 else _SINGLE_SIZE[gid]


def _probe(data: bytes, realtime_size: int) -> tuple[bool, int]:
    """Strictly walk `data` assuming a RealTimeData body of `realtime_size`.

    Returns `(consumed_exactly, n_records)`: whether the walk landed exactly on
    the end of the buffer (all records well-formed), and how many records were
    decoded before the first malformed/truncated one.
    """
    off = 0
    n = len(data)
    nrec = 0
    while True:
        size = _record_size(data, off, realtime_size)
        if size is None:
            return False, nrec
        off += 7 + size
        nrec += 1
        if off >= n:
            return off == n, nrec


def _detect_realtime_size(data: bytes) -> int:
    """Pick the RealTimeData body size (15 or 16) that best explains `data`.

    A buffer that contains RealTimeData records parses cleanly end-to-end under
    exactly one of the two sizes; the other misaligns on the first such record.
    When no RealTimeData record is present both sizes parse identically and the
    legacy size is returned (the choice is then irrelevant). For a corrupt or
    truncated buffer (neither size reaches the end) the size that decoded more
    records wins.
    """
    if len(data) < 7:
        return _RT_LEGACY_SIZE
    r15 = _probe(data, _RT_LEGACY_SIZE)
    r16 = _probe(data, _RT_NEW_SIZE)
    if r15[0] and not r16[0]:
        return _RT_LEGACY_SIZE
    if r16[0] and not r15[0]:
        return _RT_NEW_SIZE
    if r15[0] and r16[0]:
        return _RT_LEGACY_SIZE
    return _RT_LEGACY_SIZE if r15[1] >= r16[1] else _RT_NEW_SIZE


def decode_VS_DATA_BUF(
    br: BytesBuffer,
    base_time: datetime.datetime,
    ignore_errors: bool = True,
    realtime_size: int | None = None,
) -> list[RealTimeData | DoseRateDB | DoseCounter | RareData | RawData | Event]:
    """Decode a data buffer into a flat list of records.

    Multi-sample groups (eid=1) are expanded so each sample becomes its own
    single record, letting consumers process records one at a time.

    Timestamps: `ts_offset` is in 0.01-second units; `base_time` should be the
    host wall-clock time at the moment the buffer was read.

    `realtime_size` is the RealTimeData (gid 0) body size: 15 for firmware
    <= 4.14, 16 for firmware 4.15 (which appends one extra byte). When omitted
    it is auto-detected from the buffer, so a single decoder handles both.

    Decoding stops at the first malformed / truncated record: the buffer has no
    framing, so there is nothing to re-align from. With `ignore_errors=False`
    the first malformed record raises instead.
    """
    ret: list[RealTimeData | DoseRateDB | DoseCounter | RareData | RawData | Event] = []
    if realtime_size is None:
        realtime_size = _detect_realtime_size(br.data())
    next_seq = None
    while br.size() >= 7:
        seq, eid, gid, ts_offset = br.unpack('<BBBi')
        dt = base_time + datetime.timedelta(milliseconds=ts_offset * 10)
        if next_seq is not None and next_seq != seq:
            if not ignore_errors:
                print(f'seq jump while processing {eid=} {gid=}, expect:{next_seq}, got:{seq} {br.size()=}')
            break

        next_seq = (seq + 1) % 256
        try:
            ret.extend(_decode_entry(br, eid, gid, dt, realtime_size))
        except ValueError:
            # truncated / malformed record: the rest of the buffer is unaligned, stop
            if not ignore_errors:
                print(f'BytesBuffer error while decoding {eid=}/{gid=} [{br.data().hex(" ")}]')
                raise
            break

    return ret


def _record_size(data: bytes, off: int, realtime_size: int = _RT_LEGACY_SIZE) -> int | None:
    """Return the body size (after the 7-byte header) of the record at `off`,
    or None if it doesn't look like a plausible record."""
    n = len(data)
    if off + 7 > n:
        return None
    eid = data[off + 1]
    gid = data[off + 2]
    if eid == 0:
        if gid in _SINGLE_SIZE:
            size = _single_size(gid, realtime_size)
        elif gid == 7:
            if off + 8 > n:  # event byte is at off+7; the 7-byte header alone is not enough
                return None
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


def _decode_entry(
    br: BytesBuffer, eid: int, gid: int, dt: datetime.datetime, realtime_size: int = _RT_LEGACY_SIZE
) -> list[RealTimeData | DoseRateDB | DoseCounter | RareData | RawData | Event]:
    """Decode one record group; multi-sample groups are expanded per sample."""
    ret: list[RealTimeData | DoseRateDB | DoseCounter | RareData | RawData | Event] = []

    if eid == 0:  # single-sample groups
        if gid == 0:  # GRP_RealTimeData
            count_rate, dose_rate, count_rate_err, dose_rate_err, flags, rt_flags = br.unpack('<ffHHHB')
            # firmware 4.15 appends one further byte after rt_flags; consume it
            # so the next record stays aligned (its meaning is undetermined).
            extra = realtime_size - 15
            if extra > 0:
                br.unpack(f'<{extra}s')
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
        samples_num, smpl_time = br.unpack('<HI')
        # `smpl_time` is the interval between consecutive samples, in the same
        # 10 ms units as ts_offset (verified: a DoseRateDB block tiles the
        # single-sample grid exactly at smpl_time*10 ms). The samples run oldest
        # to newest starting at the group timestamp `dt`, so sample i is at
        # dt + i*smpl_time*10ms rather than all sharing dt.
        step = datetime.timedelta(milliseconds=smpl_time * 10)
        if gid == 1:  # GRP_RawData
            for i in range(samples_num):
                count_rate, dose_rate = br.unpack('<ff')
                ret.append(RawData(dt=dt + i * step, count_rate=count_rate, dose_rate=dose_rate))
        elif gid == 2:  # GRP_DoseRateDB
            for i in range(samples_num):
                count, count_rate, dose_rate, dose_rate_err, flags = br.unpack('<IffHH')
                ret.append(
                    DoseRateDB(
                        dt=dt + i * step,
                        count=count,
                        count_rate=count_rate,
                        dose_rate=dose_rate,
                        dose_rate_err=dose_rate_err / 10,
                        flags=RecordFlags(flags),
                    )
                )
        elif gid == 3:  # GRP_RareData
            for i in range(samples_num):
                duration, dose, temperature, charge_level, flags = br.unpack('<IfHHH')
                ret.append(
                    RareData(
                        dt=dt + i * step,
                        duration=duration,
                        dose=dose,
                        temperature=(temperature - 2000) / 100,
                        charge_level=charge_level / 100,
                        flags=RecordFlags(flags),
                    )
                )
        elif gid == 4:  # GRP_DoseCounter
            for i in range(samples_num):
                dose_counter, flags = br.unpack('<IH')
                ret.append(DoseCounter(dt=dt + i * step, dose_counter=dose_counter, flags=RecordFlags(flags)))
        else:
            raise ValueError(f'Unknown eid:{eid} gid:{gid}')

    return ret
