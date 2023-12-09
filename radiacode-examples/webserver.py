import argparse
import asyncio
import json
import pathlib

from aiohttp import web

from radiacode import RadiaCode, RealTimeData


async def handle_index(request):
    return web.FileResponse(pathlib.Path(__file__).parent.absolute() / 'webserver.html')


async def handle_ws(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    request.app.ws_clients.append(ws)
    async for _ in ws:
        pass
    request.app.ws_clients.remove(ws)
    return ws


async def handle_spectrum(request):
    cn = request.app.rc_conn
    accum = request.query.get('accum') == 'true'
    spectrum = cn.spectrum_accum() if accum else cn.spectrum()
    # apexcharts can't handle 0 in logarithmic view
    spectrum_data = [(channel, cnt if cnt > 0 else 0.5) for channel, cnt in enumerate(spectrum.counts)]
    print('Spectrum updated')
    return web.json_response(
        {
            'coef': [spectrum.a0, spectrum.a1, spectrum.a2],
            'duration': spectrum.duration.total_seconds(),
            'series': [{'name': 'spectrum', 'data': spectrum_data}],
        },
    )


async def handle_spectrum_reset(request):
    cn = request.app.rc_conn
    cn.spectrum_reset()
    print('Spectrum reset')
    return web.json_response({})


async def process(app):
    max_history_size = 128
    history = []
    while True:
        databuf = app.rc_conn.data_buf()
        for v in databuf:
            if isinstance(v, RealTimeData):
                history.append(v)

        history.sort(key=lambda x: x.dt)
        history = history[-max_history_size:]
        jdata = json.dumps(
            {
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
            },
        )
        print(f'Rates updated, sending to {len(app.ws_clients)} connected clients')
        await asyncio.gather(*[ws.send_str(jdata) for ws in app.ws_clients], asyncio.sleep(1.0))


async def on_startup(app):
    asyncio.create_task(process(app))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--bluetooth-mac', type=str, required=False, help='bluetooth MAC address of radiascan device')
    parser.add_argument('--listen-host', type=str, required=False, default='0.0.0.0', help='listen host for webserver')
    parser.add_argument('--listen-port', type=int, required=False, default=8080, help='listen port for webserver')
    args = parser.parse_args()

    app = web.Application()
    app.ws_clients = []
    if args.bluetooth_mac:
        print('will use Bluetooth connection')
        app.rc_conn = RadiaCode(bluetooth_mac=args.bluetooth_mac)
    else:
        print('will use USB connection')
        app.rc_conn = RadiaCode()

    app.on_startup.append(on_startup)
    app.add_routes(
        [
            web.get('/', handle_index),
            web.get('/spectrum', handle_spectrum),
            web.post('/spectrum/reset', handle_spectrum_reset),
            web.get('/ws', handle_ws),
        ],
    )
    web.run_app(app, host=args.listen_host, port=args.listen_port)
