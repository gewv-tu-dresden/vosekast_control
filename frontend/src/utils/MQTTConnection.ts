import mqtt from "mqtt";
import {
  MQTTStore,
  VosekastStore,
  PumpState,
  ValveState,
  TankState,
} from "../Store";
import { message } from "antd";
import moment from "moment";
// @ts-ignore
import { TimeSeries, TimeEvent } from "pondjs";

type MessageTypes = "status" | "log" | "message" | "command" | "info" | "data";
type Targets = "system" | "pump" | "valve";
type InfoSystems = "testrun_controller";
type DataSources = "test_results";

interface Message {
  type: MessageTypes;
  time?: string;
}

interface CommandMessage extends Message {
  type: "command";
  target: Targets;
  target_id: string;
  command: string;
}

interface StatusMessage extends Message {
  type: "status";
  device_type: "scale" | "system" | "pump" | "valve" | "tank";
  device_id: string;
  new_state: string;
  run_id?: string;
}

interface LogMessage extends Message {
  type: "log";
  sensor_id: "Pump" | "Valve";
  message: string;
  level: "INFO" | "DEBUG" | "WARNING" | "ERROR";
}

interface InfoMessage extends Message {
  type: "info";
  system: InfoSystems;
  payload: {
    id: string;
    startedAt: number;
    createdAt: number;
    state: string;
    emulated: boolean;
  };
}
interface Datapoint {
  timestamp: number;
  scale_value: number;
  flow_current: number;
  flow_average: number;
  pump_constant_tank_state: string;
  pump_measuring_tank_state: string;
  measuring_drain_valve_state: string;
  measuring_tank_switch_state: string;
  run_id: string;
}

interface DataMessage extends Message {
  type: "data";
  data_type?: "test_result" | "test_results";
  id?: DataSources;
  payload?: Array<Datapoint> | Datapoint;
}

interface PumpStatusMessage extends StatusMessage {
  new_state: PumpState;
}

interface ValveStatusMessage extends StatusMessage {
  new_state: ValveState;
}

interface TankStatusMessage extends StatusMessage {
  new_state: TankState;
}

class MQTTConnector {
  client?: mqtt.MqttClient;
  private connectionOptions: mqtt.IClientOptions = {};
  private host: string = "";

  constructor(url: string, username?: string, password?: string) {
    if (username != null) this.connectionOptions.username = username;
    if (password != null) this.connectionOptions.password = password;
    this.host = url;
  }

  connect = () => {
    this.client = mqtt.connect(this.host, this.connectionOptions);

    this.client.on("connect", this.handleConnect);
    this.client.on("message", this.handleMessage);
    this.client.on("close", this.handleDissconnect);
    this.client.on("error", this.handleError);
    this.client.on("offline", this.handleOffline);
  };

  publishCommand = (target: Targets, targetId: string, command: string) => {
    this.publishMessage("vosekast/commands", {
      type: "command",
      target,
      target_id: targetId, // eslint-disable-line @typescript-eslint/camelcase
      command,
    });
  };

  publishMessage = (topic: string, messageObject: CommandMessage) => {
    this.client?.publish(topic, JSON.stringify(messageObject));
  };

  handleConnect = () => {
    if (this.client != null) {
      MQTTStore.update((s) => {
        s.isConnected = true;
        s.connectionError = undefined;
        s.mqttInterrupted = false;
      });

      this.client.subscribe("vosekast/#", { qos: 0 }, this.handleSubscription);

      // request state of devices and current testrun
      this.publishCommand("system", "vosekast", "state_overview");
      this.publishCommand(
        "system",
        "testrun_controller",
        "get_current_run_infos"
      );
    }
  };

  handleMessage = (
    topic: string,
    payload: Buffer | string,
    packet: mqtt.Packet
  ) => {
    const message: Message = JSON.parse(payload as string);

    switch (message.type) {
      case "status":
        this.handleStatusMessage(message as StatusMessage);
        break;
      case "log":
        this.handleLogMessage(message as LogMessage);
        break;
      case "info":
        this.handleInfoMessage(message as InfoMessage);
        break;
      case "data":
        this.handleDataMessage(message as DataMessage);
        break;
      case "message":
        break;
      case "command":
        break;
    }
  };

  handleSubscription = (err: Error, granted: mqtt.ISubscriptionGrant[]) => {
    if (err == null) {
      message.success("Connect to Vosekast Info Stream!");
      console.log("Subscribed to vosekast topics.");
    }
  };

  handleDissconnect = () => {
    MQTTStore.update((s) => {
      s.isConnected = false;
    });
  };

  handleError = (error: Error) => {
    MQTTStore.update((s) => {
      s.connectionError = error;
    });

    message.error("MQTT Connection Error");
    console.error(error.message);
  };

  handleOffline = () => {
    MQTTStore.update((s) => {
      s.mqttInterrupted = true;
    });

    message.warning("MQTT Connection Lost. Try to reconnect.");
  };

  handleStatusMessage = (message: StatusMessage) => {
    switch (message.device_type) {
      case "scale": {
        VosekastStore.update((s) => {
          s.scaleState.value = message.new_state;
        });
        break;
      }
      case "system": {
        if (message.device_id === "health" && message.new_state === "OK") {
          VosekastStore.update((s) => {
            s.isHealthy = message.new_state === "OK";
            s.lastHealthUpdate = moment();
          });
        }

        if (message.device_id === "testrun_controller") {
          VosekastStore.update((s) => {
            const runId = message.run_id;
            if (runId == null) return;
            const testrun = s.testruns.get(runId);
            if (testrun == null) return;

            s.testruns.set(runId, {
              state: message.new_state,
              ...testrun,
            });
          });
        }
        break;
      }
      case "pump": {
        const {
          device_id: pumpId,
          new_state: pumpState,
        } = message as PumpStatusMessage;
        VosekastStore.update((s) => {
          s.pumpStates.set(pumpId, pumpState);
        });
        break;
      }
      case "valve": {
        const {
          device_id: valveId,
          new_state: valveState,
        } = message as ValveStatusMessage;
        VosekastStore.update((s) => {
          s.valveStates.set(valveId, valveState);
        });
        break;
      }
      case "tank": {
        const {
          device_id: tankId,
          new_state: tankState,
        } = message as TankStatusMessage;
        VosekastStore.update((s) => {
          s.tankStates.set(tankId, tankState);
        });
        break;
      }
      default: {
        console.log(`Receive unknown message: ${JSON.stringify(message)}`);
      }
    }
  };

  handleInfoMessage = (message: InfoMessage) => {
    const runId = message.payload.id;

    VosekastStore.update((s) => {
      s.testruns.set(runId, message.payload);
    });
  };

  handleDataMessage = (message: DataMessage) => {
    const runId = message.id;
    const data = message.payload;
    const data_type = message.data_type;

    if (runId == null || data == null || data_type == null) {
      console.warn("Got data message with invalid format!");
      return;
    }

    switch (data_type) {
      case "test_results":
        VosekastStore.update((s) => {
          const datapoints = data as Array<Datapoint>;
          const testrun = s.testruns.get(runId);
          if (testrun == null) return;

          testrun.results = new TimeSeries({
            name: "sensor_data",
            columns: ["time", "sensor", "status"],
            points: data as any[],
          });
          s.testruns.set(runId, testrun);
        });
        break;

      case "test_result":
        VosekastStore.update((s) => {
          const datapoint = data as Datapoint;
          const testrun = s.testruns.get(runId);
          if (testrun == null) return;

          if (testrun.results == null) {
            testrun.results = new TimeSeries({
              name: "sensor_data",
              columns: ["time", "scale_value", "flow_value"],
              points: [
                [
                  Math.round(datapoint.timestamp),
                  datapoint.scale_value,
                  datapoint.flow_current,
                ],
              ],
            });
          } else {
            const collection = testrun.results.collection().addEvent(
              new TimeEvent(Math.round(datapoint.timestamp), {
                scale_value: datapoint.scale_value,
                flow_value: datapoint.flow_current,
              })
            );
            testrun.results = testrun.results.setCollection(collection, true);
          }

          s.testruns.set(runId, testrun);
        });
        break;
    }
  };

  handleLogMessage = (message: LogMessage) => {
    const combinedMessage = `${message.sensor_id}: ${message.message}`;

    switch (message.level) {
      case "DEBUG":
        console.debug(combinedMessage);
        break;
      case "ERROR":
        console.error(combinedMessage);
        break;
      case "INFO":
        console.info(combinedMessage);
        break;
      case "WARNING":
        console.warn(combinedMessage);
        break;
    }
  };
}

// export singleton for reusing of the connection
const MQTTConnection = new MQTTConnector("ws://localhost:8083/mqtt");
export default MQTTConnection;
