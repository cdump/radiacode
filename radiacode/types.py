import datetime
from dataclasses import dataclass
from enum import Enum
from typing import List


@dataclass
class CountRate:
    dt: datetime.datetime
    count: int
    count_rate: int
    flags: int


@dataclass
class DoseRate:
    dt: datetime.datetime
    dose_rate: int
    dose_rate_err: int
    flags: int


@dataclass
class DoseRateDB:
    dt: datetime.datetime
    count: int
    count_rate: int
    dose_rate: int
    dose_rate_err: int
    flags: int


@dataclass
class RareData:
    dt: datetime.datetime
    duration: int  # for dose, in seconds
    dose: int
    temperature: int
    charge_level: int
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
    DISP_DR = 1301
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

    def __int__(self) -> int:
        return self.value


class VS(Enum):
    CONFIGURATION = 2
    DATA_BUF = 256
    SPECTRUM = 512
    ENERGY_CALIB = 514

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
