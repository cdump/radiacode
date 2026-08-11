# Spectra and calibration

## Current and accumulated spectra

`spectrum()` returns the current spectrum and `spectrum_accum()` returns the
accumulated spectrum. Both return a `Spectrum` containing:

- `duration`: live time as `datetime.timedelta`
- `counts`: counts indexed by channel number
- `a0`, `a1`, and `a2`: channel-to-energy calibration coefficients

```python
from radiacode import RadiaCode

with RadiaCode() as device:
    spectrum = device.spectrum()

print("Live time:", spectrum.duration.total_seconds(), "s")
print("Total counts:", sum(spectrum.counts))
```

## Convert a channel to energy

The calibration is quadratic: `E = a0 + a1*c + a2*c²`, where `c` is the
channel number and `E` is energy in keV. Use the supplied helper instead of
duplicating the formula:

```python
from radiacode import spectrum_channel_to_energy

energy_kev = spectrum_channel_to_energy(
    channel_number=42,
    a0=spectrum.a0,
    a1=spectrum.a1,
    a2=spectrum.a2,
)
```

## Read or update calibration

```python
from radiacode import RadiaCode

with RadiaCode() as device:
    coefficients = device.energy_calib()
    print(coefficients)  # [a0, a1, a2]
```

`set_energy_calib()` writes calibration values to the device. Preserve the
existing coefficients before changing them and only write values obtained from
a trusted calibration procedure.

```python
with RadiaCode() as device:
    previous = device.energy_calib()
    device.set_energy_calib([new_a0, new_a1, new_a2])
```

## Reset spectrum data

`spectrum_reset()` clears the current spectrum on the device. This is a device
operation and cannot be undone by the library.
