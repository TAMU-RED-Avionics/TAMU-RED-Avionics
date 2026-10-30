#ifndef Sensor_H
#define Sensor_H

#include <QWidget>
#include <QString>
#include <QLabel>

class Sensor : public QWidget {
    Q_OBJECT
public:
    // Constructors 
    Sensor();
    Sensor(QString ID, QString name, QString unit);

    // Getter/Setter functions
    QString get_ID();
    QString get_name();
    void set_ID(QString ID);
    void set_name(QString name);

    QString get_data();
    QString get_full_name();
    void update_data(const QString& data);
private:
    QString ID;
    QString name;
    QString unit;

    QLabel* data_label;

    void create_label();
};

#endif