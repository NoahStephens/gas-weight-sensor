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
from config import DEBUG

from config import REFERENCE_UNIT
from config import MEDIAN_VALUE_N

class DBWorker(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self._db = sqlite3.connect("{}-{}-db".format(APP_NAME, WELDER_TYPE.name))
        self._queue = queue.Queue()

        # first creates a table if not exists
        self.enqueue("CREATE TABLE IF NOT EXISTS Weights (Id INTEGER PRIMARY KEY AUTOINCREMENT, CreatedDate INTEGER, Data INTEGER)")

    def enqueue(self, sql, sql_params=tuple | None, cb=None):
        self._queue.put((sql, sql_params, cb), False)

    def run(self):
        while 1:
            (sql, sql_params, cb) = self._queue.get(block=True)

            try:
                cur = self._db.cursor()
                
                if sql_params:
                    cur.execute(sql, sql_params)
                else:
                    cur.execute(sql)

                if cb: 
                    cb(cur.fetchall())

                self._db.commit()
            except Exception as e:
                raise e
            
            finally:
                cur.close()


class HX711Device(object):
    def __init__(self, init_hx: hx711.HX711 | None = None):
        # self._device = hx711.HX711(dout=DATA_PIN, pd_sck=CLOCK_PIN, gain=128) if init_hx is None else init_hx
        self._device = hx711.HX711(DATA_PIN, CLOCK_PIN)
        self._device.set_reading_format("MSB", "MSB")
        self._device.set_reference_unit(REFERENCE_UNIT)
        self._hx_config_save_file_name = "hx711.obj.config"
        GPIO.setup(LED_PIN, GPIO.OUT) # setup LED pin for reading
        self._tared_value = 0
        self._calibration_value = 0

        if DEBUG:
            print("sensor_device_init: reference_unit: {} tared_value: {} calibration_value: {} raw_reading: {} ".format(REFERENCE_UNIT, self._tared_value, self._calibration_value, self.get_weight()))

        # check if device object backup exists
        self.restore_from_disk()

    def reset(self):
        self._device.reset()
        return {"reset":"successful"}

    def calibrate(self, known_weight):
        """ calibration routine to give the scale a unit to use and to scale the value accordingly. Make sure to tare the scale first to get an accurate weight. Place the object of known weight on the scale first before calling. """
        reading = self.get_weight()
        self._calibration_value = reading / known_weight
        self._device.set_reference_unit(self._calibration_value)
        if DEBUG: 
            print("calibration: known_weight: {} reading: {} reference_unit (reading/known_weight): {} ".format(known_weight, reading, self._calibration_value))
        return {"reference_unit": self._calibration_value}

    def tare(self, value=None):
        # measure tare and save the value as offset for current channel
            # and gain selected. That means channel A and gain 128
        if value:
            self._device.set_offset(value)
        else:
            self._tared_value = self._device.tare()
        if DEBUG:
            print("tare: new offset is {}".format(self._tared_value))
    
    def save_to_disk(self):
        # This is how you can save the ratio and offset in order to load it later.
        # If Raspberry Pi unexpectedly powers down, load the settings.
        if DEBUG:
            print('disk: saving ... ({}, {}, {}) to disk as {}'.format(self._device.get_gain(), self._device.get_offset(), self._device.get_reference_unit(), self._hx_config_save_file_name))
        
        with open(self._hx_config_save_file_name, 'wb') as file:
            device_config = (self._device.get_gain(), self._device.get_offset(), self._device.get_reference_unit())
            pickle.dump(device_config, file)
            file.flush()
            os.fsync(file.fileno())
            # you have to flush, fsynch and close the file all the time.
            # This will write the file to the drive. It is slow but safe.

    def restore_from_disk(self):
        """ restores gain, offset, and reference unit from disk. used for tare."""
        if os.path.isfile(self._hx_config_save_file_name):
            with open(self._hx_config_save_file_name, 'rb') as swap_file:
                (_gain, _offset, _reference_unit) = pickle.load(swap_file) # load the device from disk if it does
                self._device.set_gain(_gain)
                self._device.set_offset(_offset)
                self._device.set_reference_unit(_reference_unit)
                if DEBUG:
                    print('disk: restoring disk from {} ... ({}, {}, {})'.format(self._hx_config_save_file_name, self._device.get_gain(), self._device.get_offset(), self._device.get_reference_unit()))

        else:
            self.save_to_disk()

    def get_weight(self):
        return self._device.get_weight(MEDIAN_VALUE_N)
    
    def __enter__(self):
        return self._device
    
    def __exit__(self, *args, **kwagrs):
        return
        GPIO.cleanup()

    @property
    def tare_value(self):
        return {"tared-weight": self._tared_value}

class SensorWorker(threading.Thread):
    def __init__(self, db, *args, **kwargs):
        threading.Thread.__init__(self)
        # self._db = db
        # self._db.start()
        self._hx_device = HX711Device()
    
    def run(self,*args,**kwargs):
        while True:
            time.sleep(SENSOR_POLLING_RATE)
            data = self._hx_device.get_weight()
            # self._db.enqueue("INSERT INTO Weights VALUES (NULL, ?, ?)", (time.time_ns(), data, ))
            if DEBUG:
                print("sensor_poll(@{}): {}".format(SENSOR_POLLING_RATE, data))

    @property
    def hx_device(self):
        return self._hx_device
    
app = FastAPI()
db = DBWorker()
sensor = SensorWorker(db)

@app.get("/")
async def get_data():
    try:
        reading = sensor.hx_device.get_weight()
        return {"weight": reading}
    
    except Exception as e:
        return {"Exception": e}

class Filter(BaseModel):
    timestart : datetime
    timeend: datetime

class Calibrate(BaseModel):
    known_weight : float

class Tare(BaseModel):
    tare_value : float

@app.post("/")
async def get_data_range(filter: Filter):
    return {"weights": "this function is not implemented"}
    data = None

    def set_data(_data):
        data = _data

    time_start = calendar.timegm(filter.timestart.utctimetuple())
    time_end = calendar.timegm(filter.timeend.utctimetuple())

    # db.enqueue("SELECT * FROM Weights WHERE CreatedDate >= {} AND CreatedData <= {}".format(time_start, time_end), None, set_data)

    return {"weights": data}    

@app.get("/tare")
async def get_tare():
    try:
        return sensor.hx_device.tare_value
    except Exception as e:
        return {"Exception": e}
    
@app.put("/tare")
async def put_tare():
    try:
        sensor.hx_device.tare()
        return sensor.hx_device.tare_value
    except Exception as e:
        return {"Exception": e}
    
@app.patch("/tare")
async def patch_tare(tar:Tare):
    try:
        sensor.hx_device.tare(tar.tare_value)
        return {"tare": tar.tare_value}
    except Exception as e:
        return {"Exception": e}
    
@app.get("/save")
async def put_save():
    try:
        sensor.hx_device.save_to_disk()
        return {"save_to_disk": "successful"}
    except Exception as e:
        return {"save_to_disk": "error", "Exception": e}
    
@app.get("/restore")
async def get_restore():
    try:
        sensor.hx_device.restore_from_disk()
        return {"restore_from_disk": "successful"}
    except Exception as e:
        return {"restore_from_disk": "error", "Exception": e}
    
@app.get("/calibrate")
async def get_calibrate():
    try:
        return {"calibrate" :sensor.hx_device.calibration_value}
    except Exception as e:
        return {"calibrate": "error", "Exception": e}
    
@app.put("/calibrate")
async def get_calibrate(cal:Calibrate):
    try:
        sensor.hx_device.calibrate(cal.known_weight)
        return {"calibrate" :sensor.hx_device.calibration_value}
    except Exception as e:
        return {"calibrate": "error", "Exception": e}
    
@app.get("/reset")
async def get_reset():
    try:
        return sensor.hx_device.reset()
    except Exception as e:
        return {"reset": "error", "Exception": e}

if __name__ == "__main__":
    sensor.start()
    uvicorn.run(app, host="0.0.0.0", port=8000)