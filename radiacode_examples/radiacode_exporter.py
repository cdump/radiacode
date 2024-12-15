import argparse
import time

import prometheus_client

from radiacode import RealTimeData, RadiaCode


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--bluetooth-mac', type=str, required=False, help='bluetooth MAC address of radiascan device')
    parser.add_argument('--update-interval', type=int, default=3, required=False, help='update interval (seconds)')
    parser.add_argument('--port', type=int, default=5432, required=False, help='prometheus http port')
    args = parser.parse_args()

    if args.bluetooth_mac:
        print('will use Bluetooth connection')
        rc = RadiaCode(bluetooth_mac=args.bluetooth_mac)
    else:
        print('will use USB connection')
        rc = RadiaCode()

    serial = rc.serial_number()

    metric_count_rate = prometheus_client.Gauge('radiacode_count_rate', 'count rate, CPS', ['device']).labels(serial)
    metric_count_rate_error = prometheus_client.Gauge('radiacode_count_rate_error', 'count rate error, %', ['device']).labels(
        serial
    )
    metric_dose_rate = prometheus_client.Gauge('radiacode_dose_rate', 'dose rate, μSv/h', ['device']).labels(serial)
    metric_dose_rate_error = prometheus_client.Gauge('radiacode_dose_rate_error', 'dose rate error, %', ['device']).labels(serial)

    prometheus_client.start_http_server(args.port)

    while True:
        for v in rc.data_buf():
            if isinstance(v, RealTimeData):
                metric_count_rate.set(v.count_rate)
                metric_count_rate_error.set(v.count_rate_err)
                metric_dose_rate.set(10000 * v.dose_rate)  # convert to μSv/h
                metric_dose_rate_error.set(v.dose_rate_err)

        time.sleep(args.update_interval)


if __name__ == '__main__':
    main()
