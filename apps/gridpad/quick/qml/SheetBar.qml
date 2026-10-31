import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Sheet bar: the sheet tabs (scrolling sideways when there are many), the + button, and the
// three status texts on the right. The current tab's accent line glides between tabs.
// Tabs are kept in a ListModel that is patched in place, so switching or renaming never
// rebuilds the strip (no flicker, no scroll jump).
Rectangle {
    id: bar

    // Delete sheet was chosen: Main.qml confirms first when the sheet has notes.
    signal deleteRequested(int index)
    // A menu of the bar closed: give the keyboard back to the grid.
    signal refocusRequested()

    property int current: 0
    property real _lineX: 0
    property real _lineW: 0
    property real _scrollTarget: 0
    property bool _animate: false

    function syncSheets() {
        const names = backend.sheetNames
        for (let i = 0; i < names.length; ++i) {
            if (i < tabModel.count) {
                if (tabModel.get(i).name !== names[i])
                    tabModel.setProperty(i, "name", names[i])
            } else {
                tabModel.append({ name: names[i] })
            }
        }
        while (tabModel.count > names.length)
            tabModel.remove(tabModel.count - 1)
        bar.current = backend.currentSheet
        Qt.callLater(bar.revealCurrent)
    }

    function syncLine() {
        const item = tabs.currentItem
        if (item) {
            bar._lineX = item.x
            bar._lineW = item.width
        }
    }

    function scrollTabsTo(target) {
        const lo = tabs.originX
        const hi = tabs.originX + Math.max(0, tabs.contentWidth - tabs.width)
        const to = Math.max(lo, Math.min(hi, target))
        bar._scrollTarget = to
        if (Math.abs(to - tabs.contentX) < 0.5) {
            scrollAnim.stop()
            return
        }
        scrollAnim.stop()
        scrollAnim.from = tabs.contentX
        scrollAnim.to = to
        scrollAnim.start()
    }

    // Slide the strip just enough to show the current tab whole.
    function revealCurrent() {
        const item = tabs.itemAtIndex(bar.current)
        if (!item) {
            bar.scrollTabsTo(tabs.contentX)  // re-clamp after tabs were removed
            return
        }
        const left = scrollAnim.running ? bar._scrollTarget : tabs.contentX
        if (item.x < left)
            bar.scrollTabsTo(item.x)
        else if (item.x + item.width > left + tabs.width)
            bar.scrollTabsTo(item.x + item.width - tabs.width)
        else
            bar.scrollTabsTo(left)
    }

    implicitHeight: 32
    color: Theme.c.PANEL

    Component.onCompleted: {
        bar.syncSheets()
        animTimer.start()
    }

    Connections {
        target: backend
        function onSheetsChanged() { bar.syncSheets() }
    }

    // No glide while the window first lays itself out.
    Timer {
        id: animTimer
        interval: 300
        onTriggered: bar._animate = true
    }

    ListModel { id: tabModel }

    NumberAnimation {
        id: scrollAnim
        target: tabs
        property: "contentX"
        duration: 220
        easing.type: Easing.OutCubic
    }

    // Wheel anywhere on the bar slides the tab strip (eased, not a fling).
    WheelHandler {
        target: null
        onWheel: (event) => {
            if (tabs.contentWidth <= tabs.width)
                return
            const delta = event.angleDelta.x !== 0 ? event.angleDelta.x : event.angleDelta.y
            const base = scrollAnim.running ? bar._scrollTarget : tabs.contentX
            bar.scrollTabsTo(base - delta)
        }
    }

    Rectangle {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        height: 1
        color: Theme.c.BORDER
    }

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 8
        anchors.rightMargin: 8
        spacing: 0

        ListView {
            id: tabs

            Layout.fillHeight: true
            Layout.fillWidth: true
            Layout.preferredWidth: tabs.contentWidth
            Layout.maximumWidth: tabs.contentWidth
            Layout.minimumWidth: Math.min(tabs.contentWidth, 160)
            orientation: ListView.Horizontal
            clip: true
            interactive: false
            boundsBehavior: Flickable.StopAtBounds
            keyNavigationEnabled: false
            cacheBuffer: 10000  // a workbook has few sheets: keep every tab alive
            model: tabModel
            currentIndex: bar.current

            onCurrentItemChanged: bar.syncLine()
            onWidthChanged: Qt.callLater(bar.revealCurrent)

            Connections {
                target: tabs.currentItem
                ignoreUnknownSignals: true
                function onXChanged() { bar.syncLine() }
                function onWidthChanged() { bar.syncLine() }
            }

            delegate: Item {
                id: tab

                required property int index
                required property string name
                readonly property bool isCurrent: tab.index === bar.current

                width: label.implicitWidth + 28
                height: tabs.height

                Rectangle {
                    anchors.fill: parent
                    color: mouse.containsMouse ? (tab.isCurrent ? Theme.c.ACCENT_BG : Theme.c.HOVER) : "transparent"
                    Behavior on color { ColorAnimation { duration: 90 } }
                }

                Text {
                    id: label
                    anchors.centerIn: parent
                    text: tab.name
                    textFormat: Text.PlainText
                    font.family: Theme.sans
                    font.pixelSize: 13
                    font.weight: tab.isCurrent ? Theme.wBold : Theme.wNormal
                    color: tab.isCurrent ? Theme.c.ACCENT : (mouse.containsMouse ? Theme.c.TEXT : Theme.c.MUTED)
                    Behavior on color { ColorAnimation { duration: 120 } }
                }

                MouseArea {
                    id: mouse
                    anchors.fill: parent
                    hoverEnabled: true
                    acceptedButtons: Qt.LeftButton | Qt.RightButton
                    cursorShape: Qt.PointingHandCursor
                    onClicked: (m) => {
                        if (m.button === Qt.RightButton) {
                            tabMenu.index = tab.index
                            // Where the tab was clicked; parented to the bar, which outlives the tabs.
                            const at = tab.mapToItem(bar, m.x, m.y)
                            tabMenu.popup(bar, at.x, at.y)
                        } else if (tab.index !== backend.currentSheet) {
                            backend.switchSheet(tab.index)
                        }
                    }
                    onDoubleClicked: (m) => {
                        if (m.button === Qt.LeftButton)
                            backend.requestRename(tab.index)
                    }
                }
            }

            // The current tab's 2px accent line; it slides and stretches to the new tab.
            // Lives in the content item so it scrolls with the tabs.
            Rectangle {
                parent: tabs.contentItem
                z: 3
                y: 0
                height: 2
                x: bar._lineX
                width: bar._lineW
                color: Theme.c.ACCENT
                Behavior on x {
                    enabled: bar._animate
                    NumberAnimation { duration: 240; easing.type: Easing.OutCubic }
                }
                Behavior on width {
                    enabled: bar._animate
                    NumberAnimation { duration: 240; easing.type: Easing.OutCubic }
                }
            }
        }

        IconButton {
            Layout.leftMargin: 4
            Layout.alignment: Qt.AlignVCenter
            implicitWidth: 24
            implicitHeight: 24
            iconName: "plus"
            iconSize: 14
            iconColor: hovered ? Theme.c.TEXT : Theme.c.MUTED
            tip: "New sheet (Ctrl+T)"
            onClicked: backend.addSheet()
        }

        Item { Layout.fillWidth: true }

        Text {
            Layout.alignment: Qt.AlignVCenter
            text: backend.statusNotes
            textFormat: Text.PlainText
            font.family: Theme.sans
            font.pixelSize: 11
            font.weight: Font.Normal
            color: Theme.c.MUTED
        }

        Text {
            Layout.alignment: Qt.AlignVCenter
            Layout.leftMargin: 18
            // Fixed (the tab strip is what shrinks); only a very long hint elides.
            Layout.preferredWidth: Math.min(implicitWidth, Math.max(120, bar.width * 0.42))
            text: backend.statusHint
            textFormat: Text.PlainText
            elide: Text.ElideRight
            font.family: Theme.sans
            font.pixelSize: 11
            font.weight: Font.Normal
            color: Theme.c.MUTED
        }

        Text {
            Layout.alignment: Qt.AlignVCenter
            Layout.leftMargin: 18
            text: backend.statusSaved
            textFormat: Text.PlainText
            font.family: Theme.sans
            font.pixelSize: 11
            font.weight: Font.Normal
            color: Theme.c.MUTED
        }
    }

    GPMenu {
        id: tabMenu

        property int index: -1

        onClosed: bar.refocusRequested()

        GPMenuItem {
            text: "Rename sheet"
            onTriggered: backend.requestRename(tabMenu.index)
        }
        GPMenuItem {
            text: "Duplicate sheet"
            onTriggered: backend.duplicateSheet(tabMenu.index)
        }
        GPMenuItem {
            text: "Move left"
            enabled: tabMenu.index > 0
            onTriggered: backend.moveSheet(tabMenu.index, -1)
        }
        GPMenuItem {
            text: "Move right"
            enabled: tabMenu.index >= 0 && tabMenu.index < tabModel.count - 1
            onTriggered: backend.moveSheet(tabMenu.index, 1)
        }
        GPMenuSeparator { }
        GPMenuItem {
            text: "Delete sheet"
            enabled: tabModel.count > 1
            onTriggered: bar.deleteRequested(tabMenu.index)
        }
    }
}
