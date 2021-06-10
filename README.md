## RadiaCode
Библиотека для работы с дозиметром [RadiaCode-101](https://scan-electronics.com/dosimeters/radiacode/radiacode-101), находится в разработке - API не стабилен и возможны изменения.

Пример использования ([backend](radiacode-examples/webserver.py), [frontend](radiacode-examples/webserver.html)):
![radiacode-webserver-example](./screenshot.png)

### Установка & запуск примера
```
# установка вместе с зависимостями для примеров, уберите [examples] если они вам не нужны
$ pip3 install 'radiacode[examples]' --upgrade

# Запуск вебсервера из скриншота выше
# bluetooth: замените на адрес вашего устройства
$ python3 -m radiacode-examples.webserver --bluetooth-mac 52:43:01:02:03:04

# или то же самое, но по usb
$ sudo python3 -m radiacode-examples.webserver

# или простой пример с выводом информации в терминал, опции аналогичны webserver
$ python3 -m radiacode-examples.basic
```

### Разработка
- Установить [python poetry](https://python-poetry.org/docs/#installation)
- Склонировать репозиторий, установить и запустить:
```
$ git clone https://github.com/cdump/radiacode.git
$ cd radiacode
$ poetry install
$ poetry run python3 radiacode-examples/basic.py --bluetooth-mac 52:43:01:02:03:04  # или без --bluetooth-mac для USB подключения
```
