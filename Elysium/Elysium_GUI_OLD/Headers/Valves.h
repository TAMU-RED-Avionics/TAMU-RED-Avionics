#ifndef Valves_H
#define Valves_H

#include <QSerialPort>
#include <QPushButton>
#include <QString>
#include <QWidget>

class Valve : public QWidget {
    Q_OBJECT
public:
    // Constructors 
    // The pointer is passed in, no memory on the heap is allocated
    // Thus no rule of 3 or 5 constructors need special definitions
    Valve();
    Valve(QSerialPort* ser, QString ID, QString name, int state);

    // Getter functions
    QSerialPort* get_ser();
    QString get_ID();
    QString get_name();
    int get_state();

    // Setter functions (note that the set_state() function will also emit a signal to the teensy)
    void set_ser(QSerialPort* ser);
    void set_ID(QString ID);
    void set_name(QString name);

private:
    QSerialPort* ser;
    QString ID;
    QString name;
    int state;

    QPushButton* open;
    QPushButton* close;

public slots:
    void set_state(int state);

protected slots:
    void set_open();
    void set_closed();

signals:
    void updated_state(const QString& command);
};

class Solenoid_Valve : public Valve {
public:
    // Constructors
    Solenoid_Valve();
    Solenoid_Valve(QSerialPort* ser, QString ID, QString name, bool normally_open);

    // Getter and setter for derived class variables
    bool get_normally_open();
    void set_normally_open(bool normally_open);
private:
    bool normally_open;
};

class LA_Ball_Valve : public Valve {
public:
    // Constructors
    LA_Ball_Valve();
    LA_Ball_Valve(QSerialPort* ser, QString ID, QString name, int state, bool is_open);

    // Getter and setter for derived class variables
    bool get_is_open();
    void set_is_open(bool is_open);
private:
    // Note that is_open is distinct from state.
    // state is the state that the GUI has told the valve to be in
    // is_open is based the last signal from the limit switch which notifies if it is fully closed
    bool is_open;
};

#endif