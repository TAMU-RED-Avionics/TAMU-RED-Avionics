#ifndef GUI_Graph_Window_H
#define GUI_Graph_Window_H

#include "GUI_Main_Window.h"

// Forward decleration to avoid circular dependencies
class GUI_DAQ_Window;

class GUI_Graph_Window : public QWidget {
    Q_OBJECT
public:
    // Inherits the constructors (default, paramterized, copy, and move) from the base class
    // The parameterized constructor and destructor will be overwritten in the source file
    using QWidget::QWidget;
    GUI_Graph_Window(GUI_Main_Window* parent, GUI_DAQ_Window* daq);

private:
    GUI_Main_Window* root;
    GUI_DAQ_Window* daq;

    
private slots:
    void update_graphs();
};


#endif