#ifndef GUI_Main_Window_H
#define GUI_Main_Window_H

#include <QContextMenuEvent>
#include <QMainWindow>
#include <QGridLayout>
#include <QCloseEvent>
#include <QLabel>
#include <QColor>
#include <QFile>
#include <QDir>

// Forward declaration of COM Window to avoid circular dependencies
class GUI_COM_Window;

/*
    The Main Window for the GUI.
    Contains the layout which all major elements are attached to.
*/
class GUI_Main_Window : public QMainWindow {
    Q_OBJECT
public:
    // Inherits the constructors (default, paramterized, copy, and move) from the base class
    // The default will be overwritten in the source file
    using QMainWindow::QMainWindow;
    GUI_Main_Window();

    QDir* get_configuration();
    void add_to_main_window(QWidget* widget, int row, int col, int row_span=1, int col_span=1);
    void remove_from_main_window(QWidget* widget);
    void manual_resize(int width, int height);

private:
    bool enable_shutdown_confirmation;
    QLabel* logo;
    QGridLayout* layout;
    GUI_COM_Window* com_menu;

    QFile* theme;
    QDir* configuration;

    void closeEvent(QCloseEvent* event);
    void contextMenuEvent(QContextMenuEvent* event);
    void update_config(bool is_theme_change);
    void update_theme();

private slots:
    void set_theme(QAction* theme);
    void set_configuration(QAction* configuration);
};


#endif