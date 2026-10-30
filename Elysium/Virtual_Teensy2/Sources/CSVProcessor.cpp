#include "CSVProcessor.h"

#include <QTime>
#include <QMap>
#include <QString>
#include <QFile>
#include <QTextStream>
#include <QDebug>
#include <QMessageBox>
#include <QRegularExpression>
#include <QCoreApplication>
#include <QEventLoop>


CSVProcessor::CSVProcessor(const QString& filePath, int delay_ms, QWidget *parent)
    :QWidget(parent), filePath(filePath), delay_ms(delay_ms){

    //QObject::connect(this, &CSVProcessor::pressureUpdated, this, &CSVProcessor::edit);
    //QTimer *delayTimer = new QTimer(this);


} //base class must be initalized first



void CSVProcessor::readCSV(){
    QFile file(filePath);
    // If not csv found pop up box
    if (!file.open(QIODevice::ReadOnly | QIODevice::Text)){
        QMessageBox msg;
        msg.setText("No csv file found");
        msg.setIcon(QMessageBox::Warning);
        msg.setWindowTitle("ERROR");
        msg.exec();
        return;
    }
    //  read line by line csv
    QTextStream in(&file);
    while (!in.atEnd()) {
        QString line = in.readLine();
        //qDebug() << qUtf8Printable(line);
        //Process_line(line);
        emit new_pressure(line);
        delay(delay_ms);
       //emmit new_data(data thats processed)
    }
}


    

void CSVProcessor::delay(int millisecondsToWait ){
    QTime dieTime = QTime::currentTime().addMSecs( millisecondsToWait );
    while( QTime::currentTime() < dieTime )
    {
        QCoreApplication::processEvents( QEventLoop::AllEvents, 100 );
    }
}

// for real VT no need to process line just send new_pressure(line) 