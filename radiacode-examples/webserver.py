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
    request.app['ws_clients'].append(ws)

    try:
        async for _ in ws:
            pass
    except Exception as e:
        print(f'Unexpected error in websocket: {str(e)}')
    finally:
        request.app['ws_clients'].remove(ws)

    return ws


async def handle_spectrum(request):
    cn = request.app['rc_conn']
    accum = request.query.get('accum') == 'true'

    try:
        spectrum = await (cn.async_spectrum_accum() if accum else cn.async_spectrum())
    except Exception as e:
        print(f'Unexpected error while fetching data: {str(e)}')
        return web.json_response({'error': str(e)}, status=500)

    # apexcharts can't handle 0 in logarithmic view
    spectrum_data = [(channel, cnt if cnt > 0 else 0.5) for channel, cnt in enumerate(spectrum.counts)]

    return web.json_response(
        {
            'coef': [spectrum.a0, spectrum.a1, spectrum.a2],
            'duration': spectrum.duration.total_seconds(),
            'series': [{'name': 'spectrum', 'data': spectrum_data}],
        }
    )


async def handle_spectrum_reset(request):
    cn = request.app['rc_conn']
    await cn.async_spectrum_reset()
    return web.json_response({'message': 'Spectrum reset'})


async def process(app):
    max_history_size = 128
    history = []

    while True:
        databuf = await app['rc_conn'].async_data_buf()

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

        print(f'Rates updated, sending to {len(app["ws_clients"])} connected clients')
        await asyncio.gather(*(ws.send_str(jdata) for ws in app['ws_clients']))
        await asyncio.sleep(1.0)


async def on_startup(app):
    app['process_task'] = asyncio.create_task(process(app))
    app['ws_clients'] = []


async def init_connection(app):
    if app['args'].bluetooth_mac:
        print('will use Bluetooth connection via MAC address')
        app['rc_conn'] = await RadiaCode.async_init(bluetooth_mac=app['args'].bluetooth_mac)
    elif app['args'].bluetooth_uuid:
        print('will use Bluetooth connection via UUID')
        app['rc_conn'] = await RadiaCode.async_init(bluetooth_uuid=app['args'].bluetooth_uuid)
    else:
        print('will use USB connection')
        app['rc_conn'] = await RadiaCode.async_init()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--bluetooth-mac', type=str, required=False, help='Bluetooth MAC address of radiascan device')
    parser.add_argument('--bluetooth-uuid', type=str, required=False, help='Bluetooth UUID of radiascan device')
    parser.add_argument('--listen-host', type=str, required=False, default='127.0.0.1', help='Listen host for webserver')
    parser.add_argument('--listen-port', type=int, required=False, default=8080, help='Listen port for webserver')
    args = parser.parse_args()

    app = web.Application()
    app['args'] = args
    app.on_startup.append(init_connection)
    app.on_startup.append(on_startup)

    app.add_routes(
        [
            web.get('/', handle_index),
            web.get('/spectrum', handle_spectrum),
            web.post('/spectrum/reset', handle_spectrum_reset),
            web.get('/ws', handle_ws),
        ]
    )

    web.run_app(app, host=args.listen_host, port=args.listen_port)


if __name__ == '__main__':
    main()
