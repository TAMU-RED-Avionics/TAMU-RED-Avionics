#include "VT_Main_Window.h"
#include <QTextStream>
#include <QWidget>
#include <QString>
#include <QLabel>
#include <QMenu>
#include <QDir>
#include <Qt>

// For testing only
#include<iostream>
using std::cout;
using std::endl;

/*
    Initializes the Main Window for the VT.
*/
VT_Main_Window::VT_Main_Window():
    QMainWindow(), layout(new QGridLayout()), vt(nullptr), configuration(nullptr) {
    // Sets the initial size of the VT
    //this->manual_resize(320, 150);

    this->layout->setContentsMargins(2, 2, 2, 2);
    this->layout->setSpacing(10);

    // Load the main config file to add the configuration and theme
    QFile file("Assets/main.cfg");
    if (file.open(QIODevice::ReadOnly  | QIODevice::Text)) {
        QTextStream in(&file);
        this->configuration = new QFile(in.readLine());
        file.close();
    } else {
        cout << "Could not open main.cfg" << endl;
    }

    // Create and attach the virtual teensy
    this->vt = new Virtual_Teensy(50, this->configuration);
    this->layout->addWidget(this->vt, 0, 0);

    // Creates a dummy widget to hold the layout and attach to the window
    QWidget* w = new QWidget();
    w->setLayout(layout);
    this->setCentralWidget(w);
}

void VT_Main_Window::closeEvent(QCloseEvent* event) {
    // Trigger the shutdown of the virtual teensy
    delete this->vt;

    // Accept the event (close the program)
    event->accept();
}

void VT_Main_Window::contextMenuEvent(QContextMenuEvent* event) {
    // Create outer menu
    QMenu* menu =  new QMenu(this);

    // Search the directory of configurations for all files, sort alphabetically
    QDir configurations("Assets");
    configurations.setFilter(QDir::Files);
    configurations.setSorting(QDir::Name);
    QStringList configuration_list = configurations.entryList();

    // Add all items to the menu, besides main.cfg
    for (int i = 0; i < configuration_list.size(); ++i) {
        QString name = configuration_list[i];
        if (!name.contains(".cfg") || "main.cfg" == name) {
            continue;
        }

        QAction* cur_configuration = new QAction(name);
        cur_configuration->setCheckable(true);
        menu->addAction(cur_configuration);

        // If the configuration is already selected, indicate and disable it
        if (this->configuration->fileName().contains(name)) {
            cur_configuration->setChecked(true);
            cur_configuration->setDisabled(true);
        }
    }

    // Connect the menu to the slot to update the configuration
    QObject::connect(menu, SIGNAL(triggered(QAction*)), this, SLOT(set_configuration(QAction*)));

    // Execute the menu loop at the location of the event
    menu->exec(event->globalPos());
}

void VT_Main_Window::set_configuration(QAction* configuration) {
    // Need to delete vt before changing the config file so that it overwrites the old, not the new
    delete this->vt;
    this->configuration->setFileName("Assets/" + configuration->text());

    // Load the main config file to overwrite the configuration and theme
    QFile file("Assets/main.cfg");
    if (file.open(QIODevice::WriteOnly  | QIODevice::Text)) {
        QTextStream out(&file);
        out << this->configuration->fileName() << endl;
        file.close();
    } else {
        cout << "Could not open main.cfg" << endl;
    }
    this->vt = new Virtual_Teensy(50, this->configuration);
    this->layout->addWidget(this->vt, 0, 0);
}
