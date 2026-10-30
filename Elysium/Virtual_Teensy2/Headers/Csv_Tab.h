#ifndef CSV_TAB_H
#define CSV_TAB_H

#include "CSVProcessor.h"
#include "Connector.h"
//#include <QSlider>
#include <QSerialPort>
#include <QComboBox>
#include <QPushButton>
#include <QWidget>
#include <QGridLayout>

class Csv_Tab : public QWidget{
    Q_OBJECT

    public:
        Csv_Tab(QWidget *parent = 0);
        void pause();
        void start();        
    private:
        CSVProcessor *CSV;
        QPushButton *run;
        QComboBox *csv_options;
        QComboBox *delay;
        Connector* connector;
        QSerialPort* ser;

    private slots:
        void run_slot();
        void write_data(QString line);
    signals:
        void run_pressed();

};
    
#endif