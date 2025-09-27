#ifndef GUI_CTRL_Window_H
#define GUI_CTRL_Window_H

#include "GUI_Main_Window.h"
#include "Valves.h"
#include <QStringList>
#include <QSerialPort>
#include <QCheckBox>
#include <QHash>

// TODO: implement
class GUI_CTRL_Window : public QWidget {
    Q_OBJECT
public:
    // Inherits the constructors (default, paramterized, copy, and move) from the base class
    // The parameterized constructor and destructor will be overwritten in the source file
    using QWidget::QWidget;
    GUI_CTRL_Window(GUI_Main_Window* parent, QSerialPort* ser);

private:
    GUI_Main_Window* root;
    QSerialPort* ser;

    QList<Valve*>* valves;
    QLabel* control_state;
    QHash<QString, QHash<QString, int>*> control_states;
    QHash<QString, QPushButton*> operation_btns;

    bool is_saving;
    QFile* data_file;
    QPushButton* start_save_btn;
    QPushButton* end_save_btn;
    QPushButton* abort_btn;

    void update_control_state();

private slots:
    void start_save();
    void end_save();
    void save(const QString& command);
    void new_state(QString state);
    void sm_allowed_states(QStringList* allowed_states);
    void abort();

signals:
    void new_state_signal(QString state);
    void people_safe_dist(int people_safe_dist);
    void auto_aborts_enabled(int auto_aborts_enabled);
};


#endif