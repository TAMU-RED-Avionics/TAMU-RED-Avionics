# Test File

import serial
import time

ser = serial.Serial("COM99", baudrate=9600, timeout=1)
count = 0
while 1:
    virtual_data = ser.readline()
    print(virtual_data)
