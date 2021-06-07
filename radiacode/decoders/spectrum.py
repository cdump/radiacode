import datetime

from radiacode.bytes_buffer import BytesBuffer
from radiacode.types import Spectrum


def decode_RC_VS_SPECTRUM(br: BytesBuffer) -> Spectrum:
    ts, a0, a1, a2 = br.unpack('<Ifff')
    counts = []
    while br.size() > 0:
        counts.append(br.unpack('<I')[0])
    return Spectrum(
        duration=datetime.timedelta(seconds=ts),
        a0=a0,
        a1=a1,
        a2=a2,
        counts=counts,
    )
