#include "VTMain_window.h"
#include "Csv_Tab.h"
#include "Virtual_Teensy.h"

#include <QStringList>
#include <QTabWidget>
#include <QSettings>
#include <QDebug>
#include <QVBoxLayout>
VTMain_window::VTMain_window(): QMainWindow(), config(nullptr) {

    QWidget *central_widget = new QWidget(this);
    this->setCentralWidget(central_widget);
    
    this->layout = new QGridLayout(central_widget);
    this->tab_widget = new QTabWidget(central_widget);
    
    // Set window size
    this->setFixedSize(600, 800);
    
    // Configure layout stretching
    layout->setRowStretch(0, 1);  // Vertical stretch
    layout->setColumnStretch(0, 1); // Horizontal stretch
    
    tab_widget->setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Expanding);
    this->layout->addWidget(tab_widget, 0, 0, 1, 1);

    //config
    QFile file("Assets/main.cfg");
    if (file.open(QIODevice::ReadOnly  | QIODevice::Text)) {
        QTextStream in(&file);
        this->config = new QFile(in.readLine());
        file.close();
    } else {
        cout << "Could not open main.cfg" << endl;
    }

    //load_config(this->tab_widget);
    tab_widget->addTab(new Virtual_Teensy(50, this->config), tr("Manual mode"));
    tab_widget->addTab(new Csv_Tab(this), tr("Csv mode"));

    connect(tab_widget, &QTabWidget::currentChanged, this, &VTMain_window::onTabChange);

    
}

void VTMain_window::onTabChange(int tab){

    Virtual_Teensy* teensyTab = qobject_cast<Virtual_Teensy*>(tab_widget->widget(0));
    Csv_Tab* csvTab = qobject_cast<Csv_Tab*>(tab_widget->widget(1));
    if (teensyTab) {
        if (tab == 0) {
            teensyTab->start(); // Resume Virtual Teensy operations
        } else {
            teensyTab->pause(); // Pause Virtual Teensy operations
        }
    }

    if (csvTab) {
        if (tab == 1) {
            csvTab->start(); // Resume CSV processing
        } else {
            csvTab->pause(); // Pause CSV processing
        }
    }
}


// void VTMain_window::load_config(QTabWidget *tab_widget) {
//     QSettings settings("Assets/main.cfg", QSettings::IniFormat);
//     settings.beginGroup("Tabs");
//     QStringList keys = settings.allKeys();
    
//     for (const QString &key : keys) {
//         QString tab_name = settings.value(key).toString();
//         QWidget *tab = new QWidget(this);
        
//         // Add a layout to each tab's widget
//         QVBoxLayout *tabLayout = new QVBoxLayout(tab);
//         tabLayout->setContentsMargins(0, 0, 0, 0); // Remove margins
        
//         // Add a stretchable spacer to fill space
//         tabLayout->addStretch();
        
//         tab_widget->addTab(tab, tab_name);
//     }
//     settings.endGroup();
// }