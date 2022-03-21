#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MQTT Pub script forward RadiaCode 101 data to MQTT server.

Then it may be used by smart home hubs like Home Assistant.
"""

import argparse
import dataclasses
import datetime
import json
import logging
import os
import sys
import threading
import typing

import paho.mqtt.client as mqtt

from radiacode import RadiaCode

logger = logging.getLogger('mqttpub')


class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime.date, datetime.datetime)):
            return obj.isoformat()


@dataclasses.dataclass
class Watchdog:
    timeout: float = 30.0
    timer: typing.Optional[threading.Timer] = None

    def on_timeout(self):
        logger.critical("Watchdog timeout!")
        # sys.exit(3)
        os._exit(3)

    def reset(self):
        if self.timer:
            self.timer.cancel()

        self.timer = threading.Timer(self.timeout, self.on_timeout)
        self.timer.start()


def setup_mqtt(args) -> typing.Tuple[mqtt.Client, str, str]:
    """Make a connection to MQTT Broker"""
    devid = (f"{args.bluetooth_mac or 'usb'}").replace(':', '').lower()
    client_id = f"radiacode-{devid}"
    base_path = f"{args.mqtt_topic_prefix}{devid}"
    lwt = f"{base_path}/LWT"

    client = mqtt.Client(client_id=client_id)
    if args.mqtt_password:
        client.username_pw_set(args.mqtt_user, args.mqtt_password)

    client.will_set(topic=lwt, payload='Offline', qos=1, retain=True)

    event = threading.Event()

    def on_connect(cli: mqtt.Client, userdata, flags, rc):
        logger.info('Connected to MQTT broker')

        event.set()
        cli.publish(topic=lwt, payload='Online', qos=1, retain=True)

    client.on_connect = on_connect

    client.connect(args.mqtt_host, args.mqtt_port)
    client.loop_start()

    if not event.wait(30.0):
        logger.critical("MQTT connection timeout.")
        sys.exit(1)

    return client, devid, base_path


def send_ha_discovery(client: mqtt.Client, rc: RadiaCode, base_path: str, devid: str):
    """Send discovery messages for Home Assistant"""
    logger.info("Sending Home Assistant discovery messages")

    # TODO: send discovery for DoseRate, and maybe RareData to show Battery level.


def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s\t%(message)s')

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bluetooth-mac', type=str, help='MAC address of radiascan device')
    parser.add_argument('--mqtt-host', type=str, default='localhost', help='MQTT server hostname')
    parser.add_argument('--mqtt-port', type=int, default=1883, help='MQTT server port')
    parser.add_argument('--mqtt-user', type=str, default='DVES', help='MQTT server username')
    parser.add_argument('--mqtt-password', type=str, default=None, help='MQTT server password')
    parser.add_argument('--mqtt-topic-prefix', type=str, default='radiacode/', help='MQTT topic prefix')
    parser.add_argument('--home-assistant', type=bool, help='Enable Home Assistant discovery messages')
    args = parser.parse_args()

    wdt = Watchdog()

    if args.bluetooth_mac:
        logger.info(f'Will use Bluetooth connection: {args.bluetooth_mac}')
        rc = RadiaCode(bluetooth_mac=args.bluetooth_mac)
    else:
        logger.info('Will use USB connection')
        rc = RadiaCode()

    client, devid, base_path = setup_mqtt(args)
    if args.home_assistant:
        send_ha_discovery(client, rc, base_path, devid)

    while True:
        for v in rc.data_buf():
            wdt.reset()

            topic = f"{base_path}/{v.__class__.__name__}"
            payload = json.dumps(dataclasses.asdict(v), cls=DateTimeEncoder)

            logger.info(f"Publish: {topic}: {payload}")
            client.publish(topic=topic, payload=payload, qos=1, retain=True)


if __name__ == '__main__':
    main()