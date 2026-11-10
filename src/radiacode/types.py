"""Data records and enums used by the RadiaCode API."""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from enum import Enum

__all__ = [
    'AlarmLimits',
    'CTRL',
    'DeviceFlags',
    'DisplayDirection',
    'InterfaceType',
    'RealTimeFlags',
    'RecordFlags',
    'DoseCounter',
    'DoseRateDB',
    'Event',
    'EventId',
    'FlashArea',
    'RareData',
    'RawData',
    'RealTimeData',
    'SetExchange',
    'Spectrum',
]


@dataclass
class RealTimeData:
    """Real-time radiation measurement data from the device.

    Attributes:
        dt (datetime.datetime): Timestamp of the measurement
        count_rate (float): Number of counts per second
        count_rate_err (float): Count rate error percentage
        dose_rate (float): Radiation dose rate in device protocol units
        dose_rate_err (float): Dose rate measurement error percentage
        flags (int): Status flags for the measurement
        real_time_flags (int): Real-time status flags
    """

    dt: datetime.datetime
    count_rate: float
    count_rate_err: float
    dose_rate: float
    dose_rate_err: float
    flags: RecordFlags
    real_time_flags: RealTimeFlags


@dataclass
class RawData:
    """Raw radiation measurement data without error calculations.

    Attributes:
        dt (datetime.datetime): Timestamp of the measurement
        count_rate (float): Number of counts per second
        dose_rate (float): Radiation dose rate in device protocol units
    """

    dt: datetime.datetime
    count_rate: float
    dose_rate: float


@dataclass
class DoseRateDB:
    """Database record for dose rate measurements.

    Attributes:
        dt (datetime.datetime): Timestamp of the measurement
        count (int): Total number of counts in the measurement period
        count_rate (float): Number of counts per second
        dose_rate (float): Radiation dose rate in device protocol units
        dose_rate_err (float): Dose rate measurement error percentage
        flags (int): Status flags for the measurement
    """

    dt: datetime.datetime
    count: int
    count_rate: float
    dose_rate: float
    dose_rate_err: float
    flags: RecordFlags


@dataclass
class DoseCounter:
    """Accumulated-dose counter reading.

    Attributes:
        dt (datetime.datetime): Timestamp of the reading
        dose_counter (int): Accumulated dose counter value in device protocol units
        flags (int): Status flags
    """

    dt: datetime.datetime
    dose_counter: int
    flags: RecordFlags


@dataclass
class RareData:
    """Periodic device status and accumulated dose data.

    Attributes:
        dt (datetime.datetime): Timestamp of the status reading
        duration (int): Duration of dose accumulation in seconds
        dose (float): Accumulated dose in device protocol units
        temperature (float): Device temperature in degrees Celsius
        charge_level (float): Battery charge level as a percentage
        flags (int): Status flags
    """

    dt: datetime.datetime
    duration: int
    dose: float
    temperature: float
    charge_level: float
    flags: RecordFlags


class EventId(Enum):
    """Event identifiers emitted in buffered device data."""

    POWER_OFF = 0
    POWER_ON = 1
    LOW_BATTERY_SHUTOWN = 2
    CHANGE_DEVICE_PARAMS = 3
    DOSE_RESET = 4
    USER_EVENT = 5
    BATTERY_EMPTY_ALARM = 6
    CHARGE_START = 7
    CHARGE_STOP = 8
    DOSE_RATE_ALARM1 = 9
    DOSE_RATE_ALARM2 = 10
    DOSE_RATE_OFFSCALE = 11
    DOSE_ALARM1 = 12
    DOSE_ALARM2 = 13
    DOSE_OFFSCALE = 14
    TEMPERATURE_TOO_LOW = 15
    TEMPERATURE_TOO_HIGH = 16
    TEXT_MESSAGE = 17
    MEMORY_SNAPSHOT = 18
    SPECTRUM_RESET = 19
    COUNT_RATE_ALARM1 = 20
    COUNT_RATE_ALARM2 = 21
    COUNT_RATE_OFFSCALE = 22

    def __int__(self) -> int:
        return self.value


@dataclass
class Event:
    """Device event record.

    Alarm and off-scale events also carry the rate that triggered them, so
    `count_rate`/`count_rate_err` or `dose_rate`/`dose_rate_err` may be set.

    Attributes:
        dt (datetime.datetime): Timestamp of the event
        event (int): Event type identifier
        event_param1 (int): Event-specific parameter (channel mask)
        flags (int): Event flags
        count_rate (float): Count rate at alarm, if a count-rate event
        count_rate_err (float): Count-rate error in percent, if a count-rate event
        dose_rate (float): Dose rate at alarm, if a dose-rate event
        dose_rate_err (float): Dose-rate error in percent, if a dose-rate event
    """

    dt: datetime.datetime
    event: EventId
    event_param1: int
    flags: RecordFlags
    count_rate: float | None = None
    count_rate_err: float | None = None
    dose_rate: float | None = None
    dose_rate_err: float | None = None


class DeviceFlags:
    """Typed bitmask of the GET_STATUS device-status word.

    The device reports a single 32-bit status word; this class wraps the raw
    integer and exposes each known bit as a lowercase boolean attribute (e.g.
    ``flags.init_bit``) while keeping the raw value in ``.value``.

    Only the bits that plausibly apply to a radiation detector are named. The
    Android app's flag table also lists generic platform bits (SpO2, valves,
    pumps, pressure) that belong to other AlmaCode devices and are never set
    on a detector, so those are omitted here.

    The protocol bit names are also available as uppercase class constants —
    bit masks, not booleans — so mask math like ``flags.value &
    DeviceFlags.INIT_BIT`` works too.
    """

    BOOT_BIT = 1 << 0
    INIT_BIT = 1 << 1
    RUN_BIT = 1 << 2
    DEBUG_BIT = 1 << 3
    LCD_BIT = 1 << 4
    SDC_BIT = 1 << 5
    EMU_BIT = 1 << 6
    USB_TIMEOUT = 1 << 7
    IR1_LED_BIT = 1 << 8
    IR2_LED_BIT = 1 << 9
    FRAME_BIT = 1 << 10
    ACC_BIT = 1 << 11
    CH1_ENABLED = 1 << 16
    CH1_NOT_CONNECTED = 1 << 17
    CH1_HIGH_FREQ = 1 << 18
    CH1_READ_OVERFLOW = 1 << 19
    CH2_ENABLED = 1 << 24
    CH2_NOT_CONNECTED = 1 << 25
    CH2_HIGH_FREQ = 1 << 26
    CH2_READ_OVERFLOW = 1 << 27

    # lowercase attribute name -> bit mask
    _BITS = {
        'boot_bit': BOOT_BIT,
        'init_bit': INIT_BIT,
        'run_bit': RUN_BIT,
        'debug_bit': DEBUG_BIT,
        'lcd_bit': LCD_BIT,
        'sdc_bit': SDC_BIT,
        'emu_bit': EMU_BIT,
        'usb_timeout': USB_TIMEOUT,
        'ir1_led_bit': IR1_LED_BIT,
        'ir2_led_bit': IR2_LED_BIT,
        'frame_bit': FRAME_BIT,
        'acc_bit': ACC_BIT,
        'ch1_enabled': CH1_ENABLED,
        'ch1_not_connected': CH1_NOT_CONNECTED,
        'ch1_high_freq': CH1_HIGH_FREQ,
        'ch1_read_overflow': CH1_READ_OVERFLOW,
        'ch2_enabled': CH2_ENABLED,
        'ch2_not_connected': CH2_NOT_CONNECTED,
        'ch2_high_freq': CH2_HIGH_FREQ,
        'ch2_read_overflow': CH2_READ_OVERFLOW,
    }

    # protocol name -> bit mask, in the app's display order
    _NAMES = [
        ('BOOT_BIT', BOOT_BIT),
        ('INIT_BIT', INIT_BIT),
        ('RUN_BIT', RUN_BIT),
        ('DEBUG_BIT', DEBUG_BIT),
        ('LCD_BIT', LCD_BIT),
        ('SDC_BIT', SDC_BIT),
        ('EMU_BIT', EMU_BIT),
        ('USB_TIMEOUT', USB_TIMEOUT),
        ('IR1_LED_BIT', IR1_LED_BIT),
        ('IR2_LED_BIT', IR2_LED_BIT),
        ('FRAME_BIT', FRAME_BIT),
        ('ACC_BIT', ACC_BIT),
        ('Ch1 Enabled', CH1_ENABLED),
        ('Ch1 Not Connected', CH1_NOT_CONNECTED),
        ('Ch1 High Freq', CH1_HIGH_FREQ),
        ('Ch1 Read Overflow', CH1_READ_OVERFLOW),
        ('Ch2 Enabled', CH2_ENABLED),
        ('Ch2 Not Connected', CH2_NOT_CONNECTED),
        ('Ch2 High Freq', CH2_HIGH_FREQ),
        ('Ch2 Read Overflow', CH2_READ_OVERFLOW),
    ]

    def __init__(self, value: int):
        self.value = value

    def __int__(self) -> int:
        return self.value

    def __eq__(self, other: object) -> bool:
        if isinstance(other, DeviceFlags):
            return self.value == other.value
        return self.value == other

    def __getattr__(self, name: str) -> bool:
        if name in self._BITS:
            return bool(self.value & self._BITS[name])
        raise AttributeError(name)

    def __repr__(self) -> str:
        return f'DeviceFlags(0x{self.value:08X}: {", ".join(self.set)})'

    @property
    def set(self) -> list[str]:
        """The protocol names of every bit that is set, in bit order."""
        return [name for name, bit in self._NAMES if self.value & bit]


class RecordFlags:
    """Typed bitmask of a data-buffer record's `flags` field.

    These are a *different* bit table from `DeviceFlags` (GET_STATUS). The
    device packs several sub-fields into the u16 record `flags`:

    - a 2-bit **power source** in bits 13-14,
    - a 2-bit **temperature state** in bits 6-7,
    - single flags "Save to database" (bit 12), "Old data" (bit 15),
    - the **instantaneous alarm state** of the measurement channel: dose-rate
      alarm level in bits 0-1, count-rate alarm level in bits 8-9. These are
      set on `DoseRateDB` and `Event` records while a dose/count alarm is
      active (verified against a USB-capture alarm sequence).

    `power_source` and `temp_status` return the decoded sub-field value; the
    individual named flags are boolean attributes.
    """

    SAVE_TO_DATABASE = 1 << 12
    OLD_DATA = 1 << 15

    # alarm-state bits (instantaneous channel alarm levels)
    DOSE_RATE_ALARM_1 = 1 << 0
    DOSE_RATE_ALARM_2 = 1 << 1
    COUNT_RATE_ALARM_1 = 1 << 8
    COUNT_RATE_ALARM_2 = 1 << 9

    # power source (bits 13-14)
    POWER_ACCUM = 0x0000
    POWER_USB = 0x2000
    POWER_USB_CHARGING = 0x4000
    POWER_ACCUM_LOW = 0x6000
    _POWER_NAMES = {
        POWER_ACCUM: 'Accum',
        POWER_USB: 'USB',
        POWER_USB_CHARGING: 'USB, Chrg',
        POWER_ACCUM_LOW: 'Accum, Low',
    }

    # temperature state (bits 6-7)
    TEMP_NOT_DEFINED = 0x0000
    TEMP_TOO_LOW = 0x0080
    TEMP_TOO_HIGH = 0x00C0
    _TEMP_NAMES = {
        TEMP_NOT_DEFINED: 'Not defined',
        TEMP_TOO_LOW: 'Too low',
        TEMP_TOO_HIGH: 'Too high',
    }

    def __init__(self, value: int):
        self.value = value

    def __int__(self) -> int:
        return self.value

    def __eq__(self, other: object) -> bool:
        if isinstance(other, RecordFlags):
            return self.value == other.value
        return self.value == other

    def __repr__(self) -> str:
        return f'RecordFlags(0x{self.value:04X}: {", ".join(self.set)})'

    @property
    def save_to_database(self) -> bool:
        return bool(self.value & self.SAVE_TO_DATABASE)

    @property
    def old_data(self) -> bool:
        return bool(self.value & self.OLD_DATA)

    @property
    def dose_rate_alarm(self) -> int:
        """The active dose-rate alarm level, 0/1/2 (from bits 0-1)."""
        return self.value & 0x0003

    @property
    def count_rate_alarm(self) -> int:
        """The active count-rate alarm level, 0/1/2 (from bits 8-9)."""
        return (self.value & 0x0300) >> 8

    @property
    def power_source(self) -> str:
        """The decoded power source ('Accum', 'USB', 'USB, Chrg', 'Accum, Low')."""
        return self._POWER_NAMES.get(self.value & 0x6000, '?')

    @property
    def temp_status(self) -> str | None:
        """The decoded temperature state, or None if the sensor is undefined."""
        return self._TEMP_NAMES.get(self.value & 0xC0)

    @property
    def set(self) -> list[str]:
        names = []
        if self.save_to_database:
            names.append('Save to database')
        if self.old_data:
            names.append('Old data')
        if self.dose_rate_alarm:
            names.append(f'Dose rate: Alarm {self.dose_rate_alarm}')
        if self.count_rate_alarm:
            names.append(f'Count rate: Alarm {self.count_rate_alarm}')
        return names


class RealTimeFlags:
    """Typed bitmask of a RealTimeData record's `real_time_flags` (u8) field.

    These flag the alarm-sound / background-change state of the live
    measurement channel.
    """

    DOSE_RATE_ALARM_SOUND = 1 << 0
    DOSE_ALARM_SOUND = 1 << 1
    COUNT_RATE_ALARM_SOUND = 1 << 2
    ALARM_ACTIVE = 1 << 3
    RELIABLE_BGRND_CHANGE = 1 << 5
    BGRND_CHANGE_START = 1 << 6

    _NAMES = [
        ('Dose rate alarm sound', DOSE_RATE_ALARM_SOUND),
        ('Dose alarm sound', DOSE_ALARM_SOUND),
        ('Count rate alarm sound', COUNT_RATE_ALARM_SOUND),
        ('Alarm is active', ALARM_ACTIVE),
        ('Reliable bgrnd change', RELIABLE_BGRND_CHANGE),
        ('Bgrnd change start', BGRND_CHANGE_START),
    ]

    def __init__(self, value: int):
        self.value = value

    def __int__(self) -> int:
        return self.value

    def __eq__(self, other: object) -> bool:
        if isinstance(other, RealTimeFlags):
            return self.value == other.value
        return self.value == other

    def __repr__(self) -> str:
        return f'RealTimeFlags(0x{self.value:02X}: {", ".join(self.set)})'

    def __getattr__(self, name: str) -> bool:
        for flag_name, bit in self._NAMES:
            if flag_name == name:
                return bool(self.value & bit)
        raise AttributeError(name)

    @property
    def set(self) -> list[str]:
        """The protocol names of every bit that is set."""
        return [name for name, bit in self._NAMES if self.value & bit]


@dataclass
class Spectrum:
    """Radiation energy spectrum measurement data.

    Attributes:
        duration (datetime.timedelta): Measurement duration
        a0 (float): Energy calibration coefficient (offset)
        a1 (float): Energy calibration coefficient (linear)
        a2 (float): Energy calibration coefficient (quadratic)
        counts (list[int]): List of counts per energy channel
    """

    duration: datetime.timedelta
    a0: float
    a1: float
    a2: float
    counts: list[int]


@dataclass
class AlarmLimits:
    """Count-rate, dose-rate, and accumulated-dose alarm limits.

    The count rate may be per second or per minute depending on device
    configuration. The `count_unit` attribute indicates which.

    Dose rate is in micro-units (Sv or R) per hour, and accumulated dose is in
    micro-units (Sv or R). `dose_unit` identifies the configured unit. The
    device appears to use a fixed 100 Sv/R conversion internally.

    Attributes:
        l1_count_rate: Count-rate threshold for the level-one alarm.
        l2_count_rate: Count-rate threshold for the level-two alarm.
        count_unit: Count-rate unit, either `"cps"` or `"cpm"`.
        l1_dose_rate: Dose-rate threshold for the level-one alarm.
        l2_dose_rate: Dose-rate threshold for the level-two alarm.
        l1_dose: Accumulated-dose threshold for the level-one alarm.
        l2_dose: Accumulated-dose threshold for the level-two alarm.
        dose_unit: Dose unit, either `"Sv"` or `"R"`.
    """

    l1_count_rate: float
    l2_count_rate: float
    count_unit: str
    l1_dose_rate: float
    l2_dose_rate: float
    l1_dose: float
    l2_dose: float
    dose_unit: str


@dataclass
class FlashArea:
    """The decoded public-area descriptor read from flash via `RD_FLASH_AREA`.

    The device returns the flash region encrypted with a self-seeded PRNG
    keystream; the library decrypts it into this structured descriptor. The
    layout matches the Android app's `oo1` struct:

    ```
    PublicSignat(u32) StructLen(u32) BootSignat(u32) ProdSerNumber(32 bytes)
    TrgFileName(32 bytes) ProdName(64 bytes) CalibBP0(u32) CalibBP290(u32)
    VID(u16) PID(u16) MnfctName(32 bytes) Target_ID(u32) TargetStartTimeOut(u32)
    ```

    Attributes:
        public_signature: Magic identifier, e.g. `0x19601217`.
        struct_len: Length of the descriptor in bytes.
        boot_signature: Boot-area signature. A bit-packed date/time; see
            `boot_date`.
        prod_serial_number: Product serial number, e.g. `"RC-110-001068"`.
        trg_file_name: Firmware target file name, e.g. `"rc-110.bin"`.
        prod_name: Product name, e.g. `"RadiaCode-110"`.
        calib_bp0: Calibration value BP0.
        calib_bp290: Calibration value BP290.
        vid: USB vendor id, e.g. `0x0483`.
        pid: USB product id, e.g. `0xF123`.
        mnfct_name: Manufacturer name, e.g. `"RadiaCode"`.
        target_id: Target board identifier, e.g. `0xDADA0105`.
        target_start_timeout: Target start timeout in ms.
    """

    public_signature: int
    struct_len: int
    boot_signature: int
    prod_serial_number: str
    trg_file_name: str
    prod_name: str
    calib_bp0: int
    calib_bp290: int
    vid: int
    pid: int
    mnfct_name: str
    target_id: int
    target_start_timeout: int

    @property
    def boot_date(self) -> datetime.datetime:
        """The `boot_signature` decoded as a bit-packed UTC date/time.

        The high 16 bits pack `((year-1980)<<9 | month<<5 | day)` and the low
        16 bits pack `(hour<<11 | minute<<5 | seconds/2)`.
        """
        s = (self.boot_signature >> 16) & 0xFFFF
        s2 = self.boot_signature & 0xFFFF
        return datetime.datetime(
            ((s >> 9) & 127) + 1980,
            (s >> 5) & 15,
            s & 31,
            (s2 >> 11) & 31,
            (s2 >> 5) & 63,
            (s2 & 31) * 2,
            tzinfo=datetime.timezone.utc,
        )


class InterfaceType(Enum):
    """The physical interface the device reports over `SET_EXCHANGE`.

    The value is the device's ``IF_TYPE`` byte. The device reports the
    interface it is currently exchanging on — `USB` (1) when a host has it
    attached over USB, `BLE` (2) when the Android app connects over Bluetooth.
    `UNKNOWN` (0) is used for any unobserved code.
    """

    UNKNOWN = 0
    USB = 1
    BLE = 2

    def __int__(self) -> int:
        return self.value


class SetExchange:
    """Decoded `SET_EXCHANGE` response.

    `SET_EXCHANGE` negotiates the transport buffers and reports which physical
    interface the device is currently connected over, plus whether that
    interface is ready for a new client.

    When a host connects over USB, the device reports `IF_TYPE=1` (USB) and a
    larger `tx_size` (8224 bytes); over Bluetooth it reports `IF_TYPE=2` (BLE)
    and `tx_size=4128`. If the device is already occupied — e.g. the Android
    app tries Bluetooth while a desktop app holds the USB interface — it
    responds `if_ready=False` with the *active* interface's `if_type`.

    Attributes:
        target_id: Firmware target identifier (e.g. ``0xDADA0105``).
        tx_size: Device transmit (device-to-host) buffer size in bytes.
        rx_size: Device receive (host-to-device) buffer size in bytes.
        if_type: The physical interface currently active (`InterfaceType`).
        if_ready: Whether that interface is ready for a new exchange client.
    """

    def __init__(
        self,
        target_id: int,
        tx_size: int,
        rx_size: int,
        if_ready: int,
        if_type: int,
    ):
        self.target_id = target_id
        self.tx_size = tx_size
        self.rx_size = rx_size
        self.if_ready = bool(if_ready)
        self._if_type_raw = if_type
        try:
            self.if_type = InterfaceType(if_type)
        except ValueError:
            self.if_type = InterfaceType.UNKNOWN

    def __int__(self) -> int:
        return self.if_type.value

    def __eq__(self, other: object) -> bool:
        if isinstance(other, SetExchange):
            return all(
                (
                    self.target_id == other.target_id,
                    self.tx_size == other.tx_size,
                    self.rx_size == other.rx_size,
                    self.if_ready == other.if_ready,
                    self.if_type == other.if_type,
                )
            )
        return self.if_type == other

    def __repr__(self) -> str:
        state = 'ready' if self.if_ready else 'busy'
        return (
            f'SetExchange(if_type={self.if_type.name}, {state}, '
            f'tx_size={self.tx_size}, rx_size={self.rx_size}, target_id=0x{self.target_id:08X})'
        )


class DisplayDirection(Enum):
    """Display orientation modes accepted by the device."""

    AUTO = 0
    RIGHT = 1
    LEFT = 2

    def __int__(self) -> int:
        return self.value


# Conveniently, the radiacode tells us what VSFRs are available and what their
# data types are. By reading the SFR_FILE (Special Function Register?) string,
# we get a list of all the SFRs with their address (opcode), their size in bytes,
# their type (int or float), and whether they're signed or not.
class VSFR(Enum):
    """Low-level virtual special-function register identifiers."""

    DEVICE_CTRL = 0x0500
    DEVICE_LANG = 0x0502
    DEVICE_ON = 0x0503
    DEVICE_TIME = 0x0504

    DISP_CTRL = 0x0510
    DISP_BRT = 0x0511
    DISP_CONTR = 0x0512
    DISP_OFF_TIME = 0x0513
    DISP_ON = 0x0514
    DISP_DIR = 0x0515
    DISP_BACKLT_ON = 0x0516

    SOUND_CTRL = 0x0520
    SOUND_VOL = 0x0521
    SOUND_ON = 0x0522
    SOUND_BUTTON = 0x0523

    VIBRO_CTRL = 0x0530
    VIBRO_ON = 0x0531

    LEDS_CTRL = 0x0540
    LED0_BRT = 0x0541
    LED1_BRT = 0x0542
    LED2_BRT = 0x0543
    LED3_BRT = 0x0544
    LEDS_ON = 0x0545

    ALARM_MODE = 0x05E0
    PLAY_SIGNAL = 0x05E1

    MS_CTRL = 0x0600
    MS_MODE = 0x0601
    MS_SUB_MODE = 0x0602
    MS_RUN = 0x0603

    BLE_TX_PWR = 0x0700

    DR_LEV1_uR_h = 0x8000
    DR_LEV2_uR_h = 0x8001
    DS_LEV1_100uR = 0x8002
    DS_LEV2_100uR = 0x8003
    DS_UNITS = 0x8004
    CPS_FILTER = 0x8005
    RAW_FILTER = 0x8006
    DOSE_RESET = 0x8007
    CR_LEV1_cp10s = 0x8008
    CR_LEV2_cp10s = 0x8009

    USE_nSv_h = 0x800C

    CHN_TO_keV_A0 = 0x8010
    CHN_TO_keV_A1 = 0x8011
    CHN_TO_keV_A2 = 0x8012
    CR_UNITS = 0x8013
    TEMP_UNITS = 0x8016
    DS_LEV1_uR = 0x8014
    DS_LEV2_uR = 0x8015

    CPS = 0x8020
    DR_uR_h = 0x8021
    DS_uR = 0x8022

    TEMP_degC = 0x8024
    ACC_X = 0x8025
    ACC_Y = 0x8026
    ACC_Z = 0x8027
    OPT = 0x8028

    RAW_TEMP_degC = 0x8033
    TEMP_UP_degC = 0x8034
    TEMP_DN_degC = 0x8035

    VBIAS_mV = 0xC000
    COMP_LEV = 0xC001
    CALIB_MODE = 0xC002
    DPOT_RDAC = 0xC004
    DPOT_RDAC_EEPROM = 0xC005
    DPOT_TOLER = 0xC006

    SYS_MCU_ID0 = 0xFFFF0000
    SYS_MCU_ID1 = 0xFFFF0001
    SYS_MCU_ID2 = 0xFFFF0002

    SYS_DEVICE_ID = 0xFFFF0005
    SYS_SIGNATURE = 0xFFFF0006
    SYS_RX_SIZE = 0xFFFF0007
    SYS_TX_SIZE = 0xFFFF0008
    SYS_BOOT_VERSION = 0xFFFF0009
    SYS_TARGET_VERSION = 0xFFFF000A
    SYS_STATUS = 0xFFFF000B
    SYS_MCU_VREF = 0xFFFF000C
    SYS_MCU_TEMP = 0xFFFF000D
    SYS_FW_VER_BT = 0xFFFF010

    def __int__(self) -> int:
        return self.value


_VSFR_FORMATS: dict = {
    VSFR.DEVICE_CTRL: 'B3x',
    VSFR.DEVICE_LANG: 'B3x',
    VSFR.DEVICE_ON: '?3x',
    VSFR.DEVICE_TIME: 'I',
    VSFR.BLE_TX_PWR: 'B3x',
    VSFR.DISP_CTRL: 'B3x',
    VSFR.DISP_BRT: 'B3x',
    VSFR.DISP_CONTR: 'B3x',
    VSFR.DISP_OFF_TIME: 'I',
    VSFR.DISP_ON: '?3x',
    VSFR.DISP_DIR: 'B3x',
    VSFR.DISP_BACKLT_ON: '?3x',
    VSFR.SOUND_CTRL: 'H2x',
    VSFR.SOUND_VOL: 'B3x',
    VSFR.SOUND_ON: '?3x',
    VSFR.VIBRO_CTRL: 'H2x',
    VSFR.VIBRO_ON: '?3x',
    VSFR.ALARM_MODE: 'B3x',
    VSFR.MS_RUN: '?3x',
    VSFR.PLAY_SIGNAL: 'B3x',
    VSFR.DR_LEV1_uR_h: 'I',
    VSFR.DR_LEV2_uR_h: 'I',
    VSFR.DS_LEV1_100uR: 'I',
    VSFR.DS_LEV2_100uR: 'I',
    VSFR.DS_LEV1_uR: 'I',
    VSFR.DS_LEV2_uR: 'I',
    VSFR.DS_UNITS: '?3x',
    VSFR.USE_nSv_h: '?3x',
    VSFR.CR_UNITS: '?3x',
    VSFR.TEMP_UNITS: '?3x',
    VSFR.CPS_FILTER: 'B3x',
    VSFR.CR_LEV1_cp10s: 'I',
    VSFR.CR_LEV2_cp10s: 'I',
    VSFR.DOSE_RESET: '?3x',
    VSFR.CHN_TO_keV_A0: 'f',
    VSFR.CHN_TO_keV_A1: 'f',
    VSFR.CHN_TO_keV_A2: 'f',
    VSFR.CPS: 'I',
    VSFR.DR_uR_h: 'I',
    VSFR.DS_uR: 'I',
    VSFR.TEMP_degC: 'f',
    VSFR.RAW_TEMP_degC: 'f',
    VSFR.TEMP_UP_degC: 'f',
    VSFR.TEMP_DN_degC: 'f',
    VSFR.ACC_X: 'h2x',
    VSFR.ACC_Y: 'h2x',
    VSFR.ACC_Z: 'h2x',
    VSFR.OPT: 'H2x',
    VSFR.VBIAS_mV: 'H2x',
    VSFR.COMP_LEV: 'h2x',
    VSFR.CALIB_MODE: '?3x',
    VSFR.SYS_MCU_ID0: 'I',
    VSFR.SYS_MCU_ID1: 'I',
    VSFR.SYS_MCU_ID2: 'I',
    VSFR.SYS_DEVICE_ID: 'I',
    VSFR.SYS_SIGNATURE: 'I',
    VSFR.SYS_RX_SIZE: 'H2x',
    VSFR.SYS_TX_SIZE: 'H2x',
    VSFR.SYS_BOOT_VERSION: 'I',
    VSFR.SYS_TARGET_VERSION: 'I',
    VSFR.SYS_STATUS: 'I',
    VSFR.SYS_MCU_VREF: 'i',
    VSFR.SYS_MCU_TEMP: 'i',
    VSFR.DPOT_RDAC: 'B3x',
    VSFR.DPOT_RDAC_EEPROM: 'B3x',
    VSFR.DPOT_TOLER: 'B3x',
}


class VS(Enum):
    """Low-level virtual-string identifiers used by the device protocol."""

    CONFIGURATION = 2
    FW_DESCRIPTOR = 3
    SERIAL_NUMBER = 8
    # UNKNOWN_13 = 0xd
    TEXT_MESSAGE = 0xF
    MEM_SNAPSHOT = 0xE0
    # UNKNOWN_240 = 0xf0
    DATA_BUF = 0x100
    SFR_FILE = 0x101
    SPECTRUM = 0x200
    ENERGY_CALIB = 0x202
    SPEC_ACCUM = 0x205
    SPEC_DIFF = 0x206  # spectrogram per-channel count diff; see decoders/spectrum.py
    SPEC_RESET = 0x207  # live/current spectrum; header is ts only (no calibration)

    def __int__(self) -> int:
        return self.value


class CTRL(Enum):
    """Device events that can trigger sound or vibration feedback."""

    BUTTONS = 1 << 0
    CLICKS = 1 << 1
    DOSE_RATE_ALARM_1 = 1 << 2
    DOSE_RATE_ALARM_2 = 1 << 3
    DOSE_RATE_OUT_OF_SCALE = 1 << 4
    DOSE_ALARM_1 = 1 << 5
    DOSE_ALARM_2 = 1 << 6
    DOSE_OUT_OF_SCALE = 1 << 7

    def __int__(self) -> int:
        return self.value


class COMMAND(Enum):
    """Low-level command identifiers used by the device protocol."""

    GET_STATUS = 0x0005
    SET_EXCHANGE = 0x0007
    GET_VERSION = 0x000A
    GET_SERIAL = 0x000B
    FW_IMAGE_GET_INFO = 0x0012
    FW_SIGNATURE = 0x0101
    RD_HW_CONFIG = 0x0807
    RD_VIRT_SFR = 0x0824
    WR_VIRT_SFR = 0x0825
    RD_VIRT_STRING = 0x0826
    WR_VIRT_STRING = 0x0827
    RD_VIRT_SFR_BATCH = 0x082A
    WR_VIRT_SFR_BATCH = 0x082B
    RD_VIRT_STRING_BATCH = 0x082C
    WR_VIRT_STRING_BATCH = 0x082D
    RD_FLASH = 0x081C
    RD_FLASH_AREA = 0x081C  # alias, matches the Android app's naming
    SET_TIME = 0x0A04
    SET_BT_EXCHANGE_ID = 0x0903

    def __int__(self) -> int:
        return self.value
