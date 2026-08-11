# Measurements and units

## Buffered records

`RadiaCode.data_buf()` decodes the device's mixed record stream into dataclasses:

| Record | Purpose |
| --- | --- |
| `RealTimeData` | Current count rate and dose rate, with percentage errors |
| `RawData` | Unfiltered count-rate and dose-rate values |
| `DoseRateDB` | Historical dose-rate database sample |
| `RareData` | Accumulated dose, temperature, battery charge, and duration |
| `Event` | Device event and its event-specific parameter |

All `dt` fields are `datetime.datetime` values derived from the connection's
base time and the timestamp offset supplied by the device.

```python
import time

from radiacode import RadiaCode, RealTimeData

with RadiaCode() as device:
    while True:
        for record in device.data_buf():
            if isinstance(record, RealTimeData):
                print(record.dt.isoformat(), record.count_rate, record.dose_rate)
        time.sleep(2)
```

## Units

- `count_rate` is counts per second.
- `count_rate_err` and `dose_rate_err` are percentages.
- `temperature` is degrees Celsius.
- `charge_level` is a percentage.
- `duration` in `RareData` is seconds.
- Spectrum energy values calculated from the calibration coefficients are keV.

`dose_rate` and accumulated `dose` are returned in the device protocol's
scaled values; `data_buf()` does not normalize them to a display unit. Keep the
raw value when storing data and apply an explicit, device-configuration-aware
conversion at the application boundary.

Alarm limits are different: `get_alarm_limits()` reports their unit in
`AlarmLimits.dose_unit` (`"Sv"` or `"R"`) and their count-rate unit in
`AlarmLimits.count_unit` (`"cps"` or `"cpm"`). Dose and dose-rate alarm values
are expressed in micro-units.

!!! warning

    Do not infer dose units only from the Python numeric type. The device can be
    configured for Sievert or Roentgen display units, and the underlying
    protocol uses its own scaling.

## Events

The `Event.event` field is an `EventId`. Compare enum members rather than their
numeric protocol values:

```python
from radiacode import Event, EventId, RadiaCode

with RadiaCode() as device:
    for record in device.data_buf():
        if isinstance(record, Event) and record.event is EventId.SPECTRUM_RESET:
            print("Spectrum reset at", record.dt)
```
