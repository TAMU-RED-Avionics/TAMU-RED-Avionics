#ifndef VT_Main_Window_H
#define VT_Main_Window_H

#include "Virtual_Teensy.h"

#include <QContextMenuEvent>
#include <QCloseEvent>
#include <QMainWindow>
#include <QGridLayout>
#include <QFile>


/*
    The Main Window for the Virtual Teensy (VT).
    Contains the layout which all major elements are attached to.
*/
class VT_Main_Window : public QMainWindow {
    Q_OBJECT
public:
    // Inherits the constructors (default, paramterized, copy, and move) from the base class
    // The default will be overwritten in the source file
    using QMainWindow::QMainWindow;
    VT_Main_Window();
private:
    QGridLayout* layout;
    Virtual_Teensy* vt;
    QFile* configuration;

    void closeEvent(QCloseEvent* event);
    void contextMenuEvent(QContextMenuEvent* event);
private slots:
    void set_configuration(QAction* configuration);
};


#endif