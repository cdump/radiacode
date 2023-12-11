import datetime
import struct
from typing import List, Optional, Union

from radiacode.bytes_buffer import BytesBuffer
from radiacode.decoders.databuf import decode_VS_DATA_BUF
from radiacode.decoders.spectrum import decode_RC_VS_SPECTRUM
from radiacode.transports.bluetooth import Bluetooth
from radiacode.transports.usb import Usb
from radiacode.types import CTRL, VS, VSFR, DisplayDirection, DoseRateDB, Event, RareData, RawData, RealTimeData, Spectrum


# channel number -> kEv
def spectrum_channel_to_energy(channel_number: int, a0: float, a1: float, a2: float) -> float:
    return a0 + a1 * channel_number + a2 * channel_number * channel_number


class RadiaCode:
    _connection: Union[Bluetooth, Usb]

    def __init__(
        self,
        bluetooth_mac: Optional[str] = None,
        serial_number: Optional[str] = None,
        ignore_firmware_compatibility_check: bool = False,
    ):
        self._seq = 0
        if bluetooth_mac is not None:
            self._connection = Bluetooth(bluetooth_mac)
        else:
            self._connection = Usb(serial_number=serial_number)

        # init
        self.execute(b'\x07\x00', b'\x01\xff\x12\xff')
        self._base_time = datetime.datetime.now()
        self.set_local_time(self._base_time)
        self.device_time(0)

        (_, (vmaj, vmin, _)) = self.fw_version()
        if ignore_firmware_compatibility_check is False and vmaj < 4 or (vmaj == 4 and vmin < 8):
            raise Exception(
                f'Incompatible firmware version {vmaj}.{vmin}, >=4.8 required. Upgrade device firmware or use radiacode==0.2.2'
            )

        self._spectrum_format_version = 0
        for line in self.configuration().split('\n'):
            if line.startswith('SpecFormatVersion'):
                self._spectrum_format_version = int(line.split('=')[1])
                break

    def base_time(self) -> datetime.datetime:
        return self._base_time

    def execute(self, reqtype: bytes, args: Optional[bytes] = None) -> BytesBuffer:
        assert len(reqtype) == 2
        req_seq_no = 0x80 + self._seq
        self._seq = (self._seq + 1) % 32

        req_header = reqtype + b'\x00' + struct.pack('<B', req_seq_no)
        request = req_header + (args or b'')
        full_request = struct.pack('<I', len(request)) + request

        response = self._connection.execute(full_request)
        resp_header = response.unpack('<4s')[0]
        assert req_header == resp_header, f'req={req_header.hex()} resp={resp_header.hex()}'
        return response

    def read_request(self, command_id: Union[int, VS, VSFR]) -> BytesBuffer:
        r = self.execute(b'\x26\x08', struct.pack('<I', int(command_id)))
        retcode, flen = r.unpack('<II')
        assert retcode == 1, f'{command_id}: got retcode {retcode}'
        # HACK: workaround for new firmware bug(?)
        if r.size() == flen + 1 and r._data[-1] == 0x00:
            r._data = r._data[:-1]
        # END OF HACK
        assert r.size() == flen, f'{command_id}: got size {r.size()}, expect {flen}'
        return r

    def write_request(self, command_id: Union[int, VSFR], data: Optional[bytes] = None) -> None:
        r = self.execute(b'\x25\x08', struct.pack('<I', int(command_id)) + (data or b''))
        retcode = r.unpack('<I')[0]
        assert retcode == 1
        assert r.size() == 0

    def batch_read_vsfrs(self, vsfr_ids: List[VSFR]) -> List[int]:
        assert len(vsfr_ids)
        r = self.execute(b'\x2a\x08', b''.join(struct.pack('<I', int(c)) for c in vsfr_ids))
        ret = [r.unpack('<I')[0] for _ in range(len(vsfr_ids))]
        assert r.size() == 0
        return ret

    def status(self) -> str:
        r = self.execute(b'\x05\x00')
        flags = r.unpack('<I')
        assert r.size() == 0
        return f'status flags: {flags}'

    def set_local_time(self, dt: datetime.datetime) -> None:
        d = struct.pack('<BBBBBBBB', dt.day, dt.month, dt.year - 2000, 0, dt.second, dt.minute, dt.hour, 0)
        self.execute(b'\x04\x0a', d)

    def fw_signature(self) -> str:
        r = self.execute(b'\x01\x01')
        signature = r.unpack('<I')[0]
        filename = r.unpack_string()
        idstring = r.unpack_string()
        return f'Signature: {signature:08X}, FileName="{filename}", IdString="{idstring}"'

    def fw_version(self) -> tuple[tuple[int, int, str], tuple[int, int, str]]:
        r = self.execute(b'\x0a\x00')
        boot_minor, boot_major = r.unpack('<HH')
        boot_date = r.unpack_string()
        target_minor, target_major = r.unpack('<HH')
        target_date = r.unpack_string()
        assert r.size() == 0
        return ((boot_major, boot_minor, boot_date), (target_major, target_minor, target_date))

    def hw_serial_number(self) -> str:
        r = self.execute(b'\x0b\x00')
        serial_len = r.unpack('<I')[0]
        assert serial_len % 4 == 0
        serial_groups = [r.unpack('<I')[0] for _ in range(serial_len // 4)]
        assert r.size() == 0
        return '-'.join(f'{v:08X}' for v in serial_groups)

    def configuration(self) -> str:
        r = self.read_request(VS.CONFIGURATION)
        return r.data().decode('cp1251')

    def text_message(self) -> str:
        r = self.read_request(VS.TEXT_MESSAGE)
        return r.data().decode('ascii')

    def serial_number(self) -> str:
        r = self.read_request(8)
        return r.data().decode('ascii')

    def commands(self) -> str:
        br = self.read_request(257)
        return br.data().decode('ascii')

    # called with 0 after init!
    def device_time(self, v: int) -> None:
        self.write_request(VSFR.DEVICE_TIME, struct.pack('<I', v))

    def data_buf(self) -> List[Union[DoseRateDB, RareData, RealTimeData, RawData, Event]]:
        r = self.read_request(VS.DATA_BUF)
        return decode_VS_DATA_BUF(r, self._base_time)

    def spectrum(self) -> Spectrum:
        r = self.read_request(VS.SPECTRUM)
        return decode_RC_VS_SPECTRUM(r, self._spectrum_format_version)

    def spectrum_accum(self) -> Spectrum:
        r = self.read_request(VS.SPEC_ACCUM)
        return decode_RC_VS_SPECTRUM(r, self._spectrum_format_version)

    def dose_reset(self) -> None:
        self.write_request(VSFR.DOSE_RESET)

    def spectrum_reset(self) -> None:
        r = self.execute(b'\x27\x08', struct.pack('<II', int(VS.SPECTRUM), 0))
        retcode = r.unpack('<I')[0]
        assert retcode == 1
        assert r.size() == 0

    # used in spectrum_channel_to_energy
    def energy_calib(self) -> List[float]:
        r = self.read_request(VS.ENERGY_CALIB)
        return list(r.unpack('<fff'))

    def set_language(self, lang='ru') -> None:
        assert lang in {'ru', 'en'}, 'unsupported lang value - use "ru" or "en"'
        self.write_request(VSFR.DEVICE_LANG, struct.pack('<I', bool(lang == 'en')))

    def set_device_on(self, on: bool):
        assert not on, 'only False value accepted'
        self.write_request(VSFR.DEVICE_ON, struct.pack('<I', bool(on)))

    def set_sound_on(self, on: bool) -> None:
        self.write_request(VSFR.SOUND_ON, struct.pack('<I', bool(on)))

    def set_vibro_on(self, on: bool) -> None:
        self.write_request(VSFR.SOUND_ON, struct.pack('<I', bool(on)))

    def set_sound_ctrl(self, ctrls: List[CTRL]) -> None:
        flags = 0
        for c in ctrls:
            flags |= int(c)
        self.write_request(VSFR.SOUND_CTRL, struct.pack('<I', flags))

    def set_display_off_time(self, seconds: int) -> None:
        assert seconds in {5, 10, 15, 30}
        v = 3 if seconds == 30 else (seconds // 5) - 1
        self.write_request(VSFR.DISP_OFF_TIME, struct.pack('<I', v))

    def set_display_brightness(self, brightness: int) -> None:
        assert 0 <= brightness and brightness <= 9
        self.write_request(VSFR.DISP_BRT, struct.pack('<I', brightness))

    def set_display_direction(self, direction: DisplayDirection) -> None:
        assert isinstance(direction, DisplayDirection)
        self.write_request(VSFR.DISP_DIR, struct.pack('<I', int(direction)))

    def set_vibro_ctrl(self, ctrls: List[CTRL]) -> None:
        flags = 0
        for c in ctrls:
            assert c != CTRL.CLICKS, 'CTRL.CLICKS not supported for vibro'
            flags |= int(c)
        self.write_request(VSFR.VIBRO_CTRL, struct.pack('<I', flags))
