#ifndef GUI_COM_Window_H
#define GUI_COM_Window_H

#include "Frame_with_Title.h"
#include "GUI_CTRL_Window.h"
#include "GUI_DAQ_Window.h"
#include "State_Machine.h"

#include <QWidget>
#include <QPushButton>
#include <QComboBox>
#include <QGridLayout>
#include <QString>

#include <QSerialPort>

// Forward declaration of mainwindow to avoid circular dependencies
class GUI_Main_Window;

// Constant Declaration, not definition to avoid multiply defined objects with all files that include this header
// Defined in the .cpp file
extern const int CONNECTION_CONFRIM_INTERVAL;

/*
    The Main Window for the GUI.
    Contains the layout which all major elements are attached to.
*/
class GUI_COM_Window : public QWidget {
    Q_OBJECT

public:
    // Inherits the constructors (default, paramterized, copy, and move) from the base class
    // The parameterized constructor and destructor will be overwritten in the source file
    using QWidget::QWidget;
    GUI_COM_Window(GUI_Main_Window* parent);
    bool get_is_connected();
    void update_config();

private:
    GUI_Main_Window* root;
    QString current_port_name;
    QString current_baud_rate;

    bool enable_disconnect_confirmation;
    bool is_connected;
    QComboBox* COM_selection;
    QComboBox* baud_selection;
    QPushButton* refresh;
    QPushButton* connect;

    QSerialPort* ser;

    GUI_CTRL_Window* CTRL;
    GUI_DAQ_Window* DAQ;
    State_Machine* state_machine;

    void check_connection_button();
    void serial_open();
    void serial_close();

private slots:
    void update_COM_options();
    void update_baud_options();
    void update_port(const QString& text);
    void update_baud(const QString& text);
    void connect_to_serial();
    void send_nop();
};


#endif