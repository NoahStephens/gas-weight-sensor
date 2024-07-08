import time
import threading
from fastapi import FastAPI, BackgroundTasks
import uvicorn
from hx711 import HX711
import RPi.GPIO as GPIO
from pydantic import BaseModel
from datetime import datetime, timedelta
import sqlite3
import os 
import pickle
import queue
import calendar

from config import APP_NAME
from config import WELDER_TYPE

from config import SDA_PIN
from config import SCL_PIN
from config import LED_PIN

from config import AVG_FILTER_N

class DBWorker(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self._db = sqlite3.connect("{}.{}.db".format(APP_NAME, WELDER_TYPE.name))
        self._queue = queue.Queue()

    def enqueue(self, sql, sql_params=None):
        self._queue.put((sql, sql_params), False)

    def run(self):
        while 1:
            (sql, sql_params) = self._queue.get(block=True)
            cur = self._db.cursor()
            
            if sql_params:
                cur.execute(sql, sql_params)
            else:
                cur.execute(sql)

            cur.execute(sql)
            self._db.commit()
            cur.close()


class HX711Device(object):
    def __init__(self, init_hx: HX711 | None = None):
        GPIO.setmode(GPIO.BCM)
        self._hx = HX711(SDA_PIN, SCL_PIN) if init_hx is None else init_hx
        self._hx_config_save_file_name = "hx711.obj.config"
        self._tare = 0

    def calibrate(self, calibration_weight: float):
        """ Takes measurement of known weight and set the devices reading to calibration ratio. Also saves the ratio and zero to disk."""
        uncalibrated_weight = self._hx.get_raw_data()
        if uncalibrated_weight:
            print('Mean value from HX711 subtracted by offset:', uncalibrated_weight)

            # set scale ratio for particular channel and gain which is
            # used to calculate the conversion to units. Required argument is only
            # scale ratio. Without arguments 'channel' and 'gain_A' it sets
            # the ratio for current channel and gain.
            ratio = uncalibrated_weight / calibration_weight  # calculate the ratio for channel A and gain 128
            self._hx.set_scale_ratio(ratio)  # set ratio for current channel
            print('Ratio is set at {}.'.format(ratio))
        else:
            raise ValueError(
                'Cannot calculate mean value. Try debug mode. Variable reading:',
                uncalibrated_weight)
        
        reading = self._hx.get_raw_data_mean()
        if reading:  # always check if you get correct value or only False
                # now the value is close to 0
            print('Data subtracted by offset (should be 0):',
                reading)
        else:
            print('invalid data', reading)
        GPIO.cleanup()

        return {"calibration-weight": calibration_weight, "uncalibrated-weight": uncalibrated_weight, "calibrated-weight": reading, "ratio": ratio}
    
    def get_doctored_data(self, times: int):
        return self._hx.get_raw_data(times) - self._tare
        
    def tare(self):
        # measure tare and save the value as offset for current channel
            # and gain selected. That means channel A and gain 128
        reading = self._hx.get_raw_data()
        self._tare = reading
        if reading:  # always check if you get correct value or only False
                # now the value is close to 0
            print('Tared weight (should be 0):',
                reading)
        else:
            print('invalid data', reading)

        GPIO.cleanup()

        return {"tared-weight": reading}
    
    def save_to_disk(self):
        # This is how you can save the ratio and offset in order to load it later.
        # If Raspberry Pi unexpectedly powers down, load the settings.
        print('Saving the HX711 state to swap file on persistent memory as {}'.format(self._hx_config_save_file_name))
        with open(self._hx_config_save_file_name, 'wb') as file:
            pickle.dump(self._hx, file)
            file.flush()
            os.fsync(file.fileno())
            # you have to flush, fsynch and close the file all the time.
            # This will write the file to the drive. It is slow but safe.
    
    def __enter__(self):
        return self._hx
    
    def __exit__(self):
        GPIO.cleanup()

    @property
    def tare_value(self):
        return self._tare

class SensorWorker(threading.Thread):
    def __init__(self, *args, **kwargs):
        threading.Thread.__init__(self)
        self._db = DBWorker()
        self._db.start()
        self._hx_device = HX711Device()

    def get_data(self):
        try:
            with self._hx_device as hx:
                reading = hx.get_weight_mean(AVG_FILTER_N)
                print("Reading {}".format(reading), 'g')
                return reading

        except Exception as e:
            return e
    
    def run(self,*args,**kwargs):
        while True:
            self._db.enqueue("INSERT INTO Weights VALUES (?, ?)", (time.time_ns(), self.get_data))

    @property
    def hx_device(self):
        return self._hx_device
    
app = FastAPI()
sensor = SensorWorker()

@app.get("/{}".format(WELDER_TYPE.name))
async def get_data():
    try:
        reading = sensor.get_data()
        return {"weight": reading}
    
    except Exception as e:
        return {"Exception": e}

class Filter(BaseModel):
    timestart : datetime
    timeend: datetime

@app.post("/{}".format(WELDER_TYPE.name))
async def get_data_range(filter: Filter):
    time_start = calendar.timegm(filter.timestart.utctimetuple())
    time_end = calendar.timegm(filter.timeend.utctimetuple())
    con = sqlite3.connect("{}.{}.db".format(APP_NAME, WELDER_TYPE.name))
    cur = con.cursor()
    cur.execute("SELECT * FROM Weights WHERE CreatedDate >= {} AND CreatedData <= {}".format(time_start, time_end))
    
    return {"weights": cur.fetchall()}    

@app.get("/{}/tare".format(WELDER_TYPE.name))
async def get_tare():
    return {"tared-weight": sensor.hx_device.tare_value}

@app.put("/{}/tare".format(WELDER_TYPE.name))
async def put_tare():
    try:
        response = sensor.hx_device.tare()
        return response
    except Exception as e:
        return {"Exception": e}
    

if __name__ == "__main__":
    sensor.start()
    uvicorn.run(app, host="0.0.0.0", port=8000)