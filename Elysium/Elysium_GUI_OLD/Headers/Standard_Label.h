#ifndef Standard_Label_H
#define Standard_Label_H

#include <QLabel>
#include <QGridLayout>


class Standard_Label : public QLabel {
    Q_OBJECT
public:
    // Inherits the constructors (default, paramterized, copy, and move) from the base class
    using QLabel::QLabel;
    Standard_Label(const QString& text, QGridLayout* layout, int row);
};

#endif