#include "VT_Sensor.h"
#include <QRandomGenerator>
#include <QGridLayout>
#include <QPushButton>
#include <QLineEdit>
#include <QPixmap>
#include <QSlider>
#include <QLabel>
#include <QIcon>
#include <Qt>

#include <QDebug>
#include <iostream>
using std::cout;
using std::endl;

VT_Sensor::VT_Sensor(QString ID, QString min_data, QString max_data, QString min_error,
    QString max_error, bool is_gaussian_error):
        QWidget(), ID(ID), min_data(min_data.toDouble()), max_data(max_data.toDouble()),
        cur_data(this->min_data), min_error(min_error.toDouble()), max_error(max_error.toDouble()),
        cur_error(this->min_error), is_gaussian_check(new QCheckBox("Guassian\nError?")), generator() {
    // Setup layout
    QGridLayout* layout = new QGridLayout();
    layout->setSpacing(10);
    layout->setContentsMargins(0, 10, 0, 10);

    // Editable zone for ID
    QLineEdit* ID_line = new QLineEdit(ID);
    ID_line->setPlaceholderText("ID");
    ID_line->setFixedWidth(50);
    QObject::connect(ID_line, SIGNAL(textEdited(const QString&)), this, SLOT(set_ID(const QString&)));
    layout->addWidget(ID_line, 0, 1);

    // Editable zones for min/max data ranges
    QLineEdit* min_data_line = new QLineEdit(min_data);
    QLineEdit* max_data_line = new QLineEdit(max_data);
    min_data_line->setPlaceholderText("min value");
    max_data_line->setPlaceholderText("max value");
    min_data_line->setFixedWidth(80);
    max_data_line->setFixedWidth(80);
    QObject::connect(min_data_line, SIGNAL(textEdited(const QString&)), this, SLOT(set_min_data(const QString&)));
    QObject::connect(max_data_line, SIGNAL(textEdited(const QString&)), this, SLOT(set_max_data(const QString&)));
    layout->addWidget(min_data_line, 1, 0);
    layout->addWidget(max_data_line, 1, 6);

    // Editable zones for min/max error ranges
    QLineEdit* min_error_line = new QLineEdit(min_error);
    QLineEdit* max_error_line = new QLineEdit(max_error);
    min_error_line->setPlaceholderText("min error");
    max_error_line->setPlaceholderText("max error");
    min_error_line->setFixedWidth(80);
    max_error_line->setFixedWidth(80);
    QObject::connect(min_error_line, SIGNAL(textEdited(const QString&)), this, SLOT(set_min_error(const QString&)));
    QObject::connect(max_error_line, SIGNAL(textEdited(const QString&)), this, SLOT(set_max_error(const QString&)));
    layout->addWidget(min_error_line, 2, 0);
    layout->addWidget(max_error_line, 2, 6);

    // The sliders for data and error control
    QSlider* data_slider = new QSlider();
    QSlider* error_slider = new QSlider();
    data_slider->setRange(0, 1000);
    error_slider->setRange(0, 1000);
    QObject::connect(data_slider, SIGNAL(valueChanged(int)), this, SLOT(update_data(int)));
    QObject::connect(error_slider, SIGNAL(valueChanged(int)), this, SLOT(update_error(int)));
    data_slider->setOrientation(Qt::Horizontal);
    error_slider->setOrientation(Qt::Horizontal);
    layout->addWidget(data_slider, 1, 1, 1, 5);
    layout->addWidget(error_slider, 2, 1, 1, 5);

    // Fixed text for = and ± seperators
    QLabel* equal = new QLabel("=");
    QLabel* plus_minus = new QLabel("±");
    equal->setAlignment(Qt::AlignCenter);
    plus_minus->setAlignment(Qt::AlignCenter);
    layout->addWidget(equal, 0, 2);
    layout->addWidget(plus_minus, 0, 4);

    // Labels to show current value and error
    QLabel* data_label = new QLabel(QString::number(this->cur_data));
    QLabel* error_label = new QLabel(QString::number(this->cur_error));
    data_label->setAlignment(Qt::AlignCenter);
    error_label->setAlignment(Qt::AlignCenter);
    data_label->setFixedWidth(100);
    error_label->setFixedWidth(100);
    QObject::connect(this, SIGNAL(new_data(const QString&)), data_label, SLOT(setText(const QString&)));
    QObject::connect(this, SIGNAL(new_error(const QString&)), error_label, SLOT(setText(const QString&)));
    layout->addWidget(data_label, 0, 3);
    layout->addWidget(error_label, 0, 5);

    // Checkbox to enable Gaussian error
    this->is_gaussian_check->setLayoutDirection(Qt::RightToLeft);
    this->is_gaussian_check->setToolTip("Default (Unchecked) is Uniformly Distributed Error");
    this->is_gaussian_check->setCheckState(is_gaussian_error ? Qt::Checked : Qt::Unchecked);
    layout->addWidget(this->is_gaussian_check, 0, 0);

    // Button to delete the sensor
    QPushButton* delete_btn = new QPushButton();
    delete_btn->setIcon(QPixmap("Assets/delete_icon.png"));
    QObject::connect(delete_btn, SIGNAL(clicked()), this, SLOT(remove_sensor_called()));
    layout->addWidget(delete_btn, 0, 6);


    this->setLayout(layout);
}

QString VT_Sensor::get_reading() {
    double data = cur_data;
    if (Qt::Checked == this->is_gaussian_check->checkState()) {
        std::normal_distribution<double> distribution(0, this->cur_error);
        data += distribution(this->generator);
    } else {
        // Else corresponds to uniform distribution error
        data += QRandomGenerator::global()->generateDouble() * 2 * this->cur_error - this->cur_error;
    }
    return ID + ":" + QString::number(data);
}

QString VT_Sensor::get_settings() {
    // Output all sensor settings in a csv string.
    QString settings =  "" == ID ? "NULL" : ID;
    settings += ',' + QString::number(min_data) + ',' + QString::number(max_data) + ',';
    settings += QString::number(min_error) + ',' + QString::number(max_error) + ',';
    settings += QString::number(Qt::Checked == this->is_gaussian_check->checkState() ? true : false);
    return settings;
}


void VT_Sensor::set_ID(const QString& ID) {
    this->ID = ID;
}

void VT_Sensor::set_min_data(const QString& min_data) {
    this->min_data = min_data.toDouble();
}

void VT_Sensor::set_max_data(const QString& max_data) {
    this->max_data = max_data.toDouble();
}

void VT_Sensor::set_min_error(const QString& min_error) {
    this->min_error = min_error.toDouble();
}

void VT_Sensor::set_max_error(const QString& max_error) {
    this->max_error = max_error.toDouble();
}

// Update data from slider
void VT_Sensor::update_data(const int& cur_position) {
    this->cur_data = cur_position / 1000.0 * (max_data - min_data) + min_data;
    emit new_data(QString::number(this->cur_data));
}

// Update error from slider
void VT_Sensor::update_error(const int& cur_position) {
    this->cur_error = cur_position / 1000.0 * (max_error - min_error) + min_error;
    emit new_error(QString::number(this->cur_error));
}

void VT_Sensor::remove_sensor_called() {
    emit remove_sensor(this);
}
