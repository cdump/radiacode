from __future__ import annotations

import asyncio
import concurrent.futures
import struct
import threading
import time

from bleak import BleakClient
from radiacode.bytes_buffer import BytesBuffer


class DeviceNotFound(Exception):
    pass


class ConnectionClosed(Exception):
    pass


class Bluetooth:
    _WRITE_CHARACTERISTIC = 'e63215e6-7003-49d8-96b0-b024798fb901'
    _NOTIFY_CHARACTERISTIC = 'e63215e7-7003-49d8-96b0-b024798fb901'

    def __init__(self, mac, poll_interval: float = 0.01):
        """Initialize a Bluetooth connection.

        Args:
            mac: Bluetooth device identifier. This is normally a MAC address on
                 Linux and Windows, and a CoreBluetooth UUID on macOS.
            poll_interval: Retained for backwards compatibility. Bleak delivers
                           notifications without polling.
        """
        del poll_interval

        self._resp_buffer = b''
        self._resp_size = 0
        self._response: bytes | None = None
        self._closing = False
        self._connection_lost = False
        self._response_ready = threading.Condition()
        self._execute_lock = threading.Lock()
        self._loop = asyncio.new_event_loop()
        self._loop_ready = threading.Event()
        self._thread = threading.Thread(target=self._run_event_loop, name='radiacode-bluetooth', daemon=True)
        self._thread.start()
        self._loop_ready.wait()
        self._client: BleakClient | None = None

        try:
            self._run(self._connect(mac), timeout=30.0)
        except (KeyboardInterrupt, SystemExit):
            self.close()
            raise
        except Exception as ex:
            self.close()
            raise DeviceNotFound('Device not found or bluetooth adapter is not powered on') from ex

    def _run_event_loop(self):
        asyncio.set_event_loop(self._loop)
        self._loop_ready.set()
        try:
            self._loop.run_forever()
        finally:
            pending = asyncio.all_tasks(self._loop)
            for task in pending:
                task.cancel()
            if pending:
                self._loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            self._loop.run_until_complete(self._loop.shutdown_asyncgens())
            self._loop.close()

    def _run(self, coroutine, timeout):
        future = asyncio.run_coroutine_threadsafe(coroutine, self._loop)
        try:
            return future.result(timeout)
        except concurrent.futures.TimeoutError:
            future.cancel()
            raise
        except BaseException:
            future.cancel()
            raise

    async def _connect(self, mac):
        self._client = BleakClient(mac, disconnected_callback=self._handle_disconnect)
        await self._client.connect()
        await self._client.start_notify(self._NOTIFY_CHARACTERISTIC, self._handle_notification)

    def _handle_disconnect(self, _client):
        with self._response_ready:
            self._connection_lost = True
            self._response_ready.notify_all()

    def _handle_notification(self, _characteristic, data):
        data = bytes(data)
        with self._response_ready:
            if self._resp_size == 0:
                self._resp_size = 4 + struct.unpack('<i', data[:4])[0]
                self._resp_buffer = data[4:]
            else:
                self._resp_buffer += data
            self._resp_size -= len(data)
            assert self._resp_size >= 0
            if self._resp_size == 0:
                self._response = self._resp_buffer
                self._resp_buffer = b''
                self._response_ready.notify_all()

    async def _write(self, req):
        assert self._client is not None
        for pos in range(0, len(req), 18):
            chunk = req[pos : min(pos + 18, len(req))]
            await self._client.write_gatt_char(self._WRITE_CHARACTERISTIC, chunk, response=False)

    def execute(self, req) -> BytesBuffer:
        with self._execute_lock:
            if self._closing:
                raise ConnectionClosed('Connection is closing')
            if self._connection_lost:
                raise ConnectionClosed('Bluetooth connection lost')

            with self._response_ready:
                self._resp_buffer = b''
                self._resp_size = 0
                self._response = None

            timeout_end = time.monotonic() + 10.0
            try:
                self._run(self._write(req), timeout=10.0)
            except Exception as err:
                if self._closing or self._connection_lost:
                    raise ConnectionClosed('Bluetooth connection lost') from err
                raise

            with self._response_ready:
                while self._response is None and not self._closing and not self._connection_lost:
                    remaining_time = timeout_end - time.monotonic()
                    if remaining_time <= 0:
                        raise TimeoutError('Response timeout')
                    self._response_ready.wait(remaining_time)

                if self._closing:
                    raise ConnectionClosed('Connection closed while waiting for response')
                if self._connection_lost:
                    raise ConnectionClosed('Bluetooth connection lost')

                response = self._response
                assert response is not None
                self._response = None
                return BytesBuffer(response)

    def close(self):
        """Disconnect from the Bluetooth device and release resources."""
        if self._closing:
            return
        self._closing = True

        with self._response_ready:
            self._response_ready.notify_all()

        if self._client is not None and self._loop.is_running():
            try:
                self._run(self._client.disconnect(), timeout=10.0)
            except Exception:
                pass
            self._client = None

        if self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread.is_alive() and threading.current_thread() is not self._thread:
            self._thread.join(timeout=10.0)
