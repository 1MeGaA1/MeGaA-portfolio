import QtQuick
import QtQuick.Layouts
import "."

// Short messages in the corner (newest at the bottom); errors stay longer.
Column {
    id: toasts
    spacing: 8
    width: 380

    ListModel { id: items }
    property int nextId: 0

    function show(message, kind) {
        if (!message) return
        items.append({ uid: nextId++, message: String(message), kind: kind || "info" })
        if (items.count > 4) items.remove(0)
    }

    function drop(uid) {
        for (let i = 0; i < items.count; i++) if (items.get(i).uid === uid) { items.remove(i); return }
    }

    Connections {
        target: Store
        function onToast(message, kind) { toasts.show(message, kind) }
    }

    Repeater {
        model: items
        Rectangle {
            id: toast
            required property int uid
            required property string message
            required property string kind
            readonly property color tint: kind === "error" ? Theme.bad : kind === "ok" ? Theme.ok : Theme.cyan
            width: toasts.width
            height: row.implicitHeight + 22
            radius: 12
            color: Theme.panelSolid
            border.color: Qt.rgba(tint.r, tint.g, tint.b, 0.5)
            opacity: 0
            Component.onCompleted: opacity = 1
            Behavior on opacity { NumberAnimation { duration: 180 } }

            Rectangle { x: 0; y: 10; width: 3; height: parent.height - 20; radius: 2; color: toast.tint }
            RowLayout {
                id: row
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                anchors.leftMargin: 16
                anchors.rightMargin: 12
                spacing: 10
                Text {
                    text: toast.kind === "error" ? Theme.icWarn : toast.kind === "ok" ? Theme.icCheck : Theme.icInfo
                    font.family: Theme.icons
                    font.pixelSize: 14
                    color: toast.tint
                    Layout.alignment: Qt.AlignTop
                    Layout.topMargin: 1
                }
                Text {
                    Layout.fillWidth: true
                    text: toast.message
                    wrapMode: Text.WordWrap
                    color: Theme.text
                    font.pixelSize: 13
                }
            }
            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: toasts.drop(toast.uid) }
            Timer { running: true; interval: toast.kind === "error" ? 8000 : 4500; onTriggered: toasts.drop(toast.uid) }
        }
    }
}
