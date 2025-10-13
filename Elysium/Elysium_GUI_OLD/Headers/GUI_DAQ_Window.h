#ifndef GUI_DAQ_Window_H
#define GUI_DAQ_Window_H

#include "GUI_Main_Window.h"
#include "Sensor.h"
#include <QSerialPort>
#include <QStringList>
#include <QPushButton>
#include <QTimer>

// Forward decleration to avoid circular dependencies
class GUI_Graph_Window;

// Number of milliseconds to notify the user that no new data has arrived
// Not a definition to avoid multiply defined objects with all files that include this header
// Defined in the .cpp file
extern const int CHECK_CONNECTION_INTERVAL;

class GUI_DAQ_Window : public QWidget {
    Q_OBJECT
public:
    // Inherits the constructors (default, paramterized, copy, and move) from the base class
    // The parameterized constructor and destructor will be overwritten in the source file
    using QWidget::QWidget;
    GUI_DAQ_Window(GUI_Main_Window* parent, QSerialPort* ser);
    ~GUI_DAQ_Window();

    QHash<QString, double>* get_data();

private:
    GUI_Main_Window* root;
    QSerialPort* ser;

    QHash<QString, Sensor*> sensors;
    QStringList derived_IDs;
    QString teensy_time;
    QHash<QString, double>* data;

    bool is_saving;
    QFile* data_file;
    QPushButton* start_save_btn;
    QPushButton* end_save_btn;
    QTimer* check_connection_timer;

    GUI_Graph_Window* graphs;

    void update_derived(const QString& ID);

private slots:
    void update_sensors();
    void start_save();
    void end_save();
    void save();
    void connection_failed();

signals:
    void new_data();
};


#endif