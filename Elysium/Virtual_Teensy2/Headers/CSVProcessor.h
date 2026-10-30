#ifndef CSVPROCESSOR_H
#define CSVPROCESSOR_H

#include <QString>
#include <QWidget>
#include <QObject>

class CSVProcessor : public QWidget{
    Q_OBJECT

public:
    CSVProcessor(const QString& filePath, int delay_ms, QWidget *parent);
    void readCSV();
    void Process_line(const QString& line);
    static void delay(int millisecondsToWait); // isnt chaning across instances
private:
    QString filePath;
    int delay_ms;

signals:
    void new_pressure(const QString &Pressure);
};


#endif

