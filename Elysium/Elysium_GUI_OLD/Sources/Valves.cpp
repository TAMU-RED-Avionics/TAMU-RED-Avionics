#include "Valves.h"
#include "Standard_Label.h"
#include <QGridLayout>
#include <QPushButton>

// TESTING ONLY
#include <iostream>
using std::cout;
using std::endl;

//////////////////// Valve CLASS ////////////////////
// Constructors
Valve::Valve() : QWidget(), ser(nullptr), ID(), name(), state(-1), open(nullptr), close(nullptr) {}

Valve::Valve(QSerialPort* ser, QString ID, QString name, int state) : QWidget(), ser(ser), ID(ID),
    name(name), state(state), open(new QPushButton("OPEN")), close(new QPushButton("CLOSE")) {
    // Construct a Layout to hold the buttons and label
    QGridLayout* layout = new QGridLayout();
    layout->setContentsMargins(0, 0, 0, 0);
    layout->setSpacing(10);

    // Create Label
    QString label = name;
    label.append(" (");
    label.append(ID);
    label.append("):");
    new Standard_Label(label, layout, 0);

    // Add and connect push buttons
    QObject::connect(open, SIGNAL(clicked()), this, SLOT(set_open()));
    QObject::connect(close, SIGNAL(clicked()), this, SLOT(set_closed()));
    if (1 == state) {
        set_open();
    } else {
        set_closed();
    }

    layout->addWidget(open, 0, 1);
    layout->addWidget(close, 0, 2);

    this->setLayout(layout);
}

// Getters
QSerialPort* Valve::get_ser() {
    return ser;
}

QString Valve::get_ID() {
    return ID;
}

QString Valve::get_name() {
    return name;
}

int Valve::get_state() {
    return state;
}

// Setters
void Valve::set_ser(QSerialPort* ser) {
    this->ser = ser;
}

void Valve::set_ID(QString ID) {
    this->ID = ID;
}

void Valve::set_name(QString name) {
    this->name = name;
}

void Valve::set_state(int state) {
    QString command = ID + ":" + QString::number(state) + "\r\n";

    try {
        this->ser->write(command.toUtf8());
    } catch(...) {
        cout << "Error Writing to ser" << endl;
        return;
    }

    // Update the buttons
    this->open->setDisabled(state);
    this->close->setEnabled(state);

    // Only updates the state/ emits signal if the command was properly sent to the serial port
    this->state = state;
    emit updated_state(ID + ":" + QString::number(state));
}

void Valve::set_open() {
    set_state(1);
}

void Valve::set_closed() {
    set_state(0);
}

//////////////////// Solenoid_Valve CLASS ////////////////////
// Constructors
Solenoid_Valve::Solenoid_Valve() : Valve(), normally_open(false) {}

Solenoid_Valve::Solenoid_Valve(QSerialPort* ser, QString ID, QString name, bool normally_open) :
    Valve(ser, ID, name, int(normally_open)), normally_open(normally_open) {}

// Getters/Setters for derived class variables
bool Solenoid_Valve::get_normally_open() {
    return normally_open;
}

void Solenoid_Valve::set_normally_open(bool normally_open) {
    this->normally_open = normally_open;
}

//////////////////// Linear-Actuated Ball Valve CLASS ////////////////////
// Constructors
LA_Ball_Valve::LA_Ball_Valve() : Valve(), is_open(false) {}

LA_Ball_Valve::LA_Ball_Valve(QSerialPort* ser, QString ID, QString name, int state, bool is_open) :
    Valve(ser, ID, name, state), is_open(is_open) {}

// Getters/Setters for derived class variables

bool LA_Ball_Valve::get_is_open() {
    return is_open;
}

void LA_Ball_Valve::set_is_open(bool is_open) {
    this->is_open = is_open;
}
