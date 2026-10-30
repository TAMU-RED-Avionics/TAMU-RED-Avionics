# MASTER FILE; RUN THIS TO START VIRTUAL TEENSY

# import communication scripts from other file
import serial
import time
import random

time_start = time.time_ns()
time.sleep(0.1)
ser = serial.Serial("COM98", baudrate=115200, timeout=1, write_timeout=5)
while 1:
    try:
        output = ""
        output += str(time.time_ns()*1000 - time_start)[:-6] + ','
        output += str(30 + random.random()) + ','
        output += str(20 + 2*random.random()) + "\r\n"

        #print(output.encode())
        ser.write(output.encode())
    except:
        print("Writing Timed out")
    #time.sleep(0.01)
