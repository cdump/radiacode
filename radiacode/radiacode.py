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
    _VSFR_FORMATS,
    COMMAND,
    CTRL,
    VS,
    VSFR,
    AlarmLimits,
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

    def batch_read_vsfrs(self, vsfr_ids: list[VSFR]) -> tuple[int | float]:
        """Read multiple VSFRs

        Args:
            vsfr_ids: a list of VSFRs to fetch

        Returns a tuple of decoded items in appropriate formats, such as
        floating point for calibration, integers for counts,
        """
        nvsfr = len(vsfr_ids)
        if nvsfr == 0:
            raise ValueError('No VSFRs specified')

        # The batch read VSFR command payload is a bunch of little-endian uint32.
        # The first one is the number of VSFRs to read, followed by the VSFR ids
        # themselves.
        msg = [struct.pack('<I', nvsfr)]
        msg.extend([struct.pack('<I', int(c)) for c in vsfr_ids])
        r = self.execute(COMMAND.RD_VIRT_SFR_BATCH, b''.join(msg))

        # The device responds with a bunch of little-endian uint32. The first one is
        # a bitmask indicating which VSFRs were successfully read. If you request and
        # read one VSFR successfully, the value is 0x1. For two, it's 0x3. For three,
        # it's 0x07, and so on. If one VSFR fails to read, perhaps due to an invalid
        # VSFR number, its bit is 0. If three VSFRs are requested, and the middle one
        # fails, the first value would be 0b101, or 0x5 - not what would be expected.
        # For now, we fail the read operation, but in the future we might attempt to
        # decode the successfully read registers, but then we'd also have to identify
        # which ones they were.
        valid_flags = r.unpack('<I')[0]
        expected_flags = (1 << nvsfr) - 1
        if valid_flags != expected_flags:
            raise ValueError(f'Unexpected validity flags, bad vsfr_id? {valid_flags:08b} != {expected_flags:08b}')

        # the remaining data is sent as little-endian 32-bit values. We temporarily
        # pack them into uint32...
        tmp = r.unpack(f'<{nvsfr}I')

        # ... and then unpack them into real data types
        ret = []
        for i, v in enumerate(tmp):
            for x in struct.unpack(f'<{_VSFR_FORMATS[vsfr_ids[i]]}', struct.pack('<I', v)):
                if x is not None:
                    ret.append(x)

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

    def get_alarm_limits(self) -> AlarmLimits:
        "Retrieve the alarm limits"
        regs = [
            VSFR.CR_LEV1_cp10s,
            VSFR.CR_LEV2_cp10s,
            VSFR.DR_LEV1_uR_h,
            VSFR.DR_LEV2_uR_h,
            VSFR.DS_LEV1_uR,
            VSFR.DS_LEV2_uR,
            VSFR.DS_UNITS,
            VSFR.CR_UNITS,
        ]

        resp = self.batch_read_vsfrs(regs)

        dose_multiplier = 100 if resp[6] else 1
        count_multiplier = 60 if resp[7] else 1
        return AlarmLimits(
            l1_count_rate=resp[0] / 10 * count_multiplier,
            l2_count_rate=resp[1] / 10 * count_multiplier,
            l1_dose_rate=resp[2] / dose_multiplier,
            l2_dose_rate=resp[3] / dose_multiplier,
            l1_dose=resp[4] / 1e6 / dose_multiplier,
            l2_dose=resp[5] / 1e6 / dose_multiplier,
            dose_unit='Sv' if resp[6] else 'R',
            count_unit='cpm' if resp[7] else 'cps',
        )

    def set_alarm_limits(
        self,
        l1_count_rate: int | float | None = None,
        l2_count_rate: int | float | None = None,
        l1_dose_rate: int | float | None = None,
        l2_dose_rate: int | float | None = None,
        l1_dose: int | float | None = None,
        l2_dose: int | float | None = None,
        dose_unit_sv: bool | None = None,
        count_unit_cpm: bool | None = None,
    ) -> bool:
        """Set alarm limits - returns True if the specified limits were set

        Args:
            l1_count_rate: count rate at which to raise a level 1 alarm
            l2_count_rate: count rate at which to raise a level 2 alarm
            l1_dose_rate: dose rate (micro-unit/hr) at which to raise a level 1 alarm
            l2_dose_rate: dose rate (micro-unit/hr) at which to raise a level 2 alarm
            l1_dose: accumulated dose (micro-unit) at which to raise a level 1 alarm
            l2_dose: accumulated dose (micro-unit) at which to raise a level 2 alarm
            dose_unit_sv = specify the dose in Sievert rather than Roentgen
            count_unit_cpm = set device count rate reporting to cpm rather than cps

        Internally, the device stores count rate in counts/10s and dose in uR. It
        appears that the device uses a fixed 100Sv/R converstion.

        If count_unit_cpm is not specified, the count rate register(s) will be set to
        the specified values without any conversion. If it is specified, count rate
        will be scaled, and the display units register will also be set.

        If dose_unit_sv is not specified the dose argument is assumed to be in uR,
        and the dose alarm register will be set. If dose_unit_sv is true, the dose
        argument will be assumed to be in uSv, will be converted to uR and stored,
        and the display unit will be set to Sv.  If dose_unit_sv is False, the dose
        argument will be assumed to be in uR, will be stored as such, and the display
        unit will be set to Sv.
        """

        which_limits = []
        limit_values = []

        dose_multiplier = 100 if dose_unit_sv is True else 1
        if isinstance(count_unit_cpm, bool):
            count_multiplier = 1 / 6 if count_unit_cpm else 10
        else:
            count_multiplier = 1

        if isinstance(l1_count_rate, (int, float)):
            if l1_count_rate < 0:
                raise ValueError('bad l1_count_rate')
            which_limits.append(VSFR.CR_LEV1_cp10s)
            limit_values.append(round(l1_count_rate * count_multiplier))

        if isinstance(l2_count_rate, (int, float)):
            if l2_count_rate < 0:
                raise ValueError('bad l2_count_rate')
            which_limits.append(VSFR.CR_LEV2_cp10s)
            limit_values.append(round(l2_count_rate * count_multiplier))

        if isinstance(l1_dose_rate, (int, float)):
            if l1_dose_rate < 0:
                raise ValueError('bad l1_dose_rate')
            which_limits.append(VSFR.DR_LEV1_uR_h)
            limit_values.append(round(l1_dose_rate * dose_multiplier))

        if isinstance(l2_dose_rate, (int, float)):
            if l2_dose_rate < 0:
                raise ValueError('bad l2_dose_rate')
            which_limits.append(VSFR.DR_LEV2_uR_h)
            limit_values.append(round(l2_dose_rate * dose_multiplier))

        if isinstance(l1_dose, (int, float)):
            if l1_dose < 0:
                raise ValueError('bad l1_dose')
            which_limits.append(VSFR.DS_LEV1_uR)
            limit_values.append(round(l1_dose * dose_multiplier))

        if isinstance(l2_dose, (int, float)):
            if l2_dose < 0:
                raise ValueError('bad l2_dose')
            which_limits.append(VSFR.DS_LEV2_uR)
            limit_values.append(round(l2_dose * dose_multiplier))

        if isinstance(dose_unit_sv, bool):
            which_limits.append(VSFR.DS_UNITS)
            limit_values.append(int(dose_unit_sv))

        if isinstance(count_unit_cpm, bool):
            which_limits.append(VSFR.CR_UNITS)
            limit_values.append(int(count_unit_cpm))

        num_to_set = len(which_limits)
        if not num_to_set:
            raise ValueError('No limits specified')

        pack_items = [num_to_set] + [int(x) for x in which_limits] + limit_values
        pack_format = f'<I{num_to_set}I{num_to_set}I'
        resp = self.execute(COMMAND.WR_VIRT_SFR_BATCH, struct.pack(pack_format, *pack_items))
        expected_valid = (1 << len(which_limits)) - 1
        return expected_valid == resp.unpack('<I')[0]
