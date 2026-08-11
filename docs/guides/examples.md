# Included examples

Install the optional dependencies first:

```shell
python -m pip install --upgrade "radiacode[examples]"
```

Every command accepts `--help`. The common connection flags are
`--bluetooth-mac` for Bluetooth and `--serial` for selecting a USB device.

## Terminal output

```shell
python -m radiacode.examples.basic
python -m radiacode.examples.basic --bluetooth-mac 52:43:01:02:03:04
```

This prints device identity, firmware, spectrum, and buffered measurements.

## Web interface

```shell
python -m radiacode.examples.webserver --listen-port 8080
```

Open `http://127.0.0.1:8080` in a browser. Add `--bluetooth-mac` to connect over
Bluetooth.

## Spectrum plot

```shell
python -m radiacode.examples.show-spectrum
```

The plotting example requires the `examples` extra because it uses NumPy and
Matplotlib.

## Prometheus exporter

```shell
python -m radiacode.examples.radiacode-exporter --port 5432
curl http://127.0.0.1:5432/metrics
```

## Narodmon exporter

```shell
python -m radiacode.examples.narodmon --help
```

Review an exporter's source and unit conversions before using its output for
monitoring or alerting.
