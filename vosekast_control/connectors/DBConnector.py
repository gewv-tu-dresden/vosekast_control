import sqlite3
from sqlite3 import Error
from datetime import datetime
import logging
from vosekast_control.Log import LOGGER


class DBConnector():

    def __init__(self):
        self._db_connection = None
        self.logger = logging.getLogger(LOGGER)

    # cursor unnecessary according to https://docs.python.org/3/library/sqlite3.html#using-shortcut-methods
    def connect(self):
        try:
            self._db_connection = sqlite3.connect('sequence_values.db')
            self.logger.info("Established DB connection.")
        except Error as e:
            self.logger.warning(e)
        except:
            self.logger.info("Failed to establish DB connection.")

        self._db_connection.execute("""CREATE TABLE IF NOT EXISTS sequence_values (
            timestamp real,
            scale_value real,
            flow_current real,
            flow_average real,
            pump_constant_tank_state real,
            pump_measuring_tank_state real,
            measuring_drain_valve_state integer,
            measuring_tank_switch_state integer,
            sequence_id real
            )""")
        self._db_connection.commit()
        self.logger.info("DB created.")

    def insert_datapoint(self, data):
        try:
            # values = {
            #     'timestamp': 0000,
            #     'scale_actual': 0000,
            #     'flow_current': 0000,
            #     'flow_average': 0000}

            # https://stackoverflow.com/questions/14108162/python-sqlite3-insert-into-table-valuedictionary-goes-here/16698310
            self._db_connection.execute(
                "INSERT INTO sequence_values (timestamp,scale_value,flow_current,flow_average,pump_constant_tank_state,pump_measuring_tank_state,measuring_drain_valve_state,measuring_tank_switch_state,sequence_id) VALUES (:timestamp, :scale_value, :flow_current, :flow_average, :pump_constant_tank_state, :pump_measuring_tank_state, :measuring_drain_valve_state, :measuring_tank_switch_state, :sequence_id);", data)

            self._db_connection.commit()

        except Error as e:
            self.logger.error(e)
        except ProgrammingError as e:
            self.logger.error(e)

    # todo
    def read(self):
        pass

    # (todo) find while loop that does not sleep
    # probably fixed, needs testing

    def close(self):
        try:
            self._db_connection.close()
            self.logger.info("DB connection closed.")
        except:
            return

    # workaround to show if connected
    # https://stackoverflow.com/questions/1981392/how-to-tell-if-python-sqlite-database-connection-or-cursor-is-closed
    # https://dba.stackexchange.com/questions/223267/in-sqlite-how-to-check-the-table-is-empty-or-not
    @property
    def isConnected(self):
        try:
            # should return 0 if empty
            self._db_connection.execute(
                "SELECT count(*) FROM (select 0 from sequence_values limit 1);")
            return True
        except Error as e:
            self.logger.warning(e)
            return False
        except:
            return False


DBConnection = DBConnector()
