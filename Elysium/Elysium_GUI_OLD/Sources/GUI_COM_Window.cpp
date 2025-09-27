#include "GUI_COM_Window.h"
#include "GUI_Main_Window.h"
#include "Standard_Label.h"

// For serial communication
#include <QIODevice> // Might not need this
#include <QSerialPortInfo>
#include <QSerialPort> // In header file
#include <QList>

// For standard Qt objects and namespace
#include <QMessageBox>
#include <QGridLayout>
#include <QStringList>
#include <QObject>
#include <QFrame>
#include <Qt>

#include <QListView>

// For testing only
#include <QDebug>
#include<iostream>
using std::cout;
using std::endl;

// Constants (user set parameters)
// Number of milliseconds between nop signals to confirm that the connection is live
const int CONNECTION_CONFIRM_INTERVAL = 50;

/*
    Initializes the Communications Window for the GUI.
*/
GUI_COM_Window::GUI_COM_Window(GUI_Main_Window* parent):
    QWidget(), root(parent), current_port_name(""), current_baud_rate(""),
    enable_disconnect_confirmation(true), is_connected(false), COM_selection(new QComboBox()),
    baud_selection(new QComboBox()), refresh(new QPushButton), connect(new QPushButton()), ser(nullptr),
    CTRL(nullptr), DAQ(nullptr), state_machine(nullptr) {
    
    // Layout for the buttons and labels
    QGridLayout* bottom_layout = new QGridLayout();
    bottom_layout->setContentsMargins(5, 5, 5, 5);
    bottom_layout->setSpacing(10);

    // COM Port and Baud Rate selector boxes and labels
    new Standard_Label("COM Port:", bottom_layout, 0);
    new Standard_Label("Baud Rate:", bottom_layout, 1);

    QObject::connect(this->COM_selection, SIGNAL(currentTextChanged(const QString&)),
            this, SLOT(update_port(const QString&)));
    QObject::connect(this->baud_selection, SIGNAL(currentTextChanged(const QString&)),
            this, SLOT(update_baud(const QString&)));
    
    // Add custom view options
    this->COM_selection->setView(new QListView);
    this->baud_selection->setView(new QListView);

    bottom_layout->addWidget(this->COM_selection, 0, 1);
    bottom_layout->addWidget(this->baud_selection, 1, 1);


    // Construct refresh button to check and update both lists (also resets selected item to default)
    this->refresh->setText("Refresh");
    QObject::connect(refresh, SIGNAL(clicked()),
            this, SLOT(update_COM_options()));
    QObject::connect(refresh, SIGNAL(clicked()),
            this, SLOT(update_baud_options()));
    bottom_layout->addWidget(this->refresh, 0, 2);

    // Connect button attempts to open the serial connection
    this->connect->setText("Connect");
    QObject::connect(connect, SIGNAL(clicked()),
            this, SLOT(connect_to_serial()));
    bottom_layout->addWidget(this->connect, 1, 2);

    // Initialize options for the selection menus [must be done after they are defined, to set states]
    this->update_COM_options();
    this->update_baud_options();

    // Create frame around section
    QFrame* bottom_widget = new QFrame();
    bottom_widget->setLayout(bottom_layout);
    Frame_with_Title* layout = new Frame_with_Title("Teensy Connection", bottom_widget);

    this->setLayout(layout);
    this->setFixedHeight(106);
    this->root->add_to_main_window(this, 1, 0);
}

/*
    Public functions
*/

bool GUI_COM_Window::get_is_connected() {
    return is_connected;
}

void GUI_COM_Window::update_config() {
    if (this->CTRL) {
        delete this->CTRL;
        this->CTRL = new GUI_CTRL_Window(this->root, this->ser);
    } if (this->DAQ) {
        delete this->DAQ;
        this->DAQ = new GUI_DAQ_Window(this->root, this->ser);
    } if (this->state_machine) {
        // Create state machine, connect to CTRL and DAQ
        QString config_name = this->root->get_configuration()->dirName();
        this->state_machine = new State_Machine(config_name, this->DAQ->get_data());
        QObject::connect(this->state_machine, SIGNAL(new_state(QString)),
                         this->CTRL, SLOT(new_state(QString)));
        QObject::connect(this->state_machine, SIGNAL(allowed_states(QStringList*)),
                         this->CTRL, SLOT(sm_allowed_states(QStringList*)));
        QObject::connect(this->CTRL, SIGNAL(auto_aborts_enabled(int)),
                         this->state_machine, SLOT(set_auto_aborts_enabled(int)));
        QObject::connect(this->CTRL, SIGNAL(people_safe_dist(int)),
                         this->state_machine, SLOT(set_people_safe_dist(int)));
        QObject::connect(this->CTRL, SIGNAL(new_state_signal(QString)),
                         this->state_machine, SLOT(set_state(QString)));
        QObject::connect(this->DAQ, SIGNAL(new_data()), this->state_machine, SLOT(new_data()));

        // Initialize the state machine (cannot do in constructor because it needs connections)
        this->state_machine->start();
    }
}

/*
    Private functions
*/

void GUI_COM_Window::update_COM_options() {
    // Check for all available ports (limited to USB serial) [will not find virtual]
    cout << "Searching for serial ports... ";
    QList<QSerialPortInfo> ports = QSerialPortInfo::availablePorts();
    cout << ports.size() << " found" << endl;

    // Isolate the names of the ports, add virtual and Null ("-") ports.
    QStringList port_names = {"-"};
    for (int i = 0; i < ports.size(); ++i) {
        QSerialPortInfo port = ports[i];
        cout << "Port Name: " << port.portName().toStdString();
        cout << ", Manufacturer: " << port.manufacturer().toStdString();
        cout << ", Product ID: " << port.productIdentifier();
        cout << ", Vendor ID: " << port.vendorIdentifier();
        cout << ", System Location: " << port.systemLocation().toStdString();
        cout << ", S/N: " << port.serialNumber().toStdString();
        cout << ", Description: " << port.description().toStdString() << endl;

        // The default build of QSerialPortInfo cannot get actual details
        // However, the usbipd method seems to always map the COM port to /dev/ttyACMx for some int x
        // Print all info, in case it works and will allow to check which device is new
        if (port.portName().contains("ttyACM")) {
            port_names.append(port.portName());
        }
    }
    port_names.append("/dev/Test_GUI");

    this->COM_selection->clear();
    this->COM_selection->addItems(port_names);
}

void GUI_COM_Window::update_port(const QString& text) {
    this->current_port_name = text;
    this->check_connection_button();
}

void GUI_COM_Window::update_baud_options() {
    const QStringList baud_rates = {"-", "300", "600", "1200", "2400", "4800", "9600", "14400",
            "19200", "28800", "38400", "56000", "57600", "115200", "128000", "256000"};
    this->baud_selection->clear();
    this->baud_selection->addItems(baud_rates);
}

void GUI_COM_Window::update_baud(const QString& text) {
    this->current_baud_rate = text;
    this->check_connection_button();
}

void GUI_COM_Window::check_connection_button() {
    if ('-' == this->current_port_name || '-' == this->current_baud_rate) {
        this->connect->setDisabled(true);
    } else {
        this->connect->setEnabled(true);
    }
}

void GUI_COM_Window::connect_to_serial() {
    // If not connected, attempt to connect
    if (!this->is_connected) {
        this->serial_open();
        if (!this->is_connected) {
            cout << "ERROR: Cannot open serial connection\n" << endl;
            qDebug() << this->ser->error();
            return;
        }

        // Disable connection configuration buttons
        this->COM_selection->setDisabled(true);
        this->baud_selection->setDisabled(true);
        this->refresh->setDisabled(true);
        this->connect->setText("Disconnect");

        // Create CTRL and DAQ blocks, resize
        this->CTRL = new GUI_CTRL_Window(this->root, this->ser);
        this->DAQ = new GUI_DAQ_Window(this->root, this->ser);

        // TODO: Fix autosizing, remove manual enforcement
        this->root->manual_resize(646, 500);

        // Create state machine, connect to CTRL and DAQ
        QString config_name = this->root->get_configuration()->dirName();
        this->state_machine = new State_Machine(config_name, this->DAQ->get_data());
        QObject::connect(this->state_machine, SIGNAL(new_state(QString)),
                         this->CTRL, SLOT(new_state(QString)));
        QObject::connect(this->state_machine, SIGNAL(allowed_states(QStringList*)),
                         this->CTRL, SLOT(sm_allowed_states(QStringList*)));
        QObject::connect(this->CTRL, SIGNAL(auto_aborts_enabled(int)),
                         this->state_machine, SLOT(set_auto_aborts_enabled(int)));
        QObject::connect(this->CTRL, SIGNAL(people_safe_dist(int)),
                         this->state_machine, SLOT(set_people_safe_dist(int)));
        QObject::connect(this->CTRL, SIGNAL(new_state_signal(QString)),
                         this->state_machine, SLOT(set_state(QString)));
        QObject::connect(this->DAQ, SIGNAL(new_data()), this->state_machine, SLOT(new_data()));

        // Initialize the state machine (cannot do in constructor because it needs connections)
        this->state_machine->start();
        
        return;
    }

    QMessageBox::StandardButton confirmation = QMessageBox::Apply;
    if (this->enable_disconnect_confirmation) {
        confirmation = QMessageBox::warning(this, "Confirmation",
                        "Are you sure you want to disconnect from the Teensy?",
                        QMessageBox::Cancel | QMessageBox::Apply);
    }

    // Only delete if disconnect is confirmed or the confirmation is disabled
    if (QMessageBox::Apply == confirmation) {
        // Remove the CTRL and DAQ blocks, CTRL requires active serial connection
        delete this->CTRL;

        // DAQ requires no serial connection to close
        this->serial_close();
        delete this->DAQ;
        delete this->state_machine;

        // Re-enable the connection configuration buttons
        this->COM_selection->setEnabled(true);
        this->baud_selection->setEnabled(true);
        this->refresh->setEnabled(true);
        this->connect->setText("Connect");

        // TODO: Fix autosizing, remove manual enforcement
        this->root->manual_resize(320, 150);
    }
}

void GUI_COM_Window::serial_open() {
    cout << "Attempting to connect to serial" << endl;
    QString startup_command = "Start\r\n";
    if (this->ser) {
        try {
            if (this->ser->isOpen()) {
                cout << "Already Open" << endl;
                this->ser->flush();
                this->is_connected = true;

                // Startup/Restart Teensy
                this->ser->write(startup_command.toUtf8());
                // Send "nop" (no operation) at regular interval to confirm active connection
                QTimer* nop_timer = new QTimer();
                QObject::connect(nop_timer, SIGNAL(timeout()), this, SLOT(send_nop()));
                nop_timer->start(CONNECTION_CONFIRM_INTERVAL);
            this->ser->flush();

                return;
            } else {
                delete this->ser;
            }
        } catch (...) {
            cout << "serial connection already exists, but cannot access isOpen()" << endl;
            delete this->ser;
        }
    }

    try {
        QString PORT = this->current_port_name;
        int BAUD = this->current_baud_rate.toInt();
        this->ser = new QSerialPort();
        this->ser->setPortName(PORT);
        this->ser->setBaudRate(BAUD);

        this->ser->open(QSerialPort::ReadWrite);
        if (this->ser->isOpen()) {
            this->ser->flush();
            this->is_connected = true;

            // Startup/Restart Teensy
            this->ser->write(startup_command.toUtf8());
            this->ser->flush();
            // Send "nop" (no operation) at regular interval to confirm active connection
            QTimer* nop_timer = new QTimer();
            QObject::connect(nop_timer, SIGNAL(timeout()), this, SLOT(send_nop()));
            nop_timer->start(CONNECTION_CONFIRM_INTERVAL);
        } else {
            return;
        }
    } catch (...) {
        return;
    }
}

void GUI_COM_Window::serial_close() {
    try {
        this->ser->isOpen();
        this->ser->close();
        this->is_connected = false;
    } catch (...) { }
}

void GUI_COM_Window::send_nop() {
    QString nop = "nop\r\n";
    if (this->ser->isOpen()) {
        this->ser->write(nop.toUtf8());
        this->ser->flush();
    }
}
