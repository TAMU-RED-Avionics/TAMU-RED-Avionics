#include "State_Machine.h"
#include <QTimer>
#include <QDateTime>

// For Testing only
#include <iostream>
using std::cout;
using std::endl;

// Constants (user set parameters)
// Number of milliseconds that the ignition system should be delayed
const int PURGE_DELAY = 0;

// Number of milliseconds that the ignition system should be delayed (from main valves open)
const int IGNITION_DELAY = 150;

// Number of milliseconds that the second ignition system should be delayed (from first ignition system)
const int IGNITION_2_DELAY = 0;

// Number of milliseconds that the pre-fire and post-fire purges should last
const int PURGE_DURATION = 0;

// Number of milliseconds that Fire Ph. 2 should last (plan for main valves open for 6000 ms)
const int FIRE_DURATION = 6000 - (IGNITION_DELAY + IGNITION_2_DELAY);

// Number of milliseconds that a negative pressure gradient must be sustained before an abort
const int APG_ABORT_DURATION = 200;

// Number of milliseconds that the before purge to allow for T-10 countdown
const int SEQUENCE_DELAY = 10000 - (PURGE_DURATION + PURGE_DELAY + IGNITION_DELAY);

// Constructor
State_Machine::State_Machine(QString name, QHash<QString, double>* data):
    config_name(name), cur_state("Fully Closed"), people_safe_dist(false),
    cur_allowed_states(new QStringList()), cur_data(data), auto_aborts_enabled(true),
    apg_times(new QList<int>()) {
    // If the system autonomously updates the state, it should update the change the same as a manual update
    QObject::connect(this, SIGNAL(new_state(QString)), this, SLOT(set_state(QString)));

    // Initialize the apg times to 0
    for (size_t i = 0; i < 7; ++i) {
        this->apg_times->append(0);
    }
}

void State_Machine::start() {
    cout << "State Machine Startup" << endl;
    // Set Initial State (cannot do in constructor because it needs external connections)
    if ("hotfire_1" == this->config_name) {
        emit new_state("Fully Closed");
    } else {
        cout << "State Machine: Unknown configuration: " << this->config_name.toStdString() << endl;
    }
}

void State_Machine::hotfire_1(bool new_state, bool abort) {
    // Determine what states should be allowed, given the current state and safety
    QStringList new_allowed_states = {};

    // Handle aborts first: 2 cases
    if (abort) {
        // If the main ball valves are open, do a purge
        if (("Fire Ph. 1" == this->cur_state) || ("Fire Ph. 2" == this->cur_state) || ("Main Valves Open" == this->cur_state)) {
            this->cur_state = "Shutdown Ph. 1";
        
        // Otherwise, go straight to non-purge shutdown procedure
        } else {
            this->cur_state = "Shutdown Ph. 2";
        }

        // Notify the CTRL Window of the abort decision
        emit this->new_state(this->cur_state);
    }

    // Consider each state and failure mode
    if        ("Fully Closed"           == this->cur_state) {
        // The fill state and Pre-pressurization are safe to open
        new_allowed_states << "Filling" << "Pre-Pressurization";
        new_allowed_states << "Shutdown Ph. 2"; // Non-emergency abort

        // Personnel must be at a safe distance before advancing
        if (this->people_safe_dist) {
            new_allowed_states << "Letting GN2 In";
        }

    } else if ("Letting GN2 In"         == this->cur_state) {
        // In this state, it is safe to back to the closed state
        new_allowed_states << "Fully Closed";

        // Personnel must be at a safe distance before advancing
        if (this->people_safe_dist) {
            new_allowed_states << "Hold Pressure";
            new_allowed_states << "Shutdown Ph. 2"; // Non-emergency abort
        }

    } else if ("Hold Pressure"          == this->cur_state) {
        // Personnel must be at a safe distance before changing the state
        if (this->people_safe_dist) {
            new_allowed_states << "Letting GN2 In"; // Return to previous state
            new_allowed_states << "Dry Run";        // Advance
            new_allowed_states << "Shutdown Ph. 2"; // Non-emergency abort
        }
    
    } else if ("Dry Run"                == this->cur_state) {
        // Fully closed/returning to Hold Pressure are not allowed states
        // due to possible fluid hammer when closing LA-BV 1
        // The filling state is identical to the abort state.
        new_allowed_states << "Filling";
    
    } else if ("Filling"                == this->cur_state) {
        // Closing the venting/fill valve is safe
        new_allowed_states << "Fully Closed" << "Pre-Pressurization" << "Shutdown Ph. 2";
    
    } else if ("Pre-Pressurization"     == this->cur_state) {
        // This state is safe (identical to fully closed)
        new_allowed_states << "Fully Closed";
        new_allowed_states << "Filling";        // Revert to previous state
        new_allowed_states << "Shutdown Ph. 2"; // Non-emergency abort

        // Personnel must be at a safe distance before changing the state
        if (this->people_safe_dist) {
            new_allowed_states << "Pressurization"; // Advance
        }
    
    } else if ("Pressurization"         == this->cur_state) {
        // TODO: Consider blocking Terminal Count unless relevant pressure > UNDER_PRESSURE

        // Personnel must be at a safe distance before changing the state
        if (this->people_safe_dist) {
            new_allowed_states << "Pre-Pressurization"; // Return to previous state
            new_allowed_states << "Terminal Count";     // Advance
            new_allowed_states << "Shutdown Ph. 2";     // Non-emergency abort
        }
    
    } else if ("Terminal Count"         == this->cur_state) {
        // TODO: Consider blocking Purge unless relevant pressure > UNDER_PRESSURE

        // Personnel must be at a safe distance before changing the state
        if (this->people_safe_dist) {
            new_allowed_states << "Pressurization";     // Return to previous state
            new_allowed_states << "Purge";              // Advance
            new_allowed_states << "Shutdown Ph. 2";     // Non-emergency abort
        }

        // Once this state is reached, after SEQUENCE_DELAY, move to purge shutdown
        if (new_state) {
            QTimer* delay = new QTimer(this);
            delay->setTimerType(Qt::PreciseTimer);
            delay->setSingleShot(true);
            QObject::connect(delay, &QTimer::timeout, this, [this]() {emit this->new_state("Purge");});
            
            // If the state is changed, the timer should stop to prevent multiple state changes.
            QObject::connect(this, SIGNAL(new_state(QString)), delay, SLOT(stop()));
            delay->start(SEQUENCE_DELAY);
        }

    } else if ("Purge"                  == this->cur_state) {
        // Terminal sequence (no returning to previous state)
        // Personnel must be at a safe distance before changing the state
        if (this->people_safe_dist) {
            new_allowed_states << "Purge Shutdown"; // Advance
            new_allowed_states << "Shutdown Ph. 2"; // Non-emergency abort
        }

        // Once this state is reached, after PURGE_DURATION, move to purge shutdown
        if (new_state) {
            QTimer* purge = new QTimer(this);
            purge->setTimerType(Qt::PreciseTimer);
            purge->setSingleShot(true);
            QObject::connect(purge, &QTimer::timeout, this, [this]() {emit this->new_state("Purge Shutdown");});
            
            // If the state is changed, the timer should stop to prevent multiple state changes.
            QObject::connect(this, SIGNAL(new_state(QString)), purge, SLOT(stop()));
            purge->start(PURGE_DURATION);
        }

    } else if ("Purge Shutdown"         == this->cur_state) {
        // Terminal sequence (no returning to previous state)
        // Personnel must be at a safe distance before changing the state
        if (this->people_safe_dist) {
            new_allowed_states << "Main Valves Open";   // Advance
            new_allowed_states << "Shutdown Ph. 2";     // Non-emergency abort
        }

        // Once this state is reached, after PURGE_DELAY, move to main valves open
        if (new_state) {
            QTimer* main_valves = new QTimer(this);
            main_valves->setTimerType(Qt::PreciseTimer);
            main_valves->setSingleShot(true);
            // See GUI_CTRL_Window for lambda function example (near bottom of contructor)
            QObject::connect(main_valves, &QTimer::timeout, this, [this]() {emit this->new_state("Main Valves Open");});

            // If the state is changed, the timer should stop to prevent multiple state changes.
            QObject::connect(this, SIGNAL(new_state(QString)), main_valves, SLOT(stop()));
            main_valves->start(PURGE_DELAY);
        }
    
    } else if ("Main Valves Open"       == this->cur_state) {
        // Terminal sequence (no returning to previous state)
        // This state change makes the system safer, so while there should be no one near the engine,
        // the button should never be disabled.

        new_allowed_states << "Shutdown Ph. 1";     // Non-emergency abort
        // Personnel must be at a safe distance before changing the state
        if (this->people_safe_dist) {
            new_allowed_states << "Fire Ph. 1";               // Advance
        }

        // Once this state is reached, after IGNITION_DELAY, move to fire
        if (new_state) {
            QTimer* ignition = new QTimer(this);
            ignition->setTimerType(Qt::PreciseTimer);
            ignition->setSingleShot(true);
            // See GUI_CTRL_Window for lambda function example (near bottom of contructor)
            QObject::connect(ignition, &QTimer::timeout, this, [this]() {emit this->new_state("Fire Ph. 1");});

            // If the state is changed, the timer should stop to prevent multiple state changes.
            QObject::connect(this, SIGNAL(new_state(QString)), ignition, SLOT(stop()));
            ignition->start(IGNITION_DELAY);
        }
    
    } else if ("Fire Ph. 1"             == this->cur_state) {
        // TODO: Consider skipping (straight to Shutdown Ph. 2) if relevant pressure < UNDER_PRESSURE

        // Terminal sequence (no returning to previous state)
        // This state change makes the system safer, so while there should be no one near the engine,
        // the button should never be disabled.
        new_allowed_states << "Shutdown Ph. 1"; // Abort

        // Personnel must be at a safe distance before changing the state
        if (this->people_safe_dist) {
            new_allowed_states << "Fire Ph. 2";               // Advance
        }

        // Once this state is reached, after FIRE_DURATION, move to shutdown ph 1
        if (new_state) {
            QTimer* ignition_2 = new QTimer(this);
            ignition_2->setTimerType(Qt::PreciseTimer);
            ignition_2->setSingleShot(true);
            QObject::connect(ignition_2, &QTimer::timeout, this, [this]() {emit this->new_state("Fire Ph. 2");});

            // If the state is changed, the timer should stop to prevent multiple state changes.
            QObject::connect(this, SIGNAL(new_state(QString)), ignition_2, SLOT(stop()));
            ignition_2->start(IGNITION_2_DELAY);
        }
    
    } else if ("Fire Ph. 2"             == this->cur_state) {
        // Terminal sequence (no returning to previous state)
        // This state change makes the system safer, so while there should be no one near the engine,
        // the button should never be disabled.
        new_allowed_states << "Shutdown Ph. 1"; // Advance (and abort)

        // Once this state is reached, after FIRE_DURATION, move to shutdown ph 1
        if (new_state) {
            QTimer* fire = new QTimer(this);
            fire->setTimerType(Qt::PreciseTimer);
            fire->setSingleShot(true);
            QObject::connect(fire, &QTimer::timeout, this, [this]() {emit this->new_state("Shutdown Ph. 1");});

            // If the state is changed, the timer should stop to prevent multiple state changes.
            QObject::connect(this, SIGNAL(new_state(QString)), fire, SLOT(stop()));
            fire->start(FIRE_DURATION);
        }
    
    } else if ("Shutdown Ph. 1"         == this->cur_state) {
        // Shutdown sequence (no returning to previous state)
        if (this->people_safe_dist) {
            new_allowed_states << "Shutdown Ph. 2"; // Advance (continue safing procedure)
        }

        // Once this state is reached, after PURGE_DURATION, move to shutdown ph 2
        if (new_state) {
            QTimer* purge = new QTimer(this);
            purge->setTimerType(Qt::PreciseTimer);
            purge->setSingleShot(true);
            QObject::connect(purge, &QTimer::timeout, this, [this]() {emit this->new_state("Shutdown Ph. 2");});

            // If the state is changed, the timer should stop to prevent multiple state changes.
            QObject::connect(this, SIGNAL(new_state(QString)), purge, SLOT(stop()));
            purge->start(PURGE_DURATION);
        }
    
    } else if ("Shutdown Ph. 2"         == this->cur_state) {
        // Shutdown sequence (no returning to previous state)
        if (this->people_safe_dist) {
            new_allowed_states << "Excess Discharge Ph. 1"; // Advance (continue safing procedure)
            new_allowed_states << "Fully Closed";           // Return to start (if early abort)
        }
    
    } else if ("Excess Discharge Ph. 1" == this->cur_state) {
        // Shutdown sequence (no returning to previous state)
        if (this->people_safe_dist) {
            new_allowed_states << "Excess Discharge Ph. 2"; // Advance (continue safing procedure)
        }
    
    } else if ("Excess Discharge Ph. 2" == this->cur_state) {
        // Final shutdown step, can revert to fully closed (power off), if desired
        new_allowed_states << "Fully Closed";
    
    } else {
        cout << "State Machine: Unknown Current State: " << this->cur_state.toStdString() << endl;
    }

    // check if the allowed states are different the last emitted ones
    bool are_equal = new_allowed_states.size() == this->cur_allowed_states->size();
    if (are_equal) {
        for (int i = 0; i < new_allowed_states.size(); ++i) {
            if (new_allowed_states.at(i) != this->cur_allowed_states->at(i)) {
                are_equal = false;
                break;
            }
        }
    }

    // If the states are new, update the variable and emit a new signal
    if (!are_equal) {
        *(this->cur_allowed_states) = new_allowed_states;
        emit allowed_states(this->cur_allowed_states);
    }
}

void State_Machine::set_state(QString state) {
    if ("ABORT" == state) {
        this->update_signals(true, true);
    } else {
        this->cur_state = state;
        this->update_signals(true, false);
    }
}

void State_Machine::set_people_safe_dist(int safe) {
    this->people_safe_dist = Qt::Checked == safe;
    this->update_signals(false);
}

void State_Machine::new_data() {
    // Only abort if aborts are enabled
    if (!this->auto_aborts_enabled) {
        // Set the timers to 0, so it doesn't instantly trigger when set
        for (int i = 0; i < this->apg_times->size(); ++i) {
            this->apg_times->replace(i, 0);
        }
        
        // Do not continue to check
        return;
    }
    
    // Only abort from "Main Valves Open" or "Fire"-based states
    if ("Main Valves Open" == this->cur_state || "Fire Ph. 1" == this->cur_state || "Fire Ph. 2" == this->cur_state) {
        try {
            // Access relevant data
            double p1 = this->cur_data->value("P1");
            double p2 = this->cur_data->value("P2");
            double p3 = this->cur_data->value("P3");
            double p4 = this->cur_data->value("P4");
            double p5 = this->cur_data->value("P5");

            // Variable to store if any of the checks fail
            bool shutdown = false;
            int time = QDateTime::currentMSecsSinceEpoch();
            
            
            if (p4 > (p2 - 15)) {
                if (0 == this->apg_times->at(2)) {
                    this->apg_times->replace(2, time);
                } else if ((time - this->apg_times->at(2)) > APG_ABORT_DURATION) {
                    shutdown = true;
                } 
            } else {
                this->apg_times->replace(2, 0);
            }
            
            // Oxidizer injector inlet vs oxidizer tank
            
            if (p3 > (p1 - 15)) {
                if (0 == this->apg_times->at(3)) {
                    this->apg_times->replace(3, time);
                } else if ((time - this->apg_times->at(3)) > APG_ABORT_DURATION) {
                    shutdown = true;
                }
            } else {
                this->apg_times->replace(3, 0);
            }
            
            // Fuel tank vs upper line pressure
            if (p2 > (p5 + 10)) {
                if (0 == this->apg_times->at(4)) {
                    this->apg_times->replace(4, time);
                } else if ((time - this->apg_times->at(4)) > APG_ABORT_DURATION) {
                    shutdown = true;
                }
            } else {
                this->apg_times->replace(4, 0);
            }

            

            // Immediately shutdown if any case is confirmed
            if (shutdown) {
                emit new_state("Shutdown Ph. 1");
                return;
            }
        } catch (...) {
            cout << "Could not access data: (Pressure)" << endl;
        }
    } else {
        // If we are not in either of the abort-capable states, the timers should be set to 0.
        for (int i = 0; i < this->apg_times->size(); ++i) {
            this->apg_times->replace(i, 0);
        }
    }


    //////////////
    // Outdated //
    //////////////

    // TODO: Consider Overpressure during Pressurization - Fire. (check PT resolution, FSYS).
    // TODO: Figure out a filter/way of better checking P4.
    // It is in the injector manifold, so when fire is called, it should be ambient (<<< UNDER_PRESSURE)
    // Maybe check if it has been higher than UNDER_PRESSURE, then dropped below?

    // During the fire state, check if the fuel side has dropped in pressure below the cutoff.
    /*
    if ("Fire" == this->cur_state) {
        try {
            double p4 = this->cur_data->value("P4");
            if (p4 <= UNDER_PRESSURE) {
                // Immediatetly shutdown if underpressure is detected
                emit new_state("Shutdown Ph. 1");
                return;
            }
        } catch (...) {
            cout << "Could not access data with ID: P4" << endl;
        }
    }
    */
}

void State_Machine::update_signals(bool new_state, bool abort) {
    if ("hotfire_1" == this->config_name) {
        this->hotfire_1(new_state, abort);
    } else {
        cout << "State Machine: Unknown configuration: " << this->config_name.toStdString() << endl;
    }
}

void State_Machine::set_auto_aborts_enabled(int enabled) {
    this->auto_aborts_enabled = (Qt::Checked == enabled);
}
