import datetime
from typing import List, Union

from radiacode.bytes_buffer import BytesBuffer
from radiacode.types import CountRate, DoseRate, DoseRateDB, Event, RareData


def decode_VS_DATA_BUF(
    br: BytesBuffer, base_time: datetime.datetime
) -> List[Union[CountRate, DoseRate, DoseRateDB, RareData, Event]]:
    ret: List[Union[CountRate, DoseRate, DoseRateDB, RareData, Event]] = []
    next_seq = None
    while br.size() > 0:
        seq, eid, gid, ts_offset = br.unpack('<BBBi')
        dt = base_time + datetime.timedelta(milliseconds=ts_offset)
        if next_seq is not None and next_seq != seq:
            raise Exception(f'seq jump, expect:{next_seq}, got:{seq}')

        next_seq = (seq + 1) % 256
        if eid == 0 and gid == 0:  # GRP_CountRate
            count, count_rate, flags = br.unpack('<HfH')
            ret.append(
                CountRate(
                    dt=dt,
                    count=count,
                    count_rate=count_rate,
                    flags=flags,
                )
            )
        elif eid == 0 and gid == 1:  # GRP_DoseRate
            dose_rate, dose_rate_err, flags = br.unpack('<fHH')
            ret.append(
                DoseRate(
                    dt=dt,
                    dose_rate=dose_rate,
                    dose_rate_err=dose_rate_err * 0.1,
                    flags=flags,
                )
            )
        elif eid == 0 and gid == 2:  # GRP_DoseRateDB
            count, count_rate, dose_rate, dose_rate_err, flags = br.unpack('<HffHH')
            ret.append(
                DoseRateDB(
                    dt=dt,
                    count=count,
                    count_rate=count_rate,
                    dose_rate=dose_rate,
                    dose_rate_err=dose_rate_err * 0.1,
                    flags=flags,
                )
            )
        elif eid == 0 and gid == 3:  # GRP_RareData
            duration, dose, temperature, charge_level, flags = br.unpack('<IfHHH')
            ret.append(
                RareData(
                    dt=dt,
                    duration=duration,
                    dose=dose,
                    temperature=temperature * 0.01 - 20,
                    charge_level=charge_level * 0.01,
                    flags=flags,
                )
            )
        elif eid == 0 and gid == 7:  # GRP_Event
            event, event_param1, flags = br.unpack('<BBH')
            ret.append(
                Event(
                    dt=dt,
                    event=event,
                    event_param1=event_param1,
                    flags=flags,
                )
            )
        elif eid == 1 and gid == 2:  # ???
            br.unpack('34x')  # skip
        elif eid == 1 and gid == 3:  # ???
            br.unpack('34x')  # skip
        else:
            raise Exception(f'Uknown eid:{eid} gid:{gid}')

    return ret
