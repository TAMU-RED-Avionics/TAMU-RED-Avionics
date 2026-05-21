#ifndef State_Machine_H
#define State_Machine_H

#include <QStringList>
#include <QString>
#include <QHash>
#include <QFile>

// Constant Declarations, not definitions to avoid multiply defined objects with all files that include this header
// Defined in the .cpp file
extern const int SEQUENCE_DELAY;
extern const int PURGE_DELAY;
extern const int IGNITION_DELAY;
extern const int IGNITION_2_DELAY;
extern const int PURGE_DURATION;
extern const int FIRE_DURATION;
extern const int APG_ABORT_DURATION;

// ============================================================
// RAGNAROK TORCH IGNITER TEST — delete this block when done
// Timing constants for the Ragnarok Torch Igniter sequence
extern const int RT_ETHANOL_DELAY;   // ms from T+0 to ethanol flow (T+0.25s)
extern const int RT_PURGE_START;     // ms from T+0 to EABV close / purge start (T+1s)
extern const int RT_PURGE_DURATION;  // ms purge lasts before PABV closes (T+2s)
// ============================================================

// TODO: Consider using derived classes for each configuration. Make update_signals() a pure virtual function.
// This class must derive from QObject to use signals/slots
class State_Machine : public QObject {
    Q_OBJECT
public:
    // Constructor
    State_Machine(QString name, QHash<QString, double>* data);
    void start();
private:
    QString config_name;
    QString cur_state;
    bool people_safe_dist;
    QStringList* cur_allowed_states;

    // Pointer to data managed by GUI_DAQ_Window, must be given during initialization
    QHash<QString, double>* cur_data;

    // List of timestamps for autoaborts
    bool auto_aborts_enabled;
    QList<int>* apg_times;

    void hotfire_1(bool new_state, bool abort);

    // ============================================================
    // RAGNAROK TORCH IGNITER TEST — delete this line when done
    void ragnarok_torch_igniter(bool new_state, bool abort);
    // ============================================================
private slots:
    void set_state(QString state);
    void set_people_safe_dist(int safe);
    void new_data();
    void update_signals(bool new_state, bool abort=false);
    void set_auto_aborts_enabled(int enabled);

signals:
    void new_state(QString state);
    void allowed_states(QStringList* allowed_states);
};

#endif