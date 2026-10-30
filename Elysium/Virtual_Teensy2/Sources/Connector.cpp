#include "Connector.h"

Connector::Connector(const QString& portName, const int BAUD, QObject* parent)
    :QObject(parent), portName(portName), serialPort(new QSerialPort()) {
    
}
Connector::~Connector() {
    if (serialPort->isOpen()) {
        serialPort->close();
    }
}
QSerialPort* Connector::connect(){
    this->serialPort->setPortName(portName);
    this->serialPort->setBaudRate(baudRate);
    this->serialPort->open(QSerialPort::ReadWrite);
    
    // If connection fails, print debug info
    if (!this->serialPort->isOpen()) {
        qDebug() << "not working";
        qDebug() << this->serialPort->error();
        return nullptr;
    }
    qDebug() << "Connected to: " << portName;
    return this->serialPort;
}