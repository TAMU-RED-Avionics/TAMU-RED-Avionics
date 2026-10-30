Elysium Teensy
Overview
The Elysium Teensy program is designed for managing and monitoring various sensors and actuators in a complex system. It integrates load cells, thermocouples, pressure transducers, and accelerometers to provide real-time data and control mechanisms for a hardware project, possibly in an experimental or industrial setup. This README will guide you through downloading the necessary libraries from GitHub and installing them into your Arduino library folder.

Features
- Sensor Management: Continuously reads and processes data from pressure transducers, load cells, thermocouples, and accelerometers.
- Actuator Control: Controls multiple solenoid valves and other actuators based on user input.
- Data Logging: Sends sensor data to the serial monitor for real-time monitoring.

Before installing the libraries, ensure you have the Arduino IDE installed on your computer.

To run the Elysium Teensy program, you need the following libraries:
- HX711 - For interfacing with load cells.
- Adafruit MCP9600 - For thermocouple readings.
- Wire - For I2C communication (included with the Arduino IDE).
- IMU - For accelerometer readings.
- LSM6DSL and LIS3MDL - For accelerometer hardware interfacing.

Downloading Libraries:

For the Adafruit MCP9600 library, download it through the Arduino IDE library search and downloader.

For the HX711, IMU, LSM6DSL and LIS3MDL libraries, follow the process listed below:
1. Go to the RED GitHub repository.
2. Click on the "download raw file content" button for all 4 of the above-listed libraries. Do this for both the .h and .cpp files when available.
3. Create folders for these files, named with the library name (do not include the .h or .cpp). Move the downloaded content files into these folders.
4. Locate Your Arduino Library Folder:
	Open Arduino IDE.
	Go to File > Preferences.
	In the preferences window, note the location of the "Sketchbook location". The libraries folder is located inside this directory.
5. Copy the Library Files:
	For each downloaded library, locate the folder.
	Copy the entire folder for each library (e.g., HX711, Adafruit_MCP9600, etc.).
	Paste these folders into your Arduino libraries directory (e.g., Documents/Arduino/libraries).
6. Restart Arduino IDE:
	After copying the libraries, restart the Arduino IDE to ensure it recognizes the new libraries.

User Inputs:
Be sure to set the following user-defined inputs according to your specific hardware setup:

- Sensor update interval
- Shutdown time
- Pin assignments for valves, load cells, and pressure transducers
- Compiling and Uploading
- Connect your Teensy board to your computer via USB.
- In Arduino IDE, select the correct board and port:
- Go to Tools > Board and select your Teensy model.
- Go to Tools > Port and select the port corresponding to your Teensy board.
- Click on the checkmark to compile the code, and if successful, click on the right arrow to upload it to your board.

Conclusion:
You are now ready to use the Elysium Teensy program.