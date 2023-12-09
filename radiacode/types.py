import datetime
from dataclasses import dataclass
from enum import Enum
from typing import List


@dataclass
class RealTimeData:
    dt: datetime.datetime
    count_rate: float
    count_rate_err: float  # %
    dose_rate: int
    dose_rate_err: int
    flags: int
    real_time_flags: int


@dataclass
class RawData:
    dt: datetime.datetime
    count_rate: float
    dose_rate: float


@dataclass
class DoseRateDB:
    dt: datetime.datetime
    count: int
    count_rate: float
    dose_rate: float
    dose_rate_err: float
    flags: int


@dataclass
class RareData:
    dt: datetime.datetime
    duration: int  # for dose, in seconds
    dose: float
    temperature: float
    charge_level: float
    flags: int


@dataclass
class Event:
    dt: datetime.datetime
    event: int
    event_param1: int
    flags: int


@dataclass
class Spectrum:
    duration: datetime.timedelta
    a0: float
    a1: float
    a2: float
    counts: List[int]


class DisplayDirection(Enum):
    AUTO = 0
    RIGHT = 1
    LEFT = 2

    def __int__(self) -> int:
        return self.value


class VSFR(Enum):
    DEVICE_CTRL = 1280
    DEVICE_ON = 1283
    DEVICE_LANG = 1282
    DEVICE_TIME = 1284
    DISP_CTRL = 1296
    DISP_BRT = 1297
    DISP_CONTR = 1298
    DISP_OFF_TIME = 1299
    DISP_ON = 1300
    DISP_DIR = 1301
    SOUND_CTRL = 1312
    SOUND_VOL = 1313
    SOUND_ON = 1314
    SOUND_BUTTON = 1315
    PLAY_SIGNAL = 1505
    VIBRO_CTRL = 1328
    VIBRO_ON = 1329
    LEDS_CTRL = 1344
    LED0_BRT = 1345
    LED1_BRT = 1346
    LED2_BRT = 1347
    LED3_BRT = 1348
    LEDS_ON = 1349
    ALARM_MODE = 1504
    MS_CTRL = 1536
    MS_MODE = 1537
    MS_SUB_MODE = 1538
    MS_RUN = 1539
    DOSE_RESET = 32775

    def __int__(self) -> int:
        return self.value


class VS(Enum):
    CONFIGURATION = 2
    TEXT_MESSAGE = 15
    DATA_BUF = 256
    SPECTRUM = 512
    ENERGY_CALIB = 514
    SPEC_ACCUM = 517
    SPEC_DIFF = 518  # TODO: what's that? Can be decoded by spectrum decoder
    SPEC_RESET = 519  # TODO: looks like spectrum, but our spectrum decoder fails with `vlen == 7 unsupported`
    # UNKNOWN_13 = 13
    # UNKNOWN_240 = 240

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
