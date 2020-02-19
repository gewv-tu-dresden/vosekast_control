import RPi.GPIO as GPIO
from time import sleep


# GPIO Assignment
PIN_PUMP_CONSTANT = 17
PIN_PUMP_MEASURING = 27
PIN_VALVE_MEASURING_SWITCH = 12
PIN_VALVE_MEASURING_DRAIN = 18
PIN_LEVEL_MEASURING_HIGH = 24
PIN_LEVEL_MEASURING_LOW = 25
PIN_LEVEL_CONSTANT_LOW = 5
PIN_LEVEL_CONSTANT_HIGH = 6

GPIO.setmode(GPIO.BCM)

GPIO.setup(6, GPIO.IN)

print("starting")        

while True:
    print(GPIO.input(6))
    print("sleep")
    sleep(1)

       