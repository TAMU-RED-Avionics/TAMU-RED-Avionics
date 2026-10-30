#include "Csv_Tab.h"
#include "Connector.h"
#include "CSVProcessor.h"

#include <QString>
#include <QLabel>
#include <QPalette>
#include <QDir>
#include <QDebug>
#include <QStringList>
#include <QVBoxLayout>
#include <QFormLayout>
#include <QGroupBox>
#include <QSpacerItem>

Csv_Tab::Csv_Tab(QWidget *parent) : QWidget(parent) {
    // Window properties
    setWindowTitle("Configure Test Run");
    //QPalette palette = this->palette();
    //palette.setColor(QPalette::Window, Qt::gray);
    //this->setPalette(palette);
    //this->setAutoFillBackground(true);

    // Layout Setup
    QVBoxLayout *mainLayout = new QVBoxLayout(this);  // Main vertical layout
    QFormLayout *formLayout = new QFormLayout();      // Form style layout for input fields
    QHBoxLayout *buttonLayout = new QHBoxLayout();    // Horizontal layout for buttons



    csv_options = new QComboBox(this);
    delay = new QComboBox(this);
    run = new QPushButton("Run", this);

    csv_options->setMaximumWidth(200);
    delay->setMaximumWidth(100);
    run->setMaximumWidth(100);

    formLayout->addRow("Test Data:", csv_options);
    formLayout->addRow("Delay (ms):", delay);


    buttonLayout->addWidget(run);

    // ad to the main layout
    mainLayout->addStretch();
    mainLayout->addLayout(formLayout);
    mainLayout->addSpacing(10);
    mainLayout->addLayout(buttonLayout);
    mainLayout->addStretch();

    // Set layout
    setLayout(mainLayout);

    //this->layout->addWidget(exit, 2, 0);
    this->connector = nullptr;
    this->CSV = nullptr;
    //csv_options
    QString dirPath = "Data";
    QDir dir(dirPath);
    if (!dir.exists()) {
        qWarning() << "Directory" << dirPath << "does not exist.";
        return;
    }else{
        QStringList files = dir.entryList(QStringList() << "*.csv", QDir::Files);
        //qDebug() << files;
        for(const QString& file : files){
            this->csv_options->addItem(file);
        }
    
    }
    // Delay options
    QStringList delay_options = {"50", "100", "150", "200", "300", "400"};
    for(const QString& option : delay_options){
        this->delay->addItem(option);
    }
    //run config
    QObject::connect(this->run, &QPushButton::clicked, this, &Csv_Tab::run_slot);


    //connect to gui
    //  const QString PORT = "/dev/Virtual_Teensy";
    //  const int BAUD = 115200;



    //  connector = new Connector(PORT, BAUD, this);
    //  ser = connector->connect();
    
}

void Csv_Tab::run_slot(){
    if (this->CSV) {
        delete this->CSV;
    }

    QString selected_csv = + "Data/" + this->csv_options->currentText();
    int selected_delay = this->delay->currentText().toInt();
    qDebug()<< "running with: "<< selected_csv <<" Baud Rate: "<< selected_delay;
    this->CSV = new CSVProcessor(selected_csv, selected_delay, this);
    QObject::connect(this->CSV, &CSVProcessor::new_pressure, this, &Csv_Tab::write_data);
    this->CSV->readCSV();

}


void Csv_Tab::write_data(QString line){
    qDebug() << line;
    line += "\r\n";
    //ser->write(line.toUtf8());
}

void Csv_Tab::pause() {
    if (CSV) {
        disconnect(CSV, &CSVProcessor::new_pressure, this, &Csv_Tab::write_data);
    }
}

void Csv_Tab::start() {
    if (CSV) {
        connect(CSV, &CSVProcessor::new_pressure, this, &Csv_Tab::write_data);
    }
}