## RadiaCode

[Описание на русском языке](README_ru.md)

This is a library to work with the radiation detector and spectrometer [RadiaCode](https://scan-electronics.com/dosimeters/radiacode/radiacode-101) (101, 102, 103).

***The project is still under development and not stable. Thus, the API might change in the future.***

Example project ([backend](radiacode-examples/webserver.py), [frontend](radiacode-examples/webserver.html)):
![radiacode-webserver-example](./screenshot.png)

### Installation and example projects
```
# install library together with all the dependencies for the examples, remove [examples] if you don't need them
$ pip3 install 'radiacode[examples]' --upgrade

# launch the webserver from the screenshot above
# bluetooth: replace with the address of your device
$ python3 -m radiacode-examples.webserver --bluetooth-mac 52:43:01:02:03:04
# or the same, but via usb
$ sudo python3 -m radiacode-examples.webserver

# simple example for outputting information to the terminal, options are similar to the webserver example
$ python3 -m radiacode-examples.basic

# send data to the public monitoring project narodmon.ru
$ python3 -m radiacode-examples.narodmon --bluetooth-mac 52:43:01:02:03:04
```

### Development
- install [python poetry](https://python-poetry.org/docs/#installation)
- clone this repository
- install and run:
```
$ poetry install

$ poetry run python radiacode-examples/find-radiacode.py # To find your Radiacode over Bluetooth and discover its MAC address or UUID

$ poetry run python radiacode-examples/basic.py --help # To see all options

$ poetry run python radiacode-examples/basic.py --bluetooth-mac 52:43:01:02:03:04 # or without --bluetooth-mac for USB connection

$ poetry run python radiacode-examples/basic.py --bluetooth-uuid 1EDA584E-652C-2011-1211-B213EFADEED0 # on Mac for bluetooth connection
```

### Examples
To install the dependencies required to run the examples: ```poetry install -E examples```

### Supported OS

| OS  | Bluetooth | USB | Notes |
| :--- | :---: | :---: | :--- |
| Mac OS (Silicon/Intel)  | :white_check_mark:  | :white_check_mark: | BT only with UUID, Mac OS does not expose MAC addresses  |
| Linux  | :white_check_mark:  | :white_check_mark:  | USB requires ```libusb```|
| Windows  | :white_check_mark:  | :white_check_mark:  | USB required ```libusb``` |
| Windows (WSL)  | :x:  | :question:  | WSL does not provide direct access to hardware|

### Windows
Make sure ```libusb``` is installed:
- Download the [latest stable](https://github.com/libusb/libusb/releases) version
- Use [7-Zip](https://www.7-zip.org/download.html) to unpack it
- Pick the most recent ```libusb-1.0.dll``` file (for a *Windows 10/11 64-bit* installation, it should be in: ```libusb-1.x.xx\VS2022\MS64\dll```) 
- Copy the ```.dll``` in your ```C:\Windows\System32``` folder
- Run scripts as usual

### Mac Silicon/Intel
Make sure ```libusb``` is installed on your system, if you use [Homebrew](https://brew.sh/) you can run: 
- ```brew install libusb```

*Note:* Mac OS does not expose Bluetooth MAC addresses anymore. In order to connect to your device via Bluetooth you will need to supply either its ```serial number``` (or part of it) or its ```UUID```.

- **Serial number**: you can obtain it directly from the device, navigate to the **Info** menu, it should be in the form of: ```RC-10x-xxxxxx```
- **UUID**: the UUID depends on both devices and it will change if you try to connect to the *Radiacode* from another computer (in this case, you will just need to rediscover)

Discovering the UUID of your *Radiacode* is quite easy:
- Make sure the *Radiacode* is **disconnected** from other devices (such as your phone, so kill the *Radiacode app* and its background tasks)
- Run: ```poetry run python radiacode-examples/find-radiacode.py```

The script will return UUIDs for all available Radiacodes.

### Linux
Make sure ```libusb``` is installed on your system. For *Debian/Ubuntu/Raspberry PI*: 
- ```sudo apt install libusb```

You might have to tweak your ```udev``` configuration. On ```Debian/Ubuntu/Raspberry PI```:
- ```sudo nano /etc/udev/rules.d/99-com.rules```

Then add anywhere the following lines:

```
# Radiacode
SUBSYSTEM=="usb", ATTRS{idVendor}=="0483", ATTRS{idProduct}=="f123", MODE="0666"
```

Simply unplug and replug the Radiacode and run the scripts as per usual.

#### Bluetooth
To enable Bluetooth on a *Raspberry Pi*:
- ```sudo apt install bluetooth pi-bluetooth bluez blueman```

On *Debian/Ubuntu* you should have all necessary packages by default, otherwise just try: 
- ```sudo apt install bluetooth bluez```

## UUID and MAC Address
On `Windows` and `Linux` both `UUID` and `MAC addresses` can be used interchangeably, the library is flexible enough that it will try to establish a connection even if you supply a `UUID` where a `MAC address` is expected (e.g.: if you provide a `MAC address` while specifying `--bluetooth-uuid`). You will receive a warning anyway.

