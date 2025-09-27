#include "Frame_with_Title.h"
#include <QLabel>
#include <Qt>

// For testing only
#include<iostream>
using std::cout;
using std::endl;

Frame_with_Title::Frame_with_Title(const QString& title, QFrame* bottom_widget): QVBoxLayout() {
    // Formatting
    this->setContentsMargins(0, 10, 0, 0);
    this->setSpacing(0);

    // Adds the title to a widget aligned to the left side of the top box
    QLabel* title_w = new QLabel();
    title_w->setText(' ' + title);
    title_w->setAlignment(Qt::AlignLeft);
    title_w->setMaximumHeight(15);
    this->addWidget(title_w);

    // Adds a frame around the bottom widget and inserts into the bottom box
    bottom_widget->setFrameShape(QFrame::Box);
    this->addWidget(bottom_widget);
}
