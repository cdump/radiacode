"""RadiaCode Library

This module provides a Python interface for controlling RadiaCode radiation detection devices
via USB or Bluetooth connections. It supports device configuration, data acquisition, and
spectrum analysis.
"""

import datetime
import platform
import struct
from typing import Optional

from radiacode.bytes_buffer import BytesBuffer
from radiacode.decoders.databuf import decode_VS_DATA_BUF
from radiacode.decoders.spectrum import decode_RC_VS_SPECTRUM
from radiacode.transports.bluetooth import Bluetooth
from radiacode.transports.usb import Usb
from radiacode.types import (
    COMMAND,
    CTRL,
    VS,
    VSFR,
    DisplayDirection,
    DoseRateDB,
    Event,
    RareData,
    RawData,
    RealTimeData,
    Spectrum,
)


def spectrum_channel_to_energy(channel_number: int, a0: float, a1: float, a2: float) -> float:
    """Convert spectrometer channel number to energy in keV using quadratic calibration.

    Args:
        channel_number: Channel number from the spectrometer (integer)
        a0: Constant term coefficient (keV)
        a1: Linear term coefficient (keV/channel)
        a2: Quadratic term coefficient (keV/channel^2)

    Returns:
        float: Energy value in keV corresponding to the channel number
    """
    return a0 + a1 * channel_number + a2 * channel_number * channel_number


class RadiaCode:
    _connection: Bluetooth | Usb

    def __init__(
        self,
        bluetooth_mac: Optional[str] = None,
        serial_number: Optional[str] = None,
        ignore_firmware_compatibility_check: bool = False,
    ):
        """Initialize a RadiaCode device connection.

        This constructor establishes a connection to a RadiaCode device either via Bluetooth
        or USB, initializes the device, and performs firmware compatibility checks.

        Args:
            bluetooth_mac: Optional MAC address for Bluetooth connection. If provided and
                         Bluetooth is supported on the system, will connect via Bluetooth.
            serial_number: Optional USB serial number to connect to a specific device when
                         multiple devices are connected. Used only for USB connections.
            ignore_firmware_compatibility_check: If True, skips the firmware version
                                              compatibility check. Default is False.

        Raises:
            Exception: If the device firmware version is incompatible (< 4.8) and
                      ignore_firmware_compatibility_check is False.

        Note:
            - Bluetooth connectivity is not supported on macOS systems
            - If both bluetooth_mac and serial_number are None, connects to the first
              available USB device
            - The device is initialized with the current system time
        """
        self._seq = 0

        # Bluepy doesn't support MacOS: https://github.com/IanHarvey/bluepy/issues/44
        self._bt_supported = platform.system() != 'Darwin'

        if bluetooth_mac is not None and self._bt_supported is True:
            self._connection = Bluetooth(bluetooth_mac)
        else:
            self._connection = Usb(serial_number=serial_number)

        # init
        self.execute(COMMAND.SET_EXCHANGE, b'\x01\xff\x12\xff')
        self.set_local_time(datetime.datetime.now())
        self.device_time(0)
        self._base_time = datetime.datetime.now() + datetime.timedelta(seconds=128)

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

    def execute(self, reqtype: COMMAND, args: Optional[bytes] = None) -> BytesBuffer:
        req_seq_no = 0x80 + self._seq
        self._seq = (self._seq + 1) % 32

        req_header = struct.pack('<HBB', int(reqtype), 0, req_seq_no)
        request = req_header + (args or b'')
        full_request = struct.pack('<I', len(request)) + request

        response = self._connection.execute(full_request)
        resp_header = response.unpack('<4s')[0]
        assert req_header == resp_header, f'req={req_header.hex()} resp={resp_header.hex()}'
        return response

    def read_request(self, command_id: int | VS | VSFR) -> BytesBuffer:
        r = self.execute(COMMAND.RD_VIRT_STRING, struct.pack('<I', int(command_id)))
        retcode, flen = r.unpack('<II')
        assert retcode == 1, f'{command_id}: got retcode {retcode}'
        # HACK: workaround for new firmware bug(?)
        if r.size() == flen + 1 and r._data[-1] == 0x00:
            r._data = r._data[:-1]
        # END OF HACK
        assert r.size() == flen, f'{command_id}: got size {r.size()}, expect {flen}'
        return r

    def write_request(self, command_id: int | VSFR, data: Optional[bytes] = None) -> None:
        r = self.execute(COMMAND.WR_VIRT_SFR, struct.pack('<I', int(command_id)) + (data or b''))
        retcode = r.unpack('<I')[0]
        assert retcode == 1
        assert r.size() == 0

    def batch_read_vsfrs(self, vsfr_ids: list[VSFR]) -> list[int]:
        assert len(vsfr_ids)
        r = self.execute(COMMAND.RD_VIRT_SFR_BATCH, b''.join(struct.pack('<I', int(c)) for c in vsfr_ids))
        ret = [r.unpack('<I')[0] for _ in range(len(vsfr_ids))]
        assert r.size() == 0
        return ret

    def status(self) -> str:
        r = self.execute(COMMAND.GET_STATUS)
        flags = r.unpack('<I')
        assert r.size() == 0
        return f'status flags: {flags}'

    def set_local_time(self, dt: datetime.datetime) -> None:
        """Set the device's local time.

        Args:
            dt: datetime.datetime object containing the time to set on the device.
                The time components used are: year, month, day, hour, minute, second.
                Microseconds are ignored.
        """
        d = struct.pack('<BBBBBBBB', dt.day, dt.month, dt.year - 2000, 0, dt.second, dt.minute, dt.hour, 0)
        self.execute(COMMAND.SET_TIME, d)

    def fw_signature(self) -> str:
        r = self.execute(COMMAND.FW_SIGNATURE)
        signature = r.unpack('<I')[0]
        filename = r.unpack_string()
        idstring = r.unpack_string()
        return f'Signature: {signature:08X}, FileName="{filename}", IdString="{idstring}"'

    def fw_version(self) -> tuple[tuple[int, int, str], tuple[int, int, str]]:
        """Get firmware version information.

        Returns:
            tuple: A tuple containing two tuples:
                - Boot version: (major, minor, date string)
                - Target version: (major, minor, date string)
        """
        r = self.execute(COMMAND.GET_VERSION)
        boot_minor, boot_major = r.unpack('<HH')
        boot_date = r.unpack_string()
        target_minor, target_major = r.unpack('<HH')
        target_date = r.unpack_string()
        assert r.size() == 0
        return ((boot_major, boot_minor, boot_date), (target_major, target_minor, target_date.strip('\x00')))

    def hw_serial_number(self) -> str:
        """Get hardware serial number.

        Returns:
            str: Hardware serial number formatted as hyphen-separated hexadecimal groups
                (e.g. "12345678-9ABCDEF0")
        """
        r = self.execute(COMMAND.GET_SERIAL)
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
        """Get the device serial number.

        Returns:
            str: The device serial number as an ASCII string
        """
        r = self.read_request(VS.SERIAL_NUMBER)
        return r.data().decode('ascii')

    def commands(self) -> str:
        br = self.read_request(VS.SFR_FILE)
        return br.data().decode('ascii')

    # called with 0 after init!
    def device_time(self, v: int) -> None:
        """Set the device time value.

        Args:
            v: Time value in seconds to set on the device. Typically used with 0 after initialization.
        """
        self.write_request(VSFR.DEVICE_TIME, struct.pack('<I', v))

    def data_buf(self) -> list[DoseRateDB | RareData | RealTimeData | RawData | Event]:
        """Get buffered measurement data from the device."""
        r = self.read_request(VS.DATA_BUF)
        return decode_VS_DATA_BUF(r, self._base_time)

    def spectrum(self) -> Spectrum:
        """Get current spectrum data from the device.

        Returns:
            Spectrum: Object containing the current spectrum data
        """
        r = self.read_request(VS.SPECTRUM)
        return decode_RC_VS_SPECTRUM(r, self._spectrum_format_version)

    def spectrum_accum(self) -> Spectrum:
        """Get accumulated spectrum data from the device.

        Returns:
            Spectrum: Object containing the accumulated spectrum data
        """
        r = self.read_request(VS.SPEC_ACCUM)
        return decode_RC_VS_SPECTRUM(r, self._spectrum_format_version)

    def dose_reset(self) -> None:
        """Reset the accumulated dose measurements to zero.

        This clears all accumulated dose rate history and statistics.
        """
        self.write_request(VSFR.DOSE_RESET)

    def spectrum_reset(self) -> None:
        """Reset the current spectrum data to zero.

        This clears the current spectrum data buffer, effectively resetting the spectrum
        measurement to start fresh.
        """
        r = self.execute(COMMAND.WR_VIRT_STRING, struct.pack('<II', int(VS.SPECTRUM), 0))
        retcode = r.unpack('<I')[0]
        assert retcode == 1
        assert r.size() == 0

    def energy_calib(self) -> list[float]:
        """Get the energy calibration coefficients.

        Returns:
            list[float]: List of 3 calibration coefficients [a0, a1, a2] where:
                - a0: Constant term coefficient (keV)
                - a1: Linear term coefficient (keV/channel)
                - a2: Quadratic term coefficient (keV/channel^2)
        """
        r = self.read_request(VS.ENERGY_CALIB)
        return list(r.unpack('<fff'))

    def set_energy_calib(self, coef: list[float]) -> None:
        """Set the energy calibration coefficients.

        Args:
            coef: List of 3 calibration coefficients [a0, a1, a2] where:
                - a0: Constant term coefficient (keV)
                - a1: Linear term coefficient (keV/channel)
                - a2: Quadratic term coefficient (keV/channel^2)
        """
        assert len(coef) == 3
        pc = struct.pack('<fff', *coef)
        r = self.execute(COMMAND.WR_VIRT_STRING, struct.pack('<II', int(VS.ENERGY_CALIB), len(pc)) + pc)
        retcode = r.unpack('<I')[0]
        assert retcode == 1

    def set_language(self, lang='ru') -> None:
        """Set the device interface language.

        Args:
            lang: Language code string, either 'ru' for Russian or 'en' for English.
                Defaults to 'ru'.
        """
        assert lang in {'ru', 'en'}, 'unsupported lang value - use "ru" or "en"'
        self.write_request(VSFR.DEVICE_LANG, struct.pack('<I', bool(lang == 'en')))

    def set_device_on(self, on: bool) -> None:
        """Turn the device on or off.

        Args:
            on: True to turn device on, False to turn it off
        """
        self.write_request(VSFR.DEVICE_ON, struct.pack('<I', bool(on)))

    def set_sound_on(self, on: bool) -> None:
        """Enable or disable device sounds.

        Args:
            on: True to enable sounds, False to disable
        """
        self.write_request(VSFR.SOUND_ON, struct.pack('<I', bool(on)))

    def set_vibro_on(self, on: bool) -> None:
        """Enable or disable device vibration.

        Args:
            on: True to enable vibration, False to disable
        """
        self.write_request(VSFR.SOUND_ON, struct.pack('<I', bool(on)))

    def set_sound_ctrl(self, ctrls: list[CTRL]) -> None:
        """Configure which events trigger device sounds.

        Args:
            ctrls: List of CTRL enum values specifying which events should trigger sounds
        """
        flags = 0
        for c in ctrls:
            flags |= int(c)
        self.write_request(VSFR.SOUND_CTRL, struct.pack('<I', flags))

    def set_display_off_time(self, seconds: int) -> None:
        """Set the display auto-off timeout.

        Args:
            seconds: Time in seconds before display turns off automatically.
                    Must be one of: 5, 10, 15, or 30 seconds.
        """
        assert seconds in {5, 10, 15, 30}
        v = 3 if seconds == 30 else (seconds // 5) - 1
        self.write_request(VSFR.DISP_OFF_TIME, struct.pack('<I', v))

    def set_display_brightness(self, brightness: int) -> None:
        """Set the display brightness level.

        Args:
            brightness: Brightness level from 0 (minimum) to 9 (maximum)
        """
        assert 0 <= brightness <= 9
        self.write_request(VSFR.DISP_BRT, struct.pack('<I', brightness))

    def set_display_direction(self, direction: DisplayDirection) -> None:
        """Set the display orientation direction.

        Args:
            direction: DisplayDirection enum value specifying the desired orientation
        """
        assert isinstance(direction, DisplayDirection)
        self.write_request(VSFR.DISP_DIR, struct.pack('<I', int(direction)))

    def set_vibro_ctrl(self, ctrls: list[CTRL]) -> None:
        """Configure which events trigger device vibration.

        Args:
            ctrls: List of CTRL enum values specifying which events should trigger vibration.
                  Note: CTRL.CLICKS is not supported for vibration control.
        """
        flags = 0
        for c in ctrls:
            assert c != CTRL.CLICKS, 'CTRL.CLICKS not supported for vibro'
            flags |= int(c)
        self.write_request(VSFR.VIBRO_CTRL, struct.pack('<I', flags))
