#ifndef CONNECTOR_H
#define CONNECTOR_H

#include <QObject>
#include <QSerialPort>
#include <QSerialPortInfo>
#include <QDebug>
#include <QString>


class Connector : public QObject {
    Q_OBJECT

public:
    Connector(const QString& portName, const int BAUD, QObject* parent);
    ~Connector();
    QSerialPort* connect();
private:
    QSerialPort* serialPort;
    QString portName;
    int baudRate;
};

#endif