import json
from gmqtt import Client as MQTTClient
from vosekast_control.Log import LOGGER
from vosekast_control.utils.Msg import StatusMessage
import logging
import asyncio
import os


async def noop(*args, **kwargs):
    return None


HOST = os.getenv("MQTT_HOST", "localhost")


class MQTTConnector:
    def __init__(self, host):
        self.client = MQTTClient("Vosekast")
        self.host = host
        self.on_command = noop
        self.topic = "vosekast/commands"

        # set mqtt token
        # token = None

        # mqtt server credentials
        # if token != None:
        #     controller.set_credentials(username, password)

        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect
        self.client.on_subscribe = self.on_subscribe
        self.logger = logging.getLogger(LOGGER)
        self.tries = 0

    async def connect(self):
        self.tries += 1
        try:
            await self.client.connect(self.host)

        except OSError:
            self.logger.error("Failed to connect to MQTT broker. Seems no broker to exist.")
            raise

        except ConnectionRefusedError:
            await self.connection_refused()

    async def connection_refused(self):
        self.logger.warning(
            "Connection refused. Is the MQTT broker accessible? Retrying."
        )

        if self.tries <= 3:
            await self.connect()
        else:
            self.logger.warning("Connection refused 3 times. Aborting.")

    async def disconnect(self):
        await self.client.disconnect()

    @property
    def connected(self):
        return self.client.is_connected

    def publish(self, topic, message):
        if self.connection_test():
            self.client.publish(topic, message, qos=0)

    def publish_message(self, message_object):
        self.publish(message_object.topic, message_object.get_json())

    def on_connect(self, client, flags, rc, properties):
        self.client.subscribe(self.topic, qos=0)
        if self.connected:
            self.logger.debug('Connected to host: "' + self.host + '"')
            asyncio.create_task(self._start_healthy_loop())

    async def _start_healthy_loop(self):
        runs = 0

        while self.connected:
            try:
                if runs == 3:
                    msg = StatusMessage("system", "health", "OK")
                    self.publish_message(msg)
                    runs = 0

                runs += 1
                await asyncio.sleep(1)
            except asyncio.CancelledError:
                return

    async def on_message(self, client, topic, payload, qos, properties):
        message = payload

        try:
            command = json.loads(message)

            if command["type"] == "command":
                await self.on_command(command)

        except ValueError:
            self.logger.debug("unexpected formatting: " + str(payload.decode("utf-8")))
            self.logger.debug(ValueError)
        except KeyError:
            self.logger.debug("Got message without type.")

    def on_disconnect(self, client, packet, exc=None):
        self.logger.debug("MQTT Client Disconnected")

    def on_subscribe(self, client, mid, qos, properties):
        self.logger.debug('Vosekast listening on: "' + self.topic + '"')

    def set_credentials(self, username, password):
        self.client.set_auth_credentials(username, password)

    def connection_test(self):
        return self.client.is_connected


MQTTConnection = MQTTConnector(host=HOST)
