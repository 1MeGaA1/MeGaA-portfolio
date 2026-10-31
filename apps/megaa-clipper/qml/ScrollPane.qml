import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "."

// Vertical scrolling column for inspector tabs: children go into a padded ColumnLayout.
Flickable {
    id: pane
    default property alias content: column.data
    property alias spacing: column.spacing
    clip: true
    contentWidth: width
    contentHeight: column.implicitHeight + 28
    boundsBehavior: Flickable.StopAtBounds
    ScrollBar.vertical: NeonScrollBar {}

    ColumnLayout {
        id: column
        x: 14
        y: 10
        width: pane.width - 28
        spacing: 18
    }
}
