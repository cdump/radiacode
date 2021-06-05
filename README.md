## RadiaCode

Библиотека для работы с дозиметром [RadiaCode-101](https://scan-electronics.com/dosimeters/radiacode/radiacode-101)

Находится в разработке, доступны базовые команды: получение спектра, управление звуком и выбро, получение истории измерений и т.п.

API пока не стабилен и возможны большие изменения!

![screenshot](./screenshot.png)

### Как запустить
- Установить [python poetry](https://python-poetry.org/docs/#installation)
- Склонировать репозиторий, установить и запустить:
```
$ git clone https://github.com/cdump/radiacode.git
$ cd radiacode
$ poetry install
$ poetry run python3 example.py --bluetooth-mac 52:43:01:02:03:04
```
Без указания `--bluetooth-mac` будет использоваться USB подключение.
