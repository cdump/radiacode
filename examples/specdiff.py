#!/usr/bin/env python3
"""Analyze SPEC_DIFF (0x206) / SPEC_RESET (0x207) / SPEC_ACCUM (0x205) reads from a RadiaCode debug log.

The SPEC_ACCUM (0x205) and SPEC_RESET (0x207) virtual strings are decodable:
SPEC_ACCUM is `ts(I) + a0(f) + a1(f) + a2(f)` then v1-compressed counts,
SPEC_RESET is `ts(I)` then v1-compressed counts (no calibration).

SPEC_DIFF (0x206) is a sparse per-channel diff used by the spectrogram.  Its
format is the version-1 run-length encoding (`(duration_sec, 0)` header then
v1-compressed counts), confirmed against a 360-sample plane-spectrogram capture.
This script prints the raw data and the decoded diff so captures can be compared.
"""

import re
import struct
import sys


def extract_response(lines, idx):
    """Collect the raw response body for the read starting at line index `idx`."""
    chunks = []
    j = idx + 1
    while j < len(lines):
        m = re.search(r'Got (\d+) bytes: ((?:[0-9A-Fa-f]{2} )+[0-9A-Fa-f]{2})', lines[j])
        if m:
            n = int(m.group(1))
            hs = m.group(2).split()
            if len(hs) == n:
                chunks.append(bytes(int(h, 16) for h in hs))
            j += 1
            continue
        if 'RD_VIRT_STRING:' in lines[j]:
            break
        j += 1
    full = b''.join(chunks)
    if len(full) < 16:
        return None
    retcode, flen = struct.unpack('<II', full[8:16])
    return full[16 : 16 + flen]


def decode_v1_counts(data):
    """Decode v1-compressed channel counts from `data`."""
    counts = []
    last = 0
    pos = 0
    while pos < len(data):
        u16 = struct.unpack_from('<H', data, pos)[0]
        pos += 2
        cnt = (u16 >> 4) & 0x0FFF
        vlen = u16 & 0x0F
        for _ in range(cnt):
            if vlen == 0:
                v = 0
            elif vlen == 1:
                v = struct.unpack_from('<B', data, pos)[0]
                pos += 1
            elif vlen == 2:
                v = struct.unpack_from('<H', data, pos)[0]
                pos += 2
            elif vlen == 3:
                v = last + struct.unpack_from('<h', data, pos)[0]
                pos += 2
            elif vlen == 4:
                a, b, c = struct.unpack_from('<BBb', data, pos)
                pos += 3
                v = last + ((c << 16) | (b << 8) | a)
            elif vlen == 5:
                v = last + struct.unpack_from('<i', data, pos)[0]
                pos += 4
            else:
                raise ValueError(f'unsupported vlen={vlen}')
            last = v
            counts.append(v)
    return counts


def main():
    if len(sys.argv) < 2:
        print('usage: specdiff.py <radiacode_log.txt> [--diff] [--accum] [--reset]')
        return
    path = sys.argv[1]
    show_diff = '--diff' in sys.argv
    show_accum = '--accum' in sys.argv
    show_reset = '--reset' in sys.argv
    if not (show_diff or show_accum or show_reset):
        show_diff = show_accum = show_reset = True

    lines = open(path, encoding='utf-8', errors='ignore').read().splitlines()
    for idx, line in enumerate(lines):
        if 'Read VString:' not in line:
            continue
        which = None
        if 'RC_VS_SPEC_ACCUM' in line:
            which = 'SPEC_ACCUM'
        elif 'RC_VS_SPEC_RESET' in line:
            which = 'SPEC_RESET'
        elif 'RC_VS_SPEC_DIFF' in line:
            which = 'SPEC_DIFF'
        if which is None:
            continue
        data = extract_response(lines, idx)
        if data is None:
            continue
        ln = idx + 1
        if which == 'SPEC_ACCUM' and show_accum:
            ts, a0, a1, a2 = struct.unpack_from('<Ifff', data)
            try:
                counts = decode_v1_counts(data[16:])
            except ValueError as e:
                counts = f'ERR {e}'
            print(
                f'{ln:5d} {which:10s} len={len(data):4d} ts={ts:9d} a0={a0:.4f} a1={a1:.4f} a2={a2:.4f} channels={len(counts) if isinstance(counts, list) else counts}'
            )
        elif which == 'SPEC_RESET' and show_reset:
            ts = struct.unpack_from('<I', data)[0]
            try:
                counts = decode_v1_counts(data[4:])
            except ValueError as e:
                counts = f'ERR {e}'
            print(
                f'{ln:5d} {which:10s} len={len(data):4d} ts={ts:9d} channels={len(counts) if isinstance(counts, list) else counts}'
            )
        elif which == 'SPEC_DIFF' and show_diff:
            c0, c1 = struct.unpack_from('<II', data)
            print(f'{ln:5d} {which:10s} len={len(data):4d} hdr=({c0}, {c1}) body={data[8:].hex(" ")}')


if __name__ == '__main__':
    main()
