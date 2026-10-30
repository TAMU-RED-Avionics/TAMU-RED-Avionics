#ifndef VT_Sensor_H
#define VT_Sensor_H

#include <QCheckBox>
#include <QWidget>
#include <QString>

// No default Qt feature for Gaussian distributions
#include <random>

class VT_Sensor : public QWidget {
    Q_OBJECT
public:
    using QWidget::QWidget;
    VT_Sensor(QString ID="", QString min_data="", QString max_data="", QString min_error="",
        QString max_error="", bool is_gaussian_error=false);
    QString get_reading();
    QString get_settings();
private:
    QString ID;
    double min_data;
    double max_data;
    double cur_data;
    double min_error;
    double max_error;
    double cur_error;

    QCheckBox* is_gaussian_check;
    std::default_random_engine generator;
    void set_cur_data(const QString& cur_data);
    void set_cur_error(const QString& cur_error);
private slots:
    void set_ID(const QString& ID);
    void set_min_data(const QString& min_data);
    void set_max_data(const QString& max_data);
    void set_min_error(const QString& min_error);
    void set_max_error(const QString& max_error);

    void update_data(const int& cur_position);
    void update_error(const int& cur_position);
    void remove_sensor_called();
signals:
    void new_data(const QString& data);
    void new_error(const QString& data);
    void remove_sensor(VT_Sensor* sensor_ptr);
};

#endif