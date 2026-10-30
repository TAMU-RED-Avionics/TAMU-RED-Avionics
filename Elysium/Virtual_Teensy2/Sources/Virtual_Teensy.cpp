#include "Virtual_Teensy.h"
#include <QRandomGenerator>
#include <QGridLayout>
#include <QTextStream>
#include <QPushButton>
#include <Qt>

#include <QDebug>
#include <iostream>
using std::cout;
using std::endl;

const QString PORT = "/dev/Virtual_Teensy";
const int BAUD = 115200;

Virtual_Teensy::Virtual_Teensy(int interval, QFile* config):
    QWidget(), layout(new QGridLayout()), cur_row(3), interval(interval), config(config), sensors(),
    interval_label(new QLabel()), interval_slider(new QSlider()), ser(new QSerialPort()), timer(new QTimer()) {
    // Layout to attach internal widgets to
    this->layout->setSpacing(10);
    this->layout->setContentsMargins(5,5,5,5);

    // Label for interval selection slider
    QLabel* interval_title = new QLabel("Time between sending data:");
    interval_title->setAlignment(Qt::AlignLeft | Qt::AlignVCenter);
    this->layout->addWidget(interval_title, 0, 0);
    this->interval_label->setAlignment(Qt::AlignRight | Qt::AlignVCenter);
    this->layout->addWidget(this->interval_label, 0, 1);

    // Configure Slider for the interval and add to layout
    this->interval_slider->setMinimum(1);
    this->interval_slider->setMaximum(500);
    this->interval_slider->setValue(this->interval);
    this->interval_slider->setOrientation(Qt::Horizontal);
    QObject::connect(interval_slider, SIGNAL(valueChanged(int)), this, SLOT(set_interval(int)));
    this->set_interval(this->interval);
    this->layout->addWidget(this->interval_slider, 1, 0, 1, 2);

    // Button to add new virtual sensors
    QPushButton* add_sensor_btn = new QPushButton("Add new virtual sensor");
    QObject::connect(add_sensor_btn, SIGNAL(clicked()), this, SLOT(add_sensor()));
    this->layout->addWidget(add_sensor_btn, 2, 0, 1, 2);

    // TODO: Add all sensors from the config file
    if (this->config->open(QIODevice::ReadOnly | QIODevice::Text)) {
        QTextStream in(this->config);
        while (!in.atEnd()) {
            QStringList info = in.readLine().split(',');
            qDebug() << info;
            this->add_sensor(info[0], info[1], info[2], info[3], info[4], info[5].toInt());
        }
        this->config->close();
    } else {
        cout << "Could not open " << this->config->fileName().toStdString() << endl;
    }

    // Attach the layout to this object
    this->setLayout(this->layout);

    /*
        Non UI Elements
    */

    // Setup and connect to the GUI
    this->ser->setPortName(PORT);
    this->ser->setBaudRate(BAUD);
    this->ser->open(QSerialPort::ReadWrite);

    // If connection fails, print debug info
    if (!this->ser->isOpen()) {
        qDebug() << this->ser->error();
    }

    // Reads are detected automatically, writes every this->interval
    QObject::connect(this->ser, SIGNAL(readyRead()), this, SLOT(read_data()));
    QObject::connect(this->timer, SIGNAL(timeout()), this, SLOT(write_data()));
    this->timer->start(this->interval);
}

Virtual_Teensy::~Virtual_Teensy() {
    // Close and delete non-UI elements
    this->ser->close();
    delete this->ser;
    delete this->timer;

    // Save the current configuration
    if (this->config->open(QIODevice::WriteOnly | QIODevice::Text)) {
        QTextStream out(this->config);
        for (int i = 0; i < this->sensors.size(); ++i) {
            out << this->sensors[i]->get_settings() << endl;
        }
        this->config->close();
    } else {
        cout << "Could not open " << this->config->fileName().toStdString() << endl;
    }
}

void Virtual_Teensy::set_interval(int interval) {
    this->interval = interval;
    this->interval_label->setText(QString::number(interval) + " ms");
    this->timer->setInterval(interval);
}

void Virtual_Teensy::read_data() {
    QTextStream in(this->ser->readAll());
    bool first = true;
    while (!in.atEnd()) {
        QString text = in.readLine();
        if ("nop" == text) {
            continue;
        }
        if (first) {
            cout << "Read:";
            first = false;
        }

        cout << '\t' << text.toStdString() << "\r\n";
        //cout << '\t' << text.size() << "\r\n";
    }
    if (!first) {
        cout << endl;
    }
}

void Virtual_Teensy::write_data() {
    QString data = "";
    for (int i = 0; i < this->sensors.size(); ++i) {
        data += this->sensors[i]->get_reading();

        if (this->sensors.size() - 1 != i) {
            data += ',';
        }
    }
    
    // Uncomment if you need to confirm the output, otherwise it spams the terminal
    // cout << "Write:\t" << data.toStdString() << "\\r\\n" << endl;

    data += "\r\n";
    this->ser->write(data.toUtf8()); 
}

void Virtual_Teensy::add_sensor(QString ID, QString min_data, QString max_data, QString min_error,
    QString max_error, bool is_gaussian_error) {
    // Create a new sensor with given (or default) settings
    VT_Sensor* sensor = new VT_Sensor(ID, min_data, max_data, min_error, max_error, is_gaussian_error);
    QObject::connect(sensor, SIGNAL(remove_sensor(VT_Sensor*)), this, SLOT(remove_sensor(VT_Sensor*)));

    // Add to list and layout
    this->sensors.append(sensor);
    this->layout->addWidget(sensor, this->cur_row++, 0, 1, 2);
}

void Virtual_Teensy::remove_sensor(VT_Sensor* sensor_ptr) {
    this->sensors.removeOne(sensor_ptr);
    delete sensor_ptr;
}

void Virtual_Teensy::pause() {
    if (timer->isActive()) {
        timer->stop();
    }
    if (ser->isOpen()) {
        ser->close();
    }
}

void Virtual_Teensy::start() {
    if (!ser->isOpen()) {
        ser->setPortName(PORT);
        ser->setBaudRate(BAUD);
        ser->open(QSerialPort::ReadWrite);
    }
    if (!timer->isActive()) {
        timer->start(interval);
    }
}