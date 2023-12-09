import datetime
from typing import List, Union

from radiacode.bytes_buffer import BytesBuffer
from radiacode.types import DoseRateDB, Event, RareData, RawData, RealTimeData


def decode_VS_DATA_BUF(
    br: BytesBuffer,
    base_time: datetime.datetime,
) -> List[Union[RealTimeData, DoseRateDB, RareData, RawData, Event]]:
    ret: List[Union[RealTimeData, DoseRateDB, RareData, RawData, Event]] = []
    next_seq = None
    while br.size() > 0:
        seq, eid, gid, ts_offset = br.unpack('<BBBi')
        dt = base_time + datetime.timedelta(milliseconds=ts_offset)
        if next_seq is not None and next_seq != seq:
            raise Exception(f'seq jump, expect:{next_seq}, got:{seq}')

        next_seq = (seq + 1) % 256
        if eid == 0 and gid == 0:  # GRP_RealTimeData
            count_rate, dose_rate, count_rate_err, dose_rate_err, flags, rt_flags = br.unpack('<ffHHHB')
            ret.append(
                RealTimeData(
                    dt=dt,
                    count_rate=count_rate,
                    count_rate_err=count_rate_err / 10,
                    dose_rate=dose_rate,
                    dose_rate_err=dose_rate_err / 10,
                    flags=flags,
                    real_time_flags=rt_flags,
                )
            )
        elif eid == 0 and gid == 1:  # GRP_RawData
            count_rate, dose_rate = br.unpack('<ff')
            ret.append(
                RawData(
                    dt=dt,
                    count_rate=count_rate,
                    dose_rate=dose_rate,
                )
            )
        elif eid == 0 and gid == 2:  # GRP_DoseRateDB
            count, count_rate, dose_rate, dose_rate_err, flags = br.unpack('<IffHH')
            ret.append(
                DoseRateDB(
                    dt=dt,
                    count=count,
                    count_rate=count_rate,
                    dose_rate=dose_rate,
                    dose_rate_err=dose_rate_err / 10,
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
                    temperature=(temperature - 2000) / 100,
                    charge_level=charge_level / 100,
                    flags=flags,
                )
            )
        elif eid == 0 and gid == 4:  # GRP_UserData:
            count, count_rate, dose_rate, dose_rate_err, flags = br.unpack('<IffHH')
            # TODO
        elif eid == 0 and gid == 5:  # GRP_SheduleData
            count, count_rate, dose_rate, dose_rate_err, flags = br.unpack('<IffHH')
            # TODO
        elif eid == 0 and gid == 6:  # GRP_AccelData
            acc_x, acc_y, acc_z = br.unpack('<HHH')
            # TODO
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
        elif eid == 0 and gid == 8:  # GRP_RawCountRate
            count_rate, flags = br.unpack('<fH')
        elif eid == 0 and gid == 9:  # GRP_RawDoseRate
            dose_rate, flags = br.unpack('<fH')
        elif eid == 1 and gid == 1:  # ???
            samples_num, smpl_time_ms = br.unpack('<HI')
            br.unpack(f'<{8*samples_num}x')  # skip
        elif eid == 1 and gid == 2:
            samples_num, smpl_time_ms = br.unpack('<HI')
            br.unpack(f'<{16*samples_num}x')  # skip
        elif eid == 1 and gid == 3:  # ???
            samples_num, smpl_time_ms = br.unpack('<HI')
            br.unpack(f'<{14*samples_num}x')  # skip
        else:
            raise Exception(f'Uknown eid:{eid} gid:{gid}')

    return ret
