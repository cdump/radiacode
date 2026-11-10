import struct

from radiacode.bytes_buffer import BytesBuffer
from radiacode.types import FlashArea


def _decrypt(seed: int, data: bytes) -> tuple[int, bytes]:
    """Decrypt `data` with the LCG keystream, returning the updated seed.

    Each step advances a 32-bit LCG (`seed = seed * 22695477 + 1`) and XORs
    the next byte with `(seed >> 16) & 0xFF`. The seed is threaded through
    successive calls so the size header and the area bytes form one stream.
    """
    out = bytearray()
    for b in data:
        seed = (seed * 22695477 + 1) & 0xFFFFFFFF
        out.append(b ^ ((seed >> 16) & 0xFF))
    return seed, bytes(out)


def _read_cstring(br: BytesBuffer, size: int) -> str:
    """Read a fixed-size, NUL-padded ASCII string."""
    raw = br.unpack(f'<{size}s')[0]
    return raw.split(b'\x00', 1)[0].decode('ascii')


def decode_RC_RD_FLASH_AREA(br: BytesBuffer) -> FlashArea:
    """Decode an `RD_FLASH_AREA` response into a `FlashArea` descriptor.

    The response body is `status(u32)` (0 = FLASH_OK), a PRNG `seed(u32)`, an
    encrypted area-size `u32`, then `area_size` encrypted bytes. Both the size
    header and the area are decrypted with the same LCG keystream.

    Raises:
        ValueError: If the device reports a non-zero flash status.
    """
    status = br.unpack('<I')[0]
    if status != 0:
        raise ValueError(f'RD_FLASH_AREA failed: flash status {status} != 0')

    seed = br.unpack('<I')[0]
    enc_size = br.unpack('<4s')[0]
    seed, size_b = _decrypt(seed, enc_size)
    area_size = struct.unpack('<I', size_b)[0]

    area = br.unpack(f'<{area_size}s')[0]
    seed, plain = _decrypt(seed, area)

    pbr = BytesBuffer(plain)
    return FlashArea(
        public_signature=pbr.unpack('<I')[0],
        struct_len=pbr.unpack('<I')[0],
        boot_signature=pbr.unpack('<I')[0],
        prod_serial_number=_read_cstring(pbr, 32),
        trg_file_name=_read_cstring(pbr, 32),
        prod_name=_read_cstring(pbr, 64),
        calib_bp0=pbr.unpack('<I')[0],
        calib_bp290=pbr.unpack('<I')[0],
        vid=pbr.unpack('<H')[0],
        pid=pbr.unpack('<H')[0],
        mnfct_name=_read_cstring(pbr, 32),
        target_id=pbr.unpack('<I')[0],
        target_start_timeout=pbr.unpack('<I')[0],
    )
