import asyncio


class LevelSensor:
    # Positions
    HIGH = "HIGH"
    LOW = "LOW"

    def __init__(self, name, control_pin, sensor_type, position, gpio_controller):
        self.name = name
        self.sensor_type = sensor_type
        self.position = position
        self._pin = control_pin
        self._gpio_controller = gpio_controller

        # init gpio_pins
        self._gpio_controller.setup(self._pin, self._gpio_controller.IN)

        # add a thread for event detection
        self._gpio_controller.add_event_detect(
            self._pin, self._gpio_controller.BOTH, bouncetime=200
        )

    def add_callback(self, callback_function):
        """
        add callback function that fires every time the sensor is triggered
        the callback function gets modified to add the information if it encounters an alert or revoke
        :param callback_function: the function that gets fired
        :return:
        """
        loop = asyncio.get_event_loop()

        def extra_callback_function(pin):
            new_value = self._gpio_controller.input(self._pin)
            alert = (
                self.position == self.HIGH and new_value == self._gpio_controller.HIGH
            ) or (self.position == self.LOW and new_value == self._gpio_controller.HIGH)

            loop.create_task(callback_function(pin, alert))

        self._gpio_controller.add_event_callback(
            self._pin, extra_callback_function)

    def clear_callbacks(self):
        """
        remove all callback functions and start with a clean state
        :return:
        """
        self._gpio_controller.remove_event_detect(self._pin)
        self._gpio_controller.add_event_detect(
            self._pin, self._gpio_controller.BOTH, bouncetime=200
        )
