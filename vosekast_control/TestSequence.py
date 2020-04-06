import logging
import asyncio
import random
from vosekast_control.Log import LOGGER
import time
from vosekast_control.connectors import DBConnection
from vosekast_control.utils.Constants import (
    MEASURING_TANK,
    MEASURING_DRAIN_VALVE,
    PUMP_CONSTANT_TANK,
    PUMP_MEASURING_TANK,
    MEASURING_TANK_SWITCH,
    CONSTANT_TANK,
)


class TestSequence:
    # TestSequence states
    UNKNOWN = "UNKNOWN"
    WAITING = "WAITING"
    MEASURING = "MEASURING"
    PAUSED = "PAUSED"
    STOPPED = "STOPPED"

    def __init__(
        self, vosekast, emulate=False,
    ):

        super().__init__()
        self.logger = logging.getLogger(LOGGER)
        self.vosekast = vosekast
        self.valves = self.vosekast.valves
        self.tank = self.vosekast.tanks
        self.pumps = self.vosekast.pumps
        self.scale = self.vosekast.scale
        self.emulate = emulate
        self.state = self.UNKNOWN
        self.scale_value_start = []
        self.scale_value_stop = []

    async def start_sequence(self):
        if not self.state == self.WAITING and not self.state == self.MEASURING:
            try:
                self.logger.info("Initialising sequence.")

                # change state
                self.state = self.WAITING

                # check if already running
                if not self.scale.is_running:
                    self.scale.start()
                    self.logger.info(
                        "Initialising scale connection & measurement thread. Please wait."
                    )
                    await asyncio.sleep(1)
                else:
                    self.logger.debug("Scale running, continuing.")

                # only fill if not already full
                if (
                    not self.vosekast.tanks[CONSTANT_TANK].state
                    == self.vosekast.tanks[CONSTANT_TANK].FILLED
                ):
                    self.vosekast.tanks[CONSTANT_TANK].state = self.vosekast.tanks[
                        CONSTANT_TANK
                    ].IS_FILLING
                    # await constant_tank full
                    await self.vosekast.tanks[CONSTANT_TANK].fill()
                else:
                    self.vosekast.prepare_measuring()

                # check ready_to_measure
                if not self.vosekast.ready_to_measure:
                    self.logger.debug("Vosekast not ready to measure.")
                    self.scale.print_diagnostics()
                    self.state = self.STOPPED
                    return

                # check if state has been changed
                elif self.state == self.STOPPED or self.state == self.PAUSED:
                    return

                self.logger.debug("Vosekast ready to measure.")
                # turn on measuring pump, start measuring
                await self.start_measuring()

                self.vosekast.state = self.vosekast.MEASURING
                self.state = self.MEASURING

                # write to file
                await self.write_loop()

            # TankFillingTimeout
            except Exception:
                self.logger.error("Error, aborting test sequence.")

                await self.stop_sequence()
                self.vosekast.tanks[CONSTANT_TANK].state = self.vosekast.tanks[
                    CONSTANT_TANK
                ].STOPPED
                self.vosekast.state = self.vosekast.RUNNING
        else:
            self.logger.info("Already measuring.")

    async def write_loop(self):
        try:
            # get start time
            time_sequence_t0 = time.time()
            delta_time_sequence = 0

            # tare scale
            if abs(self.scale.scale_history[0]) < 0.15:
                scale_nulled = self.scale.scale_history[0]
            else:
                scale_nulled = 0

            # generate sequence_id
            sequence_id = random.randint(10000000000, 100000000000)

            # send values to db
            while (
                self.state == self.MEASURING
                and not self.vosekast.tanks[MEASURING_TANK].is_filled
            ):
                # get flow average
                flow_average = self.scale.flow_average()

                # emulate measuring_tank filled
                if self.emulate and delta_time_sequence >= 30:
                    self.vosekast.tanks[MEASURING_TANK].state = self.vosekast.tanks[
                        MEASURING_TANK
                    ].FILLED
                if self.emulate:
                    # timeout
                    time_sequence_t1 = time.time()
                    delta_time_sequence = time_sequence_t1 - time_sequence_t0

                    scale_actual = round(self.scale.scale_history[0], 5)
                # if not emulate use scale value
                else:
                    scale_actual = round(self.scale.scale_history[0] - scale_nulled, 5)

                try:
                    data = {
                        "timestamp": self.scale.scale_history[1],
                        "scale_value": scale_actual,
                        "flow_current": self.scale.flow_history[0],
                        "flow_average": flow_average,
                        "pump_constant_tank_state": self.vosekast.pumps[
                            PUMP_CONSTANT_TANK
                        ].state,
                        "pump_measuring_tank_state": self.vosekast.pump_measuring_tank.state,
                        "measuring_drain_valve_state": self.vosekast.valves[
                            MEASURING_DRAIN_VALVE
                        ].state,
                        "measuring_tank_switch_state": self.vosekast.valves[
                            MEASURING_TANK_SWITCH
                        ].state,
                        "sequence_id": sequence_id,
                    }
                    DBConnection.insert_datapoint(data)

                except Exception as e:
                    self.logger.error("Error sending to db.")
                    self.logger.error(e)

                self.logger.debug(
                    str(scale_actual)
                    + " kg, flow rate (average) "
                    + str(flow_average)
                    + " L/s"
                )
                await asyncio.sleep(1)

            # interrupt if measuring_tank full
            if self.vosekast.tanks[MEASURING_TANK].is_filled:
                self.vosekast.valves[MEASURING_TANK_SWITCH].close()
                self.vosekast.tanks[MEASURING_TANK].drain_tank()
                self.state = self.STOPPED
                self.logger.debug(
                    "Draining measuring tank, opening Measuring Tank bypass."
                )

        except Exception:
            self.logger.warning("Write loop killed, stopping sequence.")
            await self.stop_sequence()

    async def start_measuring(self):
        try:
            self.vosekast.tanks[MEASURING_TANK].prepare_to_fill()
            self.vosekast.valves[MEASURING_TANK_SWITCH].close()
            self.vosekast.pumps[PUMP_MEASURING_TANK].start()
            self.logger.debug("Measuring Pump spin up. Please wait.")

            await asyncio.sleep(2)

            self.vosekast.valves[MEASURING_TANK_SWITCH].open()
            self.logger.debug("Measuring started.")

        except Exception:
            self.logger.debug("Measuring aborted.")
            self.vosekast.pumps[PUMP_MEASURING_TANK].stop()
            self.vosekast.state = self.vosekast.RUNNING

    async def stop_sequence(self):
        if (
            self.state == self.MEASURING
            or self.state == self.PAUSED
            or self.state == self.WAITING
        ):
            self.state = self.STOPPED
            self.vosekast.valves[MEASURING_TANK_SWITCH].close()
            self.logger.debug("Stopped test sequence")
            self.vosekast.state = self.vosekast.RUNNING

            self.vosekast.clean()
        else:
            self.logger.info("Sequence has not yet been started.")

    def pause_sequence(self):
        if self.state == self.MEASURING:
            self.state = self.PAUSED

            # set fill countdown to False
            self.vosekast.tanks[CONSTANT_TANK].state = self.vosekast.tanks[
                CONSTANT_TANK
            ].PAUSED

            # switch to measuring_tank bypass
            self.vosekast.valves[MEASURING_TANK_SWITCH].close()

            self.logger.info("Paused. Measuring Tank bypass open.")

        # if constant_tank has not been filled yet
        elif self.state == self.WAITING and self.vosekast.PREPARING_MEASUREMENT:
            self.state = self.STOPPED
            self.vosekast.state = self.vosekast.RUNNING
            self.logger.info(
                "Measuring has not yet started, continuing to fill constant_tank."
            )
        elif self.state == self.PAUSED or self.state == self.STOPPED:
            self.logger.info("Sequence already paused.")
        else:
            self.logger.info("Sequence has not yet been started.")

    async def continue_sequence(self):
        if self.state == self.PAUSED:
            self.state = self.MEASURING

            # set fill countdown to True
            self.vosekast.tanks[CONSTANT_TANK].state = self.vosekast.tanks[
                CONSTANT_TANK
            ].IS_FILLING

            self.vosekast.valves[MEASURING_TANK_SWITCH].open()
            self.logger.info("Continuing. Measuring Tank is being filled.")
            await self.write_loop()
        elif self.state == self.WAITING or self.state == self.MEASURING:
            self.logger.info("Sequence has not been paused.")
        else:
            self.logger.info("Sequence has not yet been started.")
