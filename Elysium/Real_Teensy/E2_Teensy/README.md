# How to connect

## Windows:
In an elevated command prompt
Look for an interface that appears when you plug in the teensy
`netsh interface show interface` 

Use the interface name (ex: Ethernet 5) in the command below
`netsh interface ip set address name="{INTERFACE NAME}" static 192.168.1.175 255.255.255.0`

## Mac/Linux:
In terminal
Find the network interface name by running
`ifconfig` (Look for an interface like en0, eth0, or enp0s3 that activates only when the cable is connected)

Use the interface name (ex: eth0) in the command below
`sudo ifconfig {INTERFACE_NAME} inet 192.168.1.175 netmask 255.255.255.0 up`

-----
Upload code to Teensy from Arduino IDE if not already done

Open GUI and connect to IP: `192.168.1.174` PORT: `8888`

-----
Note: As noted in the teensy code, there is a HUMAN_CONNECTION_TIMEOUT variable. This means that if there is no human action (valve actuation) in that amount of time, the teensy will shut down and it will not reconnect unless you reopen the GUI. In E1 it was set as 5 minutes and it was a pain. With that being said, it could be an important safety feature. I have it set to 1 hour (3600000000 microsec). In theory, this should NEVER trigger (which makes it kinda useless).