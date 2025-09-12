#include "GUI_Main_Window.h"
#include "GUI_COM_Window.h"
#include <QTextStream>
#include <QMessageBox>
#include <QPalette>
#include <QWidget>
#include <QPixmap>
#include <QString>
#include <QMenu>
#include <Qt>

// For testing only
#include<iostream>
using std::cout;
using std::endl;

/*
    Initializes the Main Window for the GUI.
*/
GUI_Main_Window::GUI_Main_Window():
    QMainWindow(), enable_shutdown_confirmation(true),
    logo(new QLabel()), layout(new QGridLayout()), com_menu(nullptr),
    theme(nullptr), configuration(nullptr) {
    // Sets the initial size of the GUI
    this->manual_resize(320, 150);

    this->layout->setContentsMargins(2, 2, 2, 2);
    this->layout->setSpacing(10);

    // Load the main config file to add the configuration and theme
    QFile file("Assets/main.cfg");
    if (file.open(QIODevice::ReadOnly  | QIODevice::Text)) {
        QTextStream in(&file);
        this->theme = new QFile(in.readLine());
        this->configuration = new QDir(in.readLine());
        file.close();
    } else {
        cout << "Could not open main.cfg" << endl;
    }

    // Load the theme from the file
    this->update_theme();

    // TODO: Two versions of the logo for light/dark mode.
    // RED Logo:
    this->logo->setPixmap(QPixmap("Assets/RED_logo.png"));
    this->logo->setAlignment(Qt::AlignLeft | Qt::AlignVCenter);
    this->logo->setMaximumHeight(30);
    this->layout->addWidget(this->logo, 0, 0);

    // Create the COM Window
    this->com_menu = new GUI_COM_Window(this);

    // Creates a dummy widget to hold the layout and attach to the window
    QWidget* w = new QWidget();
    w->setLayout(layout);
    this->setCentralWidget(w);
}


/*
    Public functions
*/

QDir* GUI_Main_Window::get_configuration() {
    return this->configuration;
}

void GUI_Main_Window::add_to_main_window(QWidget* widget, int row, int col, int row_span, int col_span) {
    this->layout->addWidget(widget, row, col, row_span, col_span);
}

void GUI_Main_Window::remove_from_main_window(QWidget* widget) {
    this->layout->removeWidget(widget);
}

void GUI_Main_Window::manual_resize(int width, int height) {
    // Prevents the window from moving, but doesn't actually resize it
    this->setGeometry(this->x()+32, this->y()+32, width, height);

    // Changes the size, but will move the window without the previous command
    // Does not lock the window, for some reason
    this->setFixedSize(width, height);
}

/*
    Private functions
*/

void GUI_Main_Window::closeEvent(QCloseEvent* event) {
    // If you are not connected to the Teensy, no confirmation needed
    if (!this->com_menu || !this->com_menu->get_is_connected()) {
        delete this->com_menu;
        event->accept();
        return;
    }

    QMessageBox::StandardButton confirmation = QMessageBox::Apply;
    if (this->enable_shutdown_confirmation) {
        confirmation = QMessageBox::warning(this, "Confirmation", "Are you sure you want to exit the GUI?",
                        QMessageBox::Cancel | QMessageBox::Apply);
    }

    if (QMessageBox::Apply == confirmation) {
        delete this->com_menu;
        event->accept();
    } else {
        event->ignore();
    }
}

void GUI_Main_Window::contextMenuEvent(QContextMenuEvent* event) {
    // Create outer menu
    QMenu menu(this);

    // Search the directory of themes for all files, sort alphabetically
    QDir themes("Assets/visual_themes");
    themes.setFilter(QDir::Files);
    themes.setSorting(QDir::Name);
    QStringList theme_list = themes.entryList();

    // Construct a submenu listing each theme option
    QMenu* theme_menu = menu.addMenu(tr("Theme"));
    for (int i = 0; i < theme_list.size(); ++i) {
        QString name = theme_list[i];
        QAction* cur_theme = new QAction(name);
        cur_theme->setCheckable(true);

        theme_menu->addAction(cur_theme);

        // Check if the current theme is the already selected theme to indicate and disable it
        if (this->theme->fileName().contains(name)) {
            cur_theme->setChecked(true);
            cur_theme->setDisabled(true);
        }
    }

    // Connect the theme submenu to the slot to update the theme
    QObject::connect(theme_menu, SIGNAL(triggered(QAction*)), this, SLOT(set_theme(QAction*)));

    // Search the directory of configurations for all directories (excluding . and ..), sort alphabetically
    QDir configurations("Assets/configurations");
    configurations.setFilter(QDir::Dirs | QDir::NoDotAndDotDot);
    configurations.setSorting(QDir::Name);
    QStringList configuration_list = configurations.entryList();

    // Construct a submenu lisint each configuration option
    QMenu* configuration_menu = menu.addMenu(tr("Configuration"));
    for (int i = 0; i < configuration_list.size(); ++i) {
        QString name = configuration_list[i];
        QAction* cur_configuration = new QAction(name);
        cur_configuration->setCheckable(true);
        configuration_menu->addAction(cur_configuration);

        if (this->configuration->dirName().contains(name)) {
            cur_configuration->setChecked(true);
            cur_configuration->setDisabled(true);
        }
    }

    // Connect the theme submenu to the slot to update the theme
    QObject::connect(configuration_menu, SIGNAL(triggered(QAction*)), this, SLOT(set_configuration(QAction*)));

    // Execute the menu loop at the location of the event
    menu.exec(event->globalPos());
}

void GUI_Main_Window::update_config(bool is_theme_change) {
    // Load the main config file to overwrite the configuration and theme
    QFile file("Assets/main.cfg");
    if (file.open(QIODevice::WriteOnly  | QIODevice::Text)) {
        QTextStream out(&file);
        out << this->theme->fileName() << '\n';
        out << this->configuration->path() << '\n';
        file.flush();
        file.close();
    } else {
        cout << "Could not open main.cfg" << endl;
    }

    // Inform the com_menu of the change, which will regenerate the bottom windows, if needed
    if (!is_theme_change) {
        com_menu->update_config();
    }
}

void GUI_Main_Window::update_theme() {
    // Load the theme from the file and set it to this window (and thus to all descendants)
    if (this->theme->open(QIODevice::ReadOnly | QIODevice::Text)) {
        QTextStream theme_in(this->theme);
        this->setStyleSheet(theme_in.readAll());
        this->theme->close();
    } else {
        cout << "Could not open theme: " << this->theme->fileName().toStdString() << endl;
    }
}

void GUI_Main_Window::set_theme(QAction* theme) {
    this->theme->setFileName("Assets/visual_themes/" + theme->text());

    // Auto update the main.cfg file to default to last selected theme
    this->update_config(true);

    // Load the new theme
    this->update_theme();
}

void GUI_Main_Window::set_configuration(QAction* configuration) {
    this->configuration->setPath("Assets/configurations/" + configuration->text());

    // Auto update the main.cfg file to default to last selected configuration
    this->update_config(false);
}
