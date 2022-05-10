#!/usr/bin/env python3
#from _typeshed import Self
import time
import platform

from ant.core import driver
from ant.core import node

from usb.core import find

from PowerMeterTx import PowerMeterTx
from SpeedCadenceSensorRx import SpeedCadenceSensorRx
from config import DEBUG, LOG, NETKEY, POWER_CALCULATOR, POWER_SENSOR_ID, SENSOR_TYPE, SPEED_SENSOR_ID

class PowerSensor:

    def StopDevice(self):
        if self.speed_sensor:
            print("Closing speed sensor")
            self.speed_sensor.close()
            self.speed_sensor.unassign()
        if self.power_meter:
            print("Closing power meter")
            self.power_meter.close()
            self.power_meter.unassign()
        if self.antnode:
            print("Stopping ANT node")
            self.antnode.stop()

    def __init__(self):
        self.antnode = None
        self.speed_sensor = None
        self.power_meter = None
        self.pywin32 = False
        if platform.system() == 'Windows':
            def on_exit(sig, func=None):
                stop_ant()
            try:
                import win32api
                win32api.SetConsoleCtrlHandler(on_exit, True)
                pywin32 = True
            except ImportError:
                print("Warning: pywin32 is not installed, use Ctrl+C to stop")

        try:
            print("Using " + POWER_CALCULATOR.__class__.__name__)

            devs = find(find_all=True, idVendor=0x0fcf)
            for dev in devs:
                if dev.idProduct in [0x1008, 0x1009]:
                    # If running on the same PC as the receiver app (with two identical sticks)
                    # the first stick may be already claimed, so continue trying
                    stick = driver.USB2Driver(log=LOG, debug=DEBUG, idProduct=dev.idProduct, bus=dev.bus, address=dev.address)
                    try:
                        stick.open()
                    except:
                        continue
                    stick.close()
                    break
            else:
                print("Error. No ANT devices available")
                exit()

            self.antnode = node.Node(stick)
            print("Starting ANT node")
            self.antnode.start()
            key = node.Network(NETKEY, 'N:ANT+')
            self.antnode.setNetworkKey(0, key)

            print("Starting speed sensor")
            try:
                # Create the speed sensor object and open it
                self.speed_sensor = SpeedCadenceSensorRx(self.antnode, SENSOR_TYPE, SPEED_SENSOR_ID & 0xffff)
                self.speed_sensor.open()
                # Notify the power calculator every time we get a speed event
                self.speed_sensor.notify_change(POWER_CALCULATOR)
            except Exception as e:
                print("speed_sensor error: " + repr(e))
                self.speed_sensor = None

            print("Starting power meter with ANT+ ID " + repr(POWER_SENSOR_ID))
            try:
                # Create the power meter object and open it
                self.power_meter = PowerMeterTx(self.antnode, POWER_SENSOR_ID)
                self.power_meter.open()
            except Exception as e:
                print("power_meter error: " + repr(e))
                self.power_meter = None

            # Notify the power meter every time we get a calculated power value
            POWER_CALCULATOR.notify_change(self.power_meter)

            self.stopped = True
            self.last_time = 0
            self.last_update = 0
            print("Configuration done.")
        
        except Exception as e:
            print("Exception: " + repr(e))
    
    def GetReading(self):
        try:
            # Some apps keep the last received power value if the sensor stops broadcasting
            # and some drop the power to zero if the interval between updates is > 1 second
            if not self.stopped:
                t = int(time.time())
                if t >= self.last_update + 3:
                    if self.speed_sensor.currentData.speedEventTime == self.last_time:
                        # Set power to zero if speed sensor doesn't update for 3 seconds
                        self.power_meter.powerData.instantaneousPower = 0
                        self.stopped = True
                    self.last_time = self.speed_sensor.currentData.speedEventTime
                    self.last_update = t
                # Force an update every second to avoid power drops
                self.power_meter.update(self.power_meter.powerData.instantaneousPower)
            elif self.power_meter.powerData.instantaneousPower:
                self.stopped = False
        except (KeyboardInterrupt, SystemExit):
            print("Error. Could not read data from ANT+ sensor")

    def StopSensor(self):
        self.StopDevice()
