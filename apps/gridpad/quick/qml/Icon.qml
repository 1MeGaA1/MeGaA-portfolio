import QtQuick

// A stroke icon from the Python provider (the classic edition's drawings).
// Names: grid bold list check tag link plus x search chevron-up chevron-down
//        chevron-left chevron-right sort gear upload download
Image {
    property string name
    property color color: Theme.c.ICON
    property int size: 16

    width: size
    height: size
    sourceSize: Qt.size(size * 2, size * 2)
    source: name ? Theme.icon(name, color) : ""
    fillMode: Image.PreserveAspectFit
    smooth: true
    mipmap: true
}
