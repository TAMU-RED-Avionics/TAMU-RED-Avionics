#include "VTMain_window.h"



#include <QApplication>
#include <QScreen>

void center_screen(VTMain_window *main_window, QApplication &app){

    int w = main_window->frameGeometry().width();
    int h = main_window->frameGeometry().height();
    int x = app.primaryScreen()->geometry().center().x();
    int y = app.primaryScreen()->geometry().center().y();
    main_window->move(x - w/2, y - h/2);

}

int main(int argc, char **argv){

    
    QApplication app(argc, argv);
    VTMain_window main_window;
    center_screen(&main_window, app);
    main_window.show();
    return app.exec();
}


