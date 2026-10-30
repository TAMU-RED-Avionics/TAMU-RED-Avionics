#include "VT_Main_Window.h"
#include <QApplication>
#include <QScreen>

int main (int argc, char *argv[]) {
    // Creates an instance of QApplication
    QApplication* vt_app = new QApplication(argc, argv);

    // This is our MainWindow class containing our vt and functionality
    VT_Main_Window* vt_main_window = new VT_Main_Window;

    // Move window to the center of the screen
    int w = vt_main_window->frameGeometry().width();
    int h = vt_main_window->frameGeometry().height();
    int x = vt_app->primaryScreen()->geometry().center().x();
    int y = vt_app->primaryScreen()->geometry().center().y();
    vt_main_window->move(x - w/2, y - h/2);

    // Run the application and return execs() return value/code
    vt_main_window->show();
    return vt_app->exec();
}
