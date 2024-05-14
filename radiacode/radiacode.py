import datetime
import struct
import platform
import asyncio
from typing import List, Optional, Union

from radiacode.logger import Logger
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

    """ 
    To use this class synchronously:
        rc = Radiacode()
        serial = rc.serial_number()
    """

    def __init__(
        self,
        bluetooth_mac: Optional[str] = None,
        bluetooth_serial: Optional[str] = None,
        bluetooth_uuid: Optional[str] = None,
        serial_number: Optional[str] = None,
        ignore_firmware_compatibility_check: Optional[bool] = False,
        async_init: Optional[bool] = False,
    ):
        self._seq = 0
        self._usb = False
        self._async_init = async_init
        self._ignore_firmware_compatibility_check = ignore_firmware_compatibility_check
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        if platform.system() == 'Darwin' and bluetooth_mac:
            Logger.warning(
                'You would like to establish a bluetooth connection using a MAC address, but you appear to be on a Mac.'
            )
            Logger.warning('Apple does not expose Bluetooth MAC addresses anymore, so this method will not work.')
            Logger.warning('Try connecting to the device using another option (UUID or Serial).')

            raise Exception('Exception: The chosen connection method does not work on this platform.')

        if bluetooth_mac is not None:
            self._connection = Bluetooth(bluetooth_mac=bluetooth_mac)
        elif bluetooth_serial is not None:
            self._connection = Bluetooth(bluetooth_serial=bluetooth_serial)
        elif bluetooth_uuid is not None:
            self._connection = Bluetooth(bluetooth_uuid=bluetooth_uuid)
        else:
            self._usb = True
            # Connect over USB
            self._connection = Usb(serial_number=serial_number)

        if self._async_init is False:
            self.loop.run_until_complete(self._init_device())

    """ 
    Use this method to create an asynchronous Radiacode() object:
        rc = Radiacode.async_init()
        serial = await rc.async_serial_number()
    """

    @classmethod
    async def async_init(
        cls,
        bluetooth_mac: Optional[str] = None,
        bluetooth_serial: Optional[str] = None,
        bluetooth_uuid: Optional[str] = None,
        serial_number: Optional[str] = None,
        ignore_firmware_compatibility_check: Optional[bool] = False,
    ):
        if platform.system() == 'Darwin' and bluetooth_mac:
            Logger.warning('You want to connect over bluetooth using a MAC address, but you appear to be on a Mac.')
            Logger.warning('Apple does not expose Bluetooth MAC addresses anymore, so this method will not work.')
            Logger.warning('Try connecting to the device using another option (UUID or Serial).')

            raise Exception('Exception: The chosen connection method does not work on this platform.')

        self = cls(
            bluetooth_mac=bluetooth_mac,
            bluetooth_serial=bluetooth_serial,
            bluetooth_uuid=bluetooth_uuid,
            serial_number=serial_number,
            ignore_firmware_compatibility_check=ignore_firmware_compatibility_check,
            async_init=True,
        )

        await self._init_device()
        return self

    async def _init_device(self):
        if self._usb is False:
            # Connect over Bluetooth
            await self._connection.connect()

        # Init
        Logger.info('Initializing Radiacode...')
        await self._async_execute(b'\x07\x00', b'\x01\xff\x12\xff')

        self._base_time = datetime.datetime.now()
        await self.async_set_local_time(self._base_time)
        await self.async_device_time(0)

        (_, (vmaj, vmin, _)) = await self.async_fw_version()
        if self._ignore_firmware_compatibility_check is False and vmaj < 4 or (vmaj == 4 and vmin < 8):
            raise Exception(
                f'Incompatible firmware version {vmaj}.{vmin}, >=4.8 required. Upgrade device firmware or use radiacode==0.2.2'
            )

        self._spectrum_format_version = 0
        lines = await self.async_configuration()

        for line in lines.split('\n'):
            if line.startswith('SpecFormatVersion'):
                self._spectrum_format_version = int(line.split('=')[1])
                break

        Logger.notify('Initialization completed')

    def base_time(self) -> datetime.datetime:
        return self._base_time

    # def _execute(self, reqtype: bytes, args: Optional[bytes] = None) -> BytesBuffer:
    #     return self.loop.run_until_complete(self._async_execute(reqtype, args))

    def read_request(self, command_id: Union[int, VS, VSFR]) -> BytesBuffer:
        return self.loop.run_until_complete(self.async_read_request(command_id))

    def write_request(self, command_id: Union[int, VSFR], data: Optional[bytes] = None) -> None:
        return self.loop.run_until_complete(self.async_write_request(command_id, data))

    def batch_read_vsfrs(self, vsfr_ids: List[VSFR]) -> List[int]:
        return self.loop.run_until_complete(self.async_batch_read_vsfrs(vsfr_ids))

    def status(self) -> str:
        return self.loop.run_until_complete(self.async_status())

    def set_local_time(self, dt: datetime.datetime) -> None:
        return self.loop.run_until_complete(self.async_set_local_time(dt))

    def fw_signature(self) -> str:
        return self.loop.run_until_complete(self.async_fw_signature())

    def fw_version(self) -> tuple[tuple[int, int, str], tuple[int, int, str]]:
        return self.loop.run_until_complete(self.async_fw_version())

    def hw_serial_number(self) -> str:
        return self.loop.run_until_complete(self.async_hw_serial_number())

    def configuration(self) -> str:
        return self.loop.run_until_complete(self.async_configuration())

    def text_message(self) -> str:
        return self.loop.run_until_complete(self.async_text_message())

    def serial_number(self) -> str:
        return self.loop.run_until_complete(self.async_serial_number())

    def commands(self) -> str:
        return self.loop.run_until_complete(self.async_commands())

    def device_time(self, v: int) -> None:
        return self.loop.run_until_complete(self.async_device_time(v))

    def data_buf(self) -> List[Union[DoseRateDB, RareData, RealTimeData, RawData, Event]]:
        return self.loop.run_until_complete(self.async_data_buf())

    def spectrum(self) -> Spectrum:
        return self.loop.run_until_complete(self.async_spectrum())

    def spectrum_accum(self) -> Spectrum:
        return self.loop.run_until_complete(self.async_spectrum_accum())

    def dose_reset(self) -> None:
        return self.loop.run_until_complete(self.async_dose_reset())

    def spectrum_reset(self) -> None:
        return self.loop.run_until_complete(self.async_spectrum_reset())

    def energy_calib(self) -> List[float]:
        return self.loop.run_until_complete(self.async_energy_calib())

    def set_energy_calib(self, coef: List[float]) -> None:
        return self.loop.run_until_complete(self.async_set_energy_calib(coef))

    def set_language(self, lang='en') -> None:
        return self.loop.run_until_complete(self.async_set_language(lang))

    def set_device_on(self, on: bool):
        return self.loop.run_until_complete(self.async_set_device_on(on))

    def set_sound_on(self, on: bool) -> None:
        return self.loop.run_until_complete(self.async_set_sound_on(on))

    def set_vibro_on(self, on: bool) -> None:
        return self.loop.run_until_complete(self.async_set_vibro_on(on))

    def set_sound_ctrl(self, ctrls: List[CTRL]) -> None:
        return self.loop.run_until_complete(self.async_set_sound_ctrl(ctrls))

    def set_display_off_time(self, seconds: int) -> None:
        return self.loop.run_until_complete(self.async_set_display_off_time(seconds))

    def set_display_brightness(self, brightness: int) -> None:
        return self.loop.run_until_complete(self.async_set_display_brightness(brightness))

    def set_display_direction(self, direction: DisplayDirection) -> None:
        return self.loop.run_until_complete(self.async_set_display_direction(direction))

    def set_vibro_ctrl(self, ctrls: List[CTRL]) -> None:
        return self.loop.run_until_complete(self.async_set_vibro_ctrl(ctrls))

    async def _async_execute(self, reqtype: bytes, args: Optional[bytes] = None) -> BytesBuffer:
        assert len(reqtype) == 2
        req_seq_no = 0x80 + self._seq
        self._seq = (self._seq + 1) % 32

        req_header = reqtype + b'\x00' + struct.pack('<B', req_seq_no)
        request = req_header + (args or b'')
        full_request = struct.pack('<I', len(request)) + request

        response = await self._connection.execute(full_request)
        resp_header = response.unpack('<4s')[0]
        assert req_header == resp_header, f'req={req_header.hex()} resp={resp_header.hex()}'
        return response

    async def async_read_request(self, command_id: Union[int, VS, VSFR]) -> BytesBuffer:
        r = await self._async_execute(b'\x26\x08', struct.pack('<I', int(command_id)))
        retcode, flen = r.unpack('<II')
        assert retcode == 1, f'{command_id}: got retcode {retcode}'

        # HACK: workaround for new firmware bug(?)
        if r.size() == flen + 1 and r._data[-1] == 0x00:
            r._data = r._data[:-1]
        # END OF HACK

        assert r.size() == flen, f'{command_id}: got size {r.size()}, expect {flen}'
        return r

    async def async_write_request(self, command_id: Union[int, VSFR], data: Optional[bytes] = None) -> None:
        r = await self._async_execute(b'\x25\x08', struct.pack('<I', int(command_id)) + (data or b''))
        retcode = r.unpack('<I')[0]
        assert retcode == 1
        assert r.size() == 0

    async def async_batch_read_vsfrs(self, vsfr_ids: List[VSFR]) -> List[int]:
        assert len(vsfr_ids)
        r = await self._async_execute(b'\x2a\x08', b''.join(struct.pack('<I', int(c)) for c in vsfr_ids))
        ret = [r.unpack('<I')[0] for _ in range(len(vsfr_ids))]
        assert r.size() == 0
        return ret

    async def async_status(self) -> str:
        r = await self._async_execute(b'\x05\x00')
        flags = r.unpack('<I')
        assert r.size() == 0
        return f'status flags: {flags}'

    async def async_set_local_time(self, dt: datetime.datetime) -> None:
        d = struct.pack('<BBBBBBBB', dt.day, dt.month, dt.year - 2000, 0, dt.second, dt.minute, dt.hour, 0)
        await self._async_execute(b'\x04\x0a', d)

    async def async_fw_signature(self) -> str:
        r = await self._async_execute(b'\x01\x01')
        signature = r.unpack('<I')[0]
        filename = r.unpack_string()
        idstring = r.unpack_string()
        return f'Signature: {signature:08X}, FileName="{filename}", IdString="{idstring}"'

    async def async_fw_version(self) -> tuple[tuple[int, int, str], tuple[int, int, str]]:
        r = await self._async_execute(b'\x0a\x00')
        boot_minor, boot_major = r.unpack('<HH')
        boot_date = r.unpack_string()
        target_minor, target_major = r.unpack('<HH')
        target_date = r.unpack_string()
        assert r.size() == 0
        return ((boot_major, boot_minor, boot_date), (target_major, target_minor, target_date.strip('\x00')))

    async def async_hw_serial_number(self) -> str:
        r = await self._async_execute(b'\x0b\x00')
        serial_len = r.unpack('<I')[0]
        assert serial_len % 4 == 0
        serial_groups = [r.unpack('<I')[0] for _ in range(serial_len // 4)]
        assert r.size() == 0
        return '-'.join(f'{v:08X}' for v in serial_groups)

    async def async_configuration(self) -> str:
        r = await self.async_read_request(VS.CONFIGURATION)
        return r.data().decode('cp1251')

    async def async_text_message(self) -> str:
        r = await self.async_read_request(VS.TEXT_MESSAGE)
        return r.data().decode('ascii')

    async def async_serial_number(self) -> str:
        r = await self.async_read_request(8)
        return r.data().decode('ascii')

    async def async_commands(self) -> str:
        br = await self.async_read_request(257)
        return br.data().decode('ascii')

    # called with 0 after init!
    async def async_device_time(self, v: int) -> None:
        await self.async_write_request(VSFR.DEVICE_TIME, struct.pack('<I', v))

    async def async_data_buf(self) -> List[Union[DoseRateDB, RareData, RealTimeData, RawData, Event]]:
        r = await self.async_read_request(VS.DATA_BUF)
        return decode_VS_DATA_BUF(r, self._base_time)

    async def async_spectrum(self) -> Spectrum:
        r = await self.async_read_request(VS.SPECTRUM)
        return decode_RC_VS_SPECTRUM(r, self._spectrum_format_version)

    async def async_spectrum_accum(self) -> Spectrum:
        r = await self.async_read_request(VS.SPEC_ACCUM)
        return decode_RC_VS_SPECTRUM(r, self._spectrum_format_version)

    async def async_dose_reset(self) -> None:
        await self.async_write_request(VSFR.DOSE_RESET)

    async def async_spectrum_reset(self) -> None:
        r = await self._async_execute(b'\x27\x08', struct.pack('<II', int(VS.SPECTRUM), 0))
        retcode = r.unpack('<I')[0]
        assert retcode == 1
        assert r.size() == 0

    # used in spectrum_channel_to_energy
    async def async_energy_calib(self) -> List[float]:
        r = await self.async_read_request(VS.ENERGY_CALIB)
        return list(r.unpack('<fff'))

    async def async_set_energy_calib(self, coef: List[float]) -> None:
        assert len(coef) == 3
        pc = struct.pack('<fff', *coef)
        r = await self._async_execute(b'\x27\x08', struct.pack('<II', int(VS.ENERGY_CALIB), len(pc)) + pc)
        retcode = r.unpack('<I')[0]
        assert retcode == 1

    async def async_set_language(self, lang='en') -> None:
        assert lang in {'ru', 'en'}, 'unsupported lang value - use "ru" or "en"'
        await self.async_write_request(VSFR.DEVICE_LANG, struct.pack('<I', bool(lang == 'en')))

    async def async_set_device_on(self, on: bool):
        assert not on, 'only False value accepted'
        await self.async_write_request(VSFR.DEVICE_ON, struct.pack('<I', bool(on)))

    async def async_set_sound_on(self, on: bool) -> None:
        await self.async_write_request(VSFR.SOUND_ON, struct.pack('<I', bool(on)))

    async def async_set_vibro_on(self, on: bool) -> None:
        await self.async_write_request(VSFR.SOUND_ON, struct.pack('<I', bool(on)))

    async def async_set_sound_ctrl(self, ctrls: List[CTRL]) -> None:
        flags = 0

        for c in ctrls:
            flags |= int(c)
        await self.async_write_request(VSFR.SOUND_CTRL, struct.pack('<I', flags))

    async def async_set_display_off_time(self, seconds: int) -> None:
        assert seconds in {5, 10, 15, 30}
        v = 3 if seconds == 30 else (seconds // 5) - 1
        await self.async_write_request(VSFR.DISP_OFF_TIME, struct.pack('<I', v))

    async def async_set_display_brightness(self, brightness: int) -> None:
        assert 0 <= brightness and brightness <= 9
        await self.async_write_request(VSFR.DISP_BRT, struct.pack('<I', brightness))

    async def async_set_display_direction(self, direction: DisplayDirection) -> None:
        assert isinstance(direction, DisplayDirection)
        await self.async_write_request(VSFR.DISP_DIR, struct.pack('<I', int(direction)))

    async def async_set_vibro_ctrl(self, ctrls: List[CTRL]) -> None:
        flags = 0
        for c in ctrls:
            assert c != CTRL.CLICKS, 'CTRL.CLICKS not supported for vibro'
            flags |= int(c)
        await self.async_write_request(VSFR.VIBRO_CTRL, struct.pack('<I', flags))
