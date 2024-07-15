from enum import Enum

class Welder(Enum):
    MIG = 0,
    TIG = 1

WELDER_TYPE = Welder.MIG

APP_NAME = "weight_tracker"

# Sensor polling rate in seconds. How many seconds the sensor worker takes a reading and writes it to the db
SENSOR_POLLING_RATE = 10

''' RASPBERRY PI ZERO W 1.1 PIN DEFINITIONS'''
# hx711 device pins
DATA_PIN = 5    # GPIO5
CLOCK_PIN = 6   # GPIO6

# led pin
LED_PIN = 25    # GPIO25

''' Program Specific Variables'''
AVG_FILTER_N = 10