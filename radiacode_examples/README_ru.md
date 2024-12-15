# Примеры использования библиотеки

Устанавливаются с пакетом если указать `pip install radiacode[examples]` (вместо `pip install radiacode`)

У каждого примера есть справка по `--help`


### 1. [basic.py](./basic.py)
Минимальный пример, показывающий соединение с устройством по USB или Bluetooth и получение серийного номера, спектра и измерений числа частиц/дозы
```
$ python3 -m radiacode-examples.basic --bluetooth-mac 52:43:01:02:03:04
```

### 2. [webserver.py](./webserver.py) & [webserver.html](./webserver.html)
Спектр и число частиц/доза в веб интерфейсе с автоматическим обновлением
```
$ python3 -m radiacode-examples.webserver --bluetooth-mac 52:43:01:02:03:04 --listen-port 8080
```


### 3. [narodmon.py](./narodmon.py)
Отправка измерений в сервис [народный мониторинг narodmon.ru](https://narodmon.ru)
```
$ python3 -m radiacode-examples.narodmon --bluetooth-mac 52:43:01:02:03:04
```