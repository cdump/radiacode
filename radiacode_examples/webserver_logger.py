import argparse
import asyncio
import json
import pathlib
import signal
import logging
from logging.handlers import RotatingFileHandler
import ssl

from aiohttp import web

from radiacode import RadiaCode, RealTimeData

class RadiaCodeWebServer:
    def __init__(self):
        self.app = web.Application()
        self.app.ws_clients = []
        self.setup_logging()

    def setup_logging(self):
        # Set up logging for webserver
        webserver_log_file = '/var/log/radiacode_webserver.log'
        self.webserver_logger = logging.getLogger('radiacode.webserver')
        self.webserver_logger.setLevel(logging.INFO)
        webserver_handler = RotatingFileHandler(webserver_log_file, maxBytes=10*1024*1024, backupCount=5)
        webserver_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        webserver_handler.setFormatter(webserver_formatter)
        self.webserver_logger.addHandler(webserver_handler)

        # Set up logging for new readings
        readings_log_file = '/var/log/radiacode_readings.log'
        self.readings_logger = logging.getLogger('radiacode.readings')
        self.readings_logger.setLevel(logging.INFO)
        readings_handler = RotatingFileHandler(readings_log_file, maxBytes=10*1024*1024, backupCount=5)
        readings_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        readings_handler.setFormatter(readings_formatter)
        self.readings_logger.addHandler(readings_handler)

    def setup_routes(self):
        self.app.add_routes([
            web.get('/', self.handle_index),
            web.get('/spectrum', self.handle_spectrum),
            web.post('/spectrum/reset', self.handle_spectrum_reset),
            web.get('/ws', self.handle_ws),
        ])

    def setup_signal_handlers(self):
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, lambda: asyncio.create_task(self.shutdown()))

    async def on_startup(self, app):
        self.setup_signal_handlers()
        asyncio.create_task(self.process())

    async def on_shutdown(self, app):
        self.webserver_logger.info("Cleaning up resources...")
        if hasattr(app, 'rc_conn'):
            app.rc_conn.close()

    async def shutdown(self):
        self.webserver_logger.info("Shutting down...")
        for ws in self.app.ws_clients:
            await ws.close(code=1000, message='Server shutdown')
        await self.app.shutdown()
        await self.app.cleanup()
        asyncio.get_event_loop().stop()

    async def handle_index(self, request):
        index_path = pathlib.Path(__file__).parent.absolute() / 'webserver_logger.html'
        content = index_path.read_text()
        content = content.replace('</head>', f'<script>var isSecureConnection = {json.dumps(request.app["is_secure"])};</script></head>')
        return web.Response(text=content, content_type='text/html')

    async def handle_ws(self, request):
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        request.app.ws_clients.append(ws)
        async for _ in ws:
            pass
        request.app.ws_clients.remove(ws)
        return ws

    async def handle_spectrum(self, request):
        cn = request.app.rc_conn
        accum = request.query.get('accum') == 'true'
        spectrum = cn.spectrum_accum() if accum else cn.spectrum()
        spectrum_data = [(channel, cnt if cnt > 0 else 0.5) for channel, cnt in enumerate(spectrum.counts)]
        self.webserver_logger.info(f"Spectrum updated: {'accumulated' if accum else 'current'}")
        return web.json_response({
            'coef': [spectrum.a0, spectrum.a1, spectrum.a2],
            'duration': spectrum.duration.total_seconds(),
            'series': [{'name': 'spectrum', 'data': spectrum_data}],
        })

    async def handle_spectrum_reset(self, request):
        cn = request.app.rc_conn
        cn.spectrum_reset()
        self.webserver_logger.info("Spectrum reset")
        return web.json_response({})

    async def process(self):
        max_history_size = 128
        history = []
        while True:
            databuf = self.app.rc_conn.data_buf()
            for v in databuf:
                if isinstance(v, RealTimeData):
                    history.append(v)
                    self.readings_logger.info(f"{v.count_rate} cps, {v.dose_rate} Sv/h")

            history.sort(key=lambda x: x.dt)
            history = history[-max_history_size:]
            jdata = json.dumps({
                'series': [
                    {
                        'name': 'countrate',
                        'data': [(int(1000 * x.dt.timestamp()), x.count_rate) for x in history],
                    },
                    {
                        'name': 'doserate',
                        'data': [(int(1000 * x.dt.timestamp()), 10000 * x.dose_rate) for x in history],
                    },
                ],
                'latest': {
                    'countrate': history[-1].count_rate if history else None,
                    'doserate': history[-1].dose_rate if history else None,
                }
            })
            self.webserver_logger.info(f"Rates updated, sending to {len(self.app.ws_clients)} connected clients")
            await asyncio.gather(*[ws.send_str(jdata) for ws in self.app.ws_clients], asyncio.sleep(1.0))

    def run(self, args):
        self.app['is_secure'] = bool(args.ssl_cert and args.ssl_key)
        if args.bluetooth_mac:
            self.webserver_logger.info(f'Using Bluetooth connection with MAC: {args.bluetooth_mac}')
            self.app.rc_conn = RadiaCode(bluetooth_mac=args.bluetooth_mac)
        else:
            self.webserver_logger.info('Using USB connection')
            self.app.rc_conn = RadiaCode()

        self.app.on_startup.append(self.on_startup)
        self.app.on_shutdown.append(self.on_shutdown)
        
        self.setup_routes()
        
        ssl_context = None
        if self.app['is_secure']:
            ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            ssl_context.load_cert_chain(args.ssl_cert, args.ssl_key)
            self.webserver_logger.info(f'Starting HTTPS webserver on {args.listen_host}:{args.listen_port}')
        else:
            self.webserver_logger.info(f'Starting HTTP webserver on {args.listen_host}:{args.listen_port}')
            self.webserver_logger.warning('Running without SSL. It is recommended to use HTTPS in production.')
        
        web.run_app(self.app, host=args.listen_host, port=args.listen_port, ssl_context=ssl_context)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--bluetooth-mac', type=str, required=False, help='bluetooth MAC address of radiascan device')
    parser.add_argument('--listen-host', type=str, required=False, default='0.0.0.0', help='listen host for webserver')
    parser.add_argument('--listen-port', type=int, required=False, default=8102, help='listen port for webserver')
    parser.add_argument('--ssl-cert', type=str, required=False, help='path to SSL certificate file')
    parser.add_argument('--ssl-key', type=str, required=False, help='path to SSL private key file')
    args = parser.parse_args()

    server = RadiaCodeWebServer()
    server.run(args)

if __name__ == '__main__':
    main()