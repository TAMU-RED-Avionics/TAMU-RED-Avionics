/*
-------------------------------------------------------------------
Test Code for ethernet communications
-------------------------------------------------------------------
Outputs the time over the ethernet communication
Responds to inputs
*/

// Imports
#include <SPI.h>
#include <QNEthernet.h>
using namespace qindesign::network;

/*
-------------------------------------------------------------------
VARIABLES & USER INPUT
-------------------------------------------------------------------
*/

// Teensy server settings
IPAddress ip(192, 168, 1, 177);
IPAddress myDns(192, 168, 1, 1);
IPAddress gateway(192, 168, 1, 1);
IPAddress subnet(255, 255, 0, 0);

// telnet defaults to port 23
EthernetServer server(23);
boolean gotAMessage = false; // whether or not you got a message from the client yet

// time variables
long unsigned update_last = 0;
long unsigned update_interval = 1500000;    // update interval (microsec)     <-- USER INPUT
const int BAUD = 115200;                   // serial com in bits per second     <-- USER INPUT


/*
-------------------------------------------------------------------
SETUP
-------------------------------------------------------------------
*/
void setup() {
  // I think that the QNEthernet covers this?
    // You can use Ethernet.init(pin) to configure the CS pin
    //Ethernet.init(10);  // Most Arduino shields
    //Ethernet.init(5);   // MKR ETH shield
    //Ethernet.init(0);   // Teensy 2.0
    //Ethernet.init(20);  // Teensy++ 2.0
    //Ethernet.init(15);  // ESP8266 with Adafruit Featherwing Ethernet
    //Ethernet.init(33);  // ESP32 with Adafruit Featherwing Ethernet

  Serial.begin(BAUD);           // initializes serial communication at set baud rate
  while (!Serial && millis() < 4000) {
    // Wait for Serial
  }
  printf("Starting...\r\n");

  // start the Ethernet connection:
  Serial.println("Trying to get an IP address using DHCP");
  if (Ethernet.begin()) {
    Serial.println("Failed to configure Ethernet using DHCP");
    // Check for Ethernet hardware present
    if (Ethernet.hardwareStatus() == EthernetNoHardware) {
      Serial.println("Ethernet shield was not found.");
    } else if (Ethernet.hardwareStatus() == EthernetW5100) {
      Serial.println("W5100 Ethernet controller detected.");
    } else if (Ethernet.hardwareStatus() == EthernetW5200) {
      Serial.println("W5200 Ethernet controller detected.");
    } else if (Ethernet.hardwareStatus() == EthernetW5500) {
      Serial.println("W5500 Ethernet controller detected.");
    } else {
      Serial.println("Unknwon Ethernet controller.");
    }

    if (Ethernet.linkStatus() == LinkOFF) {
      Serial.println("Ethernet cable is not connected.");
    }
    // initialize the Ethernet device not using DHCP:
    Serial.println("Starting without DHCP");
    Ethernet.begin(ip, subnet, gateway, myDns);
  }
  // print your local IP address:
  Serial.print("My IP address: ");
  Serial.println(Ethernet.localIP());

  // start listening for clients
  server.begin();
}

/*
-------------------------------------------------------------------
LOOP
-------------------------------------------------------------------
*/
void loop() {
  // check for last reading update
  if ((micros() - update_last) > update_interval) {
    update_last = micros();                               // update last time update
    
    // send data to serial monitor 
    Serial.print(update_last);                            // print time reading
    Serial.println();
    server.write(update_last);
    delay(10);
  }
  // checks if user input is available to read
  if (Serial.available() > 0) {
    // read user input
    String test = Serial.readStringUntil('\n');
    Serial.print(test);
    Serial.println();
    delay(10);
  }

  // wait for a new client:
  EthernetClient client = server.available();

  // when the client sends the first byte, say hello:
  if (client) {
    if (!gotAMessage) {
      Serial.println("We have a new client");
      client.println("Hello, client!");
      gotAMessage = true;
    }

    // read the bytes incoming from the client:
    char thisChar = client.read();
    // echo the bytes back to the client:
    server.write(thisChar);
    // echo the bytes to the server as well:
    Serial.print(thisChar);
    Ethernet.maintain();
  }
}
