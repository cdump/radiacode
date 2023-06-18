from typing import List
import datetime

from radiacode.bytes_buffer import BytesBuffer
from radiacode.types import Spectrum


def decode_counts_v0(br: BytesBuffer) -> List[int]:
    ret = []
    while br.size() > 0:
        ret.append(br.unpack('<I')[0])
    return ret


def decode_counts_v1(br: BytesBuffer) -> List[int]:
    ret = []
    last = 0
    while br.size() > 0:
        u16 = br.unpack('<H')[0]
        cnt = (u16 >> 4) & 0x0FFF
        vlen = u16 & 0x0F
        for _ in range(cnt):
            if vlen == 0:
                v = 0
            elif vlen == 1:
                v = br.unpack('<B')[0]
            elif vlen == 2:
                v = last + br.unpack('<b')[0]
            elif vlen == 3:
                v = last + br.unpack('<h')[0]
            elif vlen == 4:
                a, b, c = br.unpack('<BBb')
                v = last + ((c << 16) | (b << 8) | a)
            elif vlen == 5:
                v = last + br.unpack('<i')[0]
            else:
                raise Exception(f'unspported vlen={vlen} in decode_RC_VS_SPECTRUM version=1', vlen)

            last = v
            ret.append(v)
    return ret


def decode_RC_VS_SPECTRUM(br: BytesBuffer, format_version: int) -> Spectrum:
    ts, a0, a1, a2 = br.unpack('<Ifff')

    assert format_version in {0, 1}, f'unspported format_version={format_version}'
    counts = decode_counts_v0(br) if format_version == 0 else decode_counts_v1(br)

    return Spectrum(
        duration=datetime.timedelta(seconds=ts),
        a0=a0,
        a1=a1,
        a2=a2,
        counts=counts,
    )
