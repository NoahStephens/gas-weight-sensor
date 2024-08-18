from enum import Enum

# prints vals out to terminal
DEBUG = 1

class Welder(Enum):
    MIG = 0,
    TIG = 1

WELDER_TYPE = Welder.MIG

APP_NAME = "weight_tracker"

# Sensor polling rate in seconds. How many seconds the sensor worker takes a reading and writes it to the db
SENSOR_POLLING_RATE = 2

''' RASPBERRY PI ZERO W 1.1 PIN DEFINITIONS'''
# hx711 device pins
DATA_PIN = 5    # GPIO5
CLOCK_PIN = 6   # GPIO6

# led pin
LED_PIN = 25    # GPIO25

''' Program Specific Variables'''
REFERENCE_UNIT = 7455.333/311.845

# Do NOT make this value even there is a bug in the library code. only odd.
MEDIAN_VALUE_N = 13