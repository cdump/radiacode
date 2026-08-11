# Device configuration

Configuration methods write their values to the connected device immediately.

```python
from radiacode import CTRL, DisplayDirection, RadiaCode

with RadiaCode() as device:
    device.set_language("en")
    device.set_display_brightness(5)
    device.set_display_off_time(30)
    device.set_display_direction(DisplayDirection.AUTO)
    device.set_sound_on(True)
    device.set_vibro_on(True)
    device.set_sound_ctrl([CTRL.BUTTONS, CTRL.DOSE_RATE_ALARM_1])
```

## Accepted values

| Method | Accepted values |
| --- | --- |
| `set_language` | `"en"` or `"ru"` |
| `set_display_brightness` | Integer from 0 through 9 |
| `set_display_off_time` | 5, 10, 15, or 30 seconds |
| `set_display_direction` | A `DisplayDirection` member |
| `set_sound_on`, `set_vibro_on`, `set_device_on` | Boolean |

`set_sound_ctrl()` and `set_vibro_ctrl()` accept lists of `CTRL` flags.
`CTRL.CLICKS` is not accepted by `set_vibro_ctrl()`.

## Alarm limits

Read all current alarm settings with `get_alarm_limits()`:

```python
with RadiaCode() as device:
    limits = device.get_alarm_limits()
    print(limits.count_unit, limits.l1_count_rate, limits.l2_count_rate)
    print(limits.dose_unit, limits.l1_dose_rate, limits.l2_dose_rate)
```

`set_alarm_limits()` updates only arguments that are supplied. Specify the
display units when you want the method to scale values and update the unit
registers:

```python
with RadiaCode() as device:
    device.set_alarm_limits(
        l1_count_rate=5,
        l2_count_rate=10,
        count_unit_cpm=False,
        l1_dose_rate=0.3,
        l2_dose_rate=1.0,
        dose_unit_sv=True,
    )
```

The method raises `ValueError` when no limit is supplied or when a numeric
limit is negative.

## Reset operations

`dose_reset()` and `spectrum_reset()` clear accumulated state on the device.
Treat them as irreversible device operations.
