import datetime
from dataclasses import dataclass
from enum import Enum


@dataclass
class RealTimeData:
    """Real-time radiation measurement data from the device.

    Attributes:
        dt (datetime.datetime): Timestamp of the measurement
        count_rate (float): Number of counts per second
        count_rate_err (float): Count rate error percentage
        dose_rate (int): Radiation dose rate measurement
        dose_rate_err (float): Dose rate measurement error percentage
        flags (int): Status flags for the measurement
        real_time_flags (int): Real-time status flags
    """

    dt: datetime.datetime
    count_rate: float
    count_rate_err: float
    dose_rate: int
    dose_rate_err: float
    flags: int
    real_time_flags: int


@dataclass
class RawData:
    """Raw radiation measurement data without error calculations.

    Attributes:
        dt (datetime.datetime): Timestamp of the measurement
        count_rate (float): Number of counts per second
        dose_rate (float): Radiation dose rate measurement
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
        dose_rate (float): Radiation dose rate measurement
        dose_rate_err (float): Dose rate measurement error percentage
        flags (int): Status flags for the measurement
    """

    dt: datetime.datetime
    count: int
    count_rate: float
    dose_rate: float
    dose_rate_err: float
    flags: int


@dataclass
class RareData:
    """Periodic device status and accumulated dose data.

    Attributes:
        dt (datetime.datetime): Timestamp of the status reading
        duration (int): Duration of dose accumulation in seconds
        dose (float): Accumulated radiation dose
        temperature (float): Device temperature reading
        charge_level (float): Battery charge level
        flags (int): Status flags
    """

    dt: datetime.datetime
    duration: int
    dose: float
    temperature: float
    charge_level: float
    flags: int


class EventId(Enum):
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

    Attributes:
        dt (datetime.datetime): Timestamp of the event
        event (int): Event type identifier
        event_param1 (int): Event-specific parameter
        flags (int): Event flags
    """

    dt: datetime.datetime
    event: EventId
    event_param1: int
    flags: int


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
    """Alarm limits

    The count rate may be per second or per minute depending on device
    configuration. The `count_unit` attribute indicates which.

    Dose rate is in micro-units (Sv or R) per hour.

    Accumulated dos is in micro-units (Sv or R).

    The dose unit may be Roentgen or Sievert depending on device
    configuration. The `dose_unit` attribute indicates which. There seems
    to be a fixed 100Sv/R conversion within the device
    """

    l1_count_rate: float
    l2_count_rate: float
    count_unit: str
    l1_dose_rate: float
    l2_dose_rate: float
    l1_dose: float
    l2_dose: float
    dose_unit: str


class DisplayDirection(Enum):
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
    VSFR.DEVICE_CTRL: '3xB',
    VSFR.DEVICE_LANG: '3xB',
    VSFR.DEVICE_ON: '3x?',
    VSFR.DEVICE_TIME: 'I',
    VSFR.BLE_TX_PWR: '3xB',
    VSFR.DISP_CTRL: '3xB',
    VSFR.DISP_BRT: '3xB',
    VSFR.DISP_CONTR: '3xB',
    VSFR.DISP_OFF_TIME: 'I',
    VSFR.DISP_ON: '3x?',
    VSFR.DISP_DIR: '3xB',
    VSFR.DISP_BACKLT_ON: '3x?',
    VSFR.SOUND_CTRL: '2xH',
    VSFR.SOUND_VOL: '3xB',
    VSFR.SOUND_ON: '3x?',
    VSFR.VIBRO_CTRL: '3xB',
    VSFR.VIBRO_ON: '3x?',
    VSFR.ALARM_MODE: '3xB',
    VSFR.MS_RUN: '3x?',
    VSFR.PLAY_SIGNAL: '3xB',
    VSFR.DR_LEV1_uR_h: 'I',
    VSFR.DR_LEV2_uR_h: 'I',
    VSFR.DS_LEV1_100uR: 'I',
    VSFR.DS_LEV2_100uR: 'I',
    VSFR.DS_LEV1_uR: 'I',
    VSFR.DS_LEV2_uR: 'I',
    VSFR.DS_UNITS: '3x?',
    VSFR.USE_nSv_h: '3x?',
    VSFR.CR_UNITS: '3x?',
    VSFR.CPS_FILTER: '3xB',
    VSFR.CR_LEV1_cp10s: 'I',
    VSFR.CR_LEV2_cp10s: 'I',
    VSFR.DOSE_RESET: '3x?',
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
    VSFR.ACC_X: '2xh',
    VSFR.ACC_Y: '2xh',
    VSFR.ACC_Z: '2xh',
    VSFR.OPT: '2xH',
    VSFR.VBIAS_mV: '2xH',
    VSFR.COMP_LEV: '2xh',
    VSFR.CALIB_MODE: '3x?',
    VSFR.SYS_MCU_ID0: 'I',
    VSFR.SYS_MCU_ID1: 'I',
    VSFR.SYS_MCU_ID2: 'I',
    VSFR.SYS_DEVICE_ID: 'I',
    VSFR.SYS_SIGNATURE: 'I',
    VSFR.SYS_RX_SIZE: '2xH',
    VSFR.SYS_TX_SIZE: '2xH',
    VSFR.SYS_BOOT_VERSION: 'I',
    VSFR.SYS_TARGET_VERSION: 'I',
    VSFR.SYS_STATUS: 'I',
    VSFR.SYS_MCU_VREF: 'i',
    VSFR.SYS_MCU_TEMP: 'i',
    VSFR.DPOT_RDAC: '3xB',
    VSFR.DPOT_RDAC_EEPROM: '3xB',
    VSFR.DPOT_TOLER: '3xB',
}


class VS(Enum):
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
    SPEC_DIFF = 0x206  # TODO: what's that? Can be decoded by spectrum decoder
    SPEC_RESET = 0x207  # TODO: looks like spectrum, but our spectrum decoder fails with `vlen == 7 unsupported`

    def __int__(self) -> int:
        return self.value


class CTRL(Enum):
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
    RD_FLASH = 0x081C
    SET_TIME = 0x0A04

    def __int__(self) -> int:
        return self.value
