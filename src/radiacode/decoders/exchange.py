from radiacode.bytes_buffer import BytesBuffer
from radiacode.types import SetExchange


def decode_SET_EXCHANGE(br: BytesBuffer) -> SetExchange:
    """Decode a `SET_EXCHANGE` response into a `SetExchange` descriptor.

    The response body is `TARGET_ID(u32) TX(u16) RX(u16) IF_READY(u8)
    IF_TYPE(u8)` with no retcode. `IF_TYPE` is the active physical interface
    (1 = USB, 2 = BLE) and `IF_READY` is whether that interface is ready for a
    new exchange client (0 = busy / in use elsewhere).

    Raises:
        ValueError: If the response is shorter than the fixed 10-byte body.
    """
    target_id, tx, rx, ready, if_type = br.unpack('<IHHBB')
    return SetExchange(target_id, tx, rx, ready, if_type)
