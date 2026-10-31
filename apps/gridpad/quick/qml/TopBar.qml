import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Top bar: logo, "GridPad", file name — then the tag-filter chip, "Check duplicates and sort",
// import / export / settings and the find box. The sort menu lives here (it opens under its
// button); import / export / settings are signals Main.qml answers with its dialogs.
Rectangle {
    id: bar

    property alias search: searchBox

    signal importClicked()
    signal exportClicked()
    signal settingsClicked()
    // A menu of the bar closed and nothing in the bar takes the keyboard back: focus the grid.
    signal refocusRequested()

    property string _chipTag: ""
    property bool _searchHadFocus: false

    Component.onCompleted: bar._chipTag = backend.filterTag

    function openSortMenu() {
        const info = backend.sortMenuInfo()  // also commits an open cell editor
        if (!info.ok)
            return  // the backend flashed "Click a cell inside your data first"
        sortMenu.letter = info.letter
        sortMenu.scope = info.scope
        bar._searchHadFocus = searchBox.inputFocused
        sortMenu.popup(sortButton, 0, sortButton.height + 4)
    }

    implicitHeight: 44
    color: Theme.c.PANEL

    // Keep the chip's text while it fades out after the filter is cleared.
    Connections {
        target: backend
        function onFilterChanged() {
            if (backend.filterTag !== "")
                bar._chipTag = backend.filterTag
        }
    }

    Rectangle {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        height: 1
        color: Theme.c.BORDER
    }

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 14
        anchors.rightMargin: 14
        spacing: 14

        Icon {
            // Icon's implicit size is its 2x sourceSize: pin the layout size to `size`.
            Layout.preferredWidth: 18
            Layout.preferredHeight: 18
            Layout.alignment: Qt.AlignVCenter
            name: "grid"
            color: Theme.c.ACCENT
            size: 18
        }

        Text {
            Layout.alignment: Qt.AlignVCenter
            text: "GridPad"
            font.family: Theme.sans
            font.pixelSize: 15
            font.weight: Theme.wBold
            color: Theme.c.TEXT
        }

        Text {
            Layout.alignment: Qt.AlignVCenter
            Layout.fillWidth: true
            Layout.minimumWidth: 40
            Layout.maximumWidth: implicitWidth
            text: backend.fileName
            textFormat: Text.PlainText
            elide: Text.ElideMiddle
            font.family: Theme.sans
            font.pixelSize: 12
            font.weight: Font.Normal
            color: Theme.c.MUTED
        }

        Item { Layout.fillWidth: true }

        // "Filter: #tag ×" — fades and scales in while a tag filter is on; click clears it.
        AbstractButton {
            id: chip

            readonly property bool shown: backend.filterTag !== ""

            Layout.alignment: Qt.AlignVCenter
            visible: opacity > 0.01
            opacity: chip.shown ? 1 : 0
            scale: chip.shown ? 1 : 0.88
            Behavior on opacity { NumberAnimation { duration: 160; easing.type: Easing.OutCubic } }
            Behavior on scale { NumberAnimation { duration: 200; easing.type: Easing.OutCubic } }

            implicitWidth: chipRow.implicitWidth + 16
            implicitHeight: 24
            focusPolicy: Qt.NoFocus
            hoverEnabled: true
            ToolTip.visible: chip.hovered
            ToolTip.text: "Clear the tag filter (Esc)"
            ToolTip.delay: 600
            onClicked: backend.setFilter("")

            background: Rectangle {
                radius: 4
                color: chip.hovered ? Theme.c.HOVER : Theme.c.TAG_BG
                Behavior on color { ColorAnimation { duration: 90 } }
            }

            contentItem: Item {
                Row {
                    id: chipRow
                    anchors.centerIn: parent
                    spacing: 5
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        text: "Filter: #" + bar._chipTag
                        font.family: Theme.mono
                        font.pixelSize: 12
                        font.weight: Theme.wNormal
                        color: Theme.c.TAG
                    }
                    Icon {
                        anchors.verticalCenter: parent.verticalCenter
                        name: "x"
                        color: Theme.c.TAG
                        size: 14
                    }
                }
            }

            HoverHandler { cursorShape: Qt.PointingHandCursor }
        }

        IconButton {
            id: sortButton
            Layout.alignment: Qt.AlignVCenter
            iconName: "sort"
            text: "Check duplicates and sort"
            tip: "Sort rows, or group duplicate values on top (uses the selected column)"
            checked: sortMenu.visible
            onClicked: bar.openSortMenu()
        }

        IconButton {
            Layout.alignment: Qt.AlignVCenter
            iconName: "upload"
            tip: "Import CSV or text (Ctrl+I) — or drop a file on the window"
            onClicked: bar.importClicked()
        }

        IconButton {
            Layout.alignment: Qt.AlignVCenter
            iconName: "download"
            tip: "Export sheet as CSV or text (Ctrl+E)"
            onClicked: bar.exportClicked()
        }

        IconButton {
            Layout.alignment: Qt.AlignVCenter
            iconName: "gear"
            tip: "Theme and font (Ctrl+,)"
            onClicked: bar.settingsClicked()
        }

        SearchBox {
            id: searchBox
            Layout.alignment: Qt.AlignVCenter
            // 300 wide; near the 900 px minimum window width with the filter chip showing,
            // it gives up to 100 px instead of running off the edge.
            Layout.fillWidth: true
            Layout.minimumWidth: 200
            Layout.preferredWidth: 300
            Layout.maximumWidth: 300
            Layout.preferredHeight: 30
        }
    }

    GPMenu {
        id: sortMenu

        property string letter
        property string scope

        onClosed: {
            if (bar._searchHadFocus)
                searchBox.focusInput()
            else
                bar.refocusRequested()
        }

        GPMenuItem {
            text: "Sort rows A → Z by column " + sortMenu.letter + sortMenu.scope
            onTriggered: backend.sortRows(false)
        }
        GPMenuItem {
            text: "Sort rows Z → A by column " + sortMenu.letter + sortMenu.scope
            onTriggered: backend.sortRows(true)
        }
        GPMenuSeparator { }
        GPMenuItem {
            text: "Check duplicates in column " + sortMenu.letter + sortMenu.scope + " — group them on top"
            onTriggered: backend.groupDuplicates()
        }
        GPMenuItem {
            text: "Delete duplicate rows in column " + sortMenu.letter + sortMenu.scope + " — keep the first"
            onTriggered: backend.dedupe()
        }
    }
}
