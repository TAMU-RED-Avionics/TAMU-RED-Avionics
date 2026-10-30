#ifndef Virtual_Teensy_H
#define Virtual_Teensy_H

#include "VT_Sensor.h"

#include <QGridLayout>
#include <QSerialPort>
#include <QWidget>
#include <QString>
#include <QSlider>
#include <QTimer>
#include <QLabel>
#include <QFile>
#include <QList>

#include <QDebug>
#include <iostream>
using std::cout;
using std::endl;

extern const QString PORT;
extern const int BAUD;

class Virtual_Teensy : public QWidget {
    Q_OBJECT
public:
    using QWidget::QWidget;
    Virtual_Teensy(int interval, QFile* config);
    ~Virtual_Teensy();
    void pause();
    void start();
private:
    QGridLayout* layout;
    int cur_row;
    int interval;
    QFile* config;
    QList<VT_Sensor*> sensors;

    QLabel* interval_label;
    QSlider* interval_slider;
    QSerialPort* ser;
    QTimer* timer;

private slots:
    void set_interval(int interval);
    void read_data();
    void write_data();
    void add_sensor(QString ID="", QString min_data="", QString max_data="", QString min_error="",
        QString max_error="", bool is_gaussian_error=false);
    void remove_sensor(VT_Sensor* sensor_ptr);
};

#endif