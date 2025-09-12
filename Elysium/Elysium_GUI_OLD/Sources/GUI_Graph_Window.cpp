#include "GUI_Graph_Window.h"
#include "Frame_with_Title.h"
#include "GUI_DAQ_Window.h"

// For testing only
#include <QDebug>
#include<iostream>
using std::cout;
using std::endl;

GUI_Graph_Window::GUI_Graph_Window(GUI_Main_Window* parent, GUI_DAQ_Window* daq):
    QWidget(), root(parent), daq(daq) {
    
    // Layout for the graphs
    QGridLayout* bottom_layout = new QGridLayout();
    bottom_layout->setContentsMargins(5, 5, 5, 5);
    bottom_layout->setSpacing(10);

    // Build frame and title for the Graph section
    QFrame* bottom_widget = new QFrame();
    bottom_widget->setLayout(bottom_layout);
    Frame_with_Title* layout = new Frame_with_Title("Live Graphs", bottom_widget);

    // Attach to the main window such that it aligns with all 3 existing windows, in the next column
    this->setLayout(layout);
    this->root->add_to_main_window(this, 1, 1, 3, 1);
}


void GUI_Graph_Window::update_graphs() {

}
