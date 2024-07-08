from enum import Enum

class Welder(Enum):
    MIG = 0,
    TIG = 1

WELDER_TYPE = Welder.MIG

APP_NAME = "weight_tracker"

''' RASPBERRY PI ZERO W 1.1 PIN DEFINITIONS'''
SCL_PIN = 5
SDA_PIN = 3
LED_PIN = 18 # GPIO25

AVG_FILTER_N = 10