#include "GUI_APP.h"
#include "GUI_Main_Window.h"

int main (int argc, char *argv[]) {
    // Creates an instance of QApplication
    GUI_APP* gui_app = new GUI_APP(argc, argv);

    // This is our MainWindow class containing our GUI and functionality
    GUI_Main_Window* gui_main_window = new GUI_Main_Window;

    // Move window to the center of the screen
    int w = gui_main_window->frameGeometry().width();
    int h = gui_main_window->frameGeometry().height();
    int x = gui_app->primaryScreen()->geometry().center().x();
    int y = gui_app->primaryScreen()->geometry().center().y();
    gui_main_window->move(x - w/2, y - h/2);

    // Run the application and return execs() return value/code
    gui_main_window->show();
    return gui_app->exec();
}
