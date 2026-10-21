import datetime

from radiacode.bytes_buffer import BytesBuffer
from radiacode.types import Spectrum


def decode_counts_v0(br: BytesBuffer) -> list[int]:
    ret = []
    while br.size() > 0:
        ret.append(br.unpack('<I')[0])
    return ret


def decode_counts_v1(br: BytesBuffer) -> list[int]:
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


def decode_RC_VS_SPEC_RESET(br: BytesBuffer, format_version: int) -> Spectrum:
    """Decode the live/current spectrum (VS 0x207).

    Unlike SPEC_ACCUM (0x205) / SPECTRUM (0x200), SPEC_RESET carries no
    calibration coefficients: the header is just `ts(I)` followed by the
    per-channel counts.
    """
    ts = br.unpack('<I')[0]

    assert format_version in {0, 1}, f'unspported format_version={format_version}'
    counts = decode_counts_v0(br) if format_version == 0 else decode_counts_v1(br)

    return Spectrum(
        duration=datetime.timedelta(seconds=ts),
        a0=0.0,
        a1=0.0,
        a2=0.0,
        counts=counts,
    )


def decode_RC_VS_SPEC_DIFF(br: BytesBuffer, format_version: int) -> tuple[int, list]:
    """Decode the spectrogram per-channel count diff (VS 0x206).

    The header is `(duration_seconds(I), 0(I))`. The body is the change in
    each channel since the previous spectrum read, v1-compressed (see §10 /
    `decode_counts_v1`).

    NOTE: Only the version-1 encoding has been observed in live captures;
    `format_version` is accepted for compatibility but the body is always
    decoded as version 1.
    """
    duration_seconds = br.unpack('<I')[0]
    br.unpack('<I')[0]

    if format_version not in {0, 1}:
        raise Exception(f'unspported format_version={format_version} for SPEC_DIFF')

    counts = decode_counts_v1(br)
    return duration_seconds, counts
