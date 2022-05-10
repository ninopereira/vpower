from vpower import *
import time 

powerSensor = PowerSensor()
time.sleep(1)

while(True):
    powerSensor.GetReading()
    time.sleep(1)
