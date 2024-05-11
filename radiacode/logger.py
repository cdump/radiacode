from enum import Enum


class LogLevel(Enum):
    Notification = ('notification', '[\033[1;32m\N{check mark}\033[0m]')
    Error = ('error', '[\033[1;31m\N{aegean check mark}\033[0m]')
    Info = ('info', '[\033[1;34m\N{information source}\033[0m]')
    Warning = ('warning', '[\033[1;35m\N{warning sign}\033[0m]')


class Logger:
    @staticmethod
    def log(message):
        print(message)

    @staticmethod
    def notify(message):
        Logger._log_level(message, LogLevel.Notification)

    @staticmethod
    def error(message):
        Logger._log_level(message, LogLevel.Error)

    @staticmethod
    def info(message):
        Logger._log_level(message, LogLevel.Info)

    @staticmethod
    def warning(message):
        Logger._log_level(message, LogLevel.Warning)

    @staticmethod
    def _log_level(message, level):
        prefix = level.value[1]
        print(f'{prefix} {message}')
