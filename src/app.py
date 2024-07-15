import time
import threading
from fastapi import FastAPI, BackgroundTasks
import uvicorn
import RPi.GPIO as GPIO
from pydantic import BaseModel
from datetime import datetime, timedelta
import sqlite3
import os 
import pickle
import queue
import calendar

from lib.hx711py import hx711

from config import APP_NAME
from config import WELDER_TYPE

from config import SENSOR_POLLING_RATE
from config import DATA_PIN
from config import CLOCK_PIN
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
    def __init__(self, init_hx: hx711.HX711 | None = None):
        self._device = hx711.HX711(dout=DATA_PIN, pd_sck=CLOCK_PIN, gain=128) if init_hx is None else init_hx
        self._device.set_reading_format("MSB", "MSB")
        self._hx_config_save_file_name = "hx711.obj.config"
        GPIO.setup(LED_PIN, GPIO.OUT) # setup LED pin for reading

        # check if device object backup exists
        if os.path.isfile(self._hx_config_save_file_name):
            with open(self._hx_config_save_file_name, 'rb') as swap_file:
                self._device = pickle.load(swap_file) # load the device from disk if it does
        else:
            self.save_to_disk() # save to disk in the event of a power failure before taring.

        # tare on device instance. The user may also need to tare later...
        self._tared_value = self.tare()
        
    def tare(self):
        # measure tare and save the value as offset for current channel
            # and gain selected. That means channel A and gain 128
        reading = self._hx.tare()
        self._tared_value = reading
        if reading:  # always check if you get correct value or only False
                # now the value is close to 0
            print('Tared weight (should be 0):',
                reading)
        else:
            print('invalid data', reading)

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

    def get_weight(self):
        GPIO.output(LED_PIN, GPIO.HIGH)
        time.sleep(1)
        GPIO.output(LED_PIN, GPIO.LOW)
        return self._device.get_weight()
    
    def get_formatted_weight(self):
        return {"weight": self._device.get_weight()}
    
    def __enter__(self):
        return self._hx
    
    def __exit__(self):
        GPIO.cleanup()

    @property
    def tare_value(self):
        return {"tared-weight": self._tared_value}

class SensorWorker(threading.Thread):
    def __init__(self, *args, **kwargs):
        threading.Thread.__init__(self)
        self._db = DBWorker()
        self._db.start()
        self._hx_device = HX711Device()

    def get_data(self):
        try:
            with self._hx_device as hx:
                return hx.get_weight()

        except Exception as e:
            raise e
    
    def run(self,*args,**kwargs):
        while True:
            time.sleep(SENSOR_POLLING_RATE)
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
    return sensor.hx_device.tare_value

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