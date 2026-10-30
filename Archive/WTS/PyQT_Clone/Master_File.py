# MASTER FILE; RUN THIS TO START GUI

# import GUI and communication scripts from other files
from GUI_Architecture import GUI_APP, GUI_Main_Window

# Create the application instance
gui_app = GUI_APP()

# Create the main window of the GUI, parent of all other widgets
gui_main_window = GUI_Main_Window()
gui_main_window.show()

# Executes the main loop
gui_app.exec()
