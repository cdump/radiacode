# -*- coding: utf-8 -*-
"""
MQTT Pub script forward RadiaCode 101 data to MQTT server.

Then it may be used by smart home hubs like Home Assistant.
"""

import argparse
import logging
import typing

import paho.mqtt.client as mqtt

from radiacode import RadiaCode

logger = logging.getLogger(__name__)


def send_ha_discovery(client: mqtt.Client, base_path: str, devid: str):
    """Send discovery messages for Home Assistant"""
    logger.info("Sending Home Assistant discovery messages")


def setup_mqtt(args) -> typing.Tuple[mqtt.Client, str]:
    """Make a connection to MQTT Broker"""
    devid = f"{args.bluetooth_mac or 'usb'}"
    client_id = f"radiacode-{devid}"
    base_path = f"{args.mqtt_topic_prefix}{devid}"
    lwt = f"{base_path}/LWT"

    client = mqtt.Client(client_id=client_id)
    if args.mqtt_password:
        client.username_pw_set(args.mqtt_user, args.mqtt_password)

    client.will_set(topic=lwt, payload='Offline', qos=1, retain=True)

    def on_connect(cli: mqtt.Client, userdata, flags, rc):
        logger.info('Connected to MQTT broker')

        cli.publish(topic=lwt, payload='Online', qos=1, retain=True)

        if args.home_assistant:
            send_ha_discovery(cli, base_path, devid)

    client.on_connect = on_connect

    client.connect(args.mqtt_host, args.mqtt_port)
    client.loop_start()

    return client, base_path


def main():
    logging.basicConfig()

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bluetooth-mac', type=str, help='MAC address of radiascan device')
    parser.add_argument('--mqtt-host', type=str, default='localhost', help='MQTT server hostname')
    parser.add_argument('--mqtt-port', type=int, default=1883, help='MQTT server port')
    parser.add_argument('--mqtt-user', type=str, default='DVES', help='MQTT server username')
    parser.add_argument('--mqtt-password', type=str, default=None, help='MQTT server password')
    parser.add_argument('--mqtt-topic-prefix', type=str, default='radiacode/', help='MQTT topic prefix')
    parser.add_argument('--home-assistant', type=bool, help='Enable Home Assistant discovery messages')
    args = parser.parse_args()

    client, base_path = setup_mqtt(args)


if __name__ == '__main__':
    main()
