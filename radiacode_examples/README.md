# RadiaCode Library - Examples

[Описание на русском языке](README_ru.md)

These example projects are installed with the library if you specify `pip install radiacode[examples]` (instead of `pip install radiacode`).
Each example project provides information when using the parameter `--help`.

### 1. [basic.py](./basic.py)
Minimal example connecting to a device via USB or Bluetooth, obtaining serial number, spectrum and particle/dose measurements.
```
$ python3 -m radiacode-examples.basic --bluetooth-mac 52:43:01:02:03:04
```

### 2. [webserver.py](./webserver.py) & [webserver.html](./webserver.html)
Shows spectrum and particles/dose measurements in the web interface with automatic updates.
```
$ python3 -m radiacode-examples.webserver --bluetooth-mac 52:43:01:02:03:04 --listen-port 8080
```

### 3. [narodmon.py](./narodmon.py)
Sends measurements to the service [public monitoring project narodmon.ru](https://narodmon.ru).
```
$ python3 -m radiacode-examples.narodmon --bluetooth-mac 52:43:01:02:03:04
```

### 3. [radiacode-exporter.py](./radiacode-exporter.py)
Exports metrics for [prometheus](https://prometheus.io/)
```
$ python3 -m radiacode-examples.radiacode-exporter --bluetooth-mac 52:43:01:02:03:04 --port 5432
$ curl http://127.0.0.1:5432/metrics
```
