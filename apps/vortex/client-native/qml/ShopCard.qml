import QtQuick

// A shop product card: product picture from the server, name, price in the cafe currency, BUY.
// Falls back to a big initial letter while the picture loads or if there is none.
Rectangle {
    id: root
    property string name: ""
    property int price: 0                // MINOR units (2500 = 25.00); shown via vortex.money
    property string imageUrl: ""         // full URL (vortex.serverHttp + image_url) or ""
    property string currency: "EGP"
    property color accent: Theme.cyan
    signal buy()

    implicitWidth: 150
    implicitHeight: 196
    color: Theme.surface
    border.color: ma.containsMouse ? accent : Theme.border
    border.width: 1

    // soft accent halo behind the picture on hover
    Rectangle {
        anchors.horizontalCenter: parent.horizontalCenter
        y: 16
        width: 100
        height: 100
        radius: 50
        color: root.accent
        opacity: ma.containsMouse ? 0.16 : 0.0
        Behavior on opacity { NumberAnimation { duration: 180 } }
    }

    Image {
        id: pic
        anchors.horizontalCenter: parent.horizontalCenter
        y: 14
        width: 104
        height: 104
        source: root.imageUrl
        sourceSize.width: 208
        sourceSize.height: 208
        fillMode: Image.PreserveAspectFit
        smooth: true
        asynchronous: true
        visible: status === Image.Ready
        scale: ma.containsMouse ? 1.06 : 1.0
        Behavior on scale { NumberAnimation { duration: 140; easing.type: Easing.OutCubic } }
    }

    // fallback initial when there is no picture
    Text {
        visible: !pic.visible
        anchors.horizontalCenter: parent.horizontalCenter
        y: 34
        text: root.name.length ? root.name.charAt(0).toUpperCase() : "?"
        color: root.accent
        font.family: Theme.fontDisplay
        font.weight: Font.Bold
        font.pixelSize: 48
    }

    Column {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.margins: 12
        spacing: 7
        Text {
            width: parent.width
            text: root.name
            color: Theme.textPrimary
            elide: Text.ElideRight
            horizontalAlignment: Text.AlignHCenter
            font.family: Theme.fontBody
            font.pixelSize: 13
        }
        Row {
            anchors.horizontalCenter: parent.horizontalCenter
            spacing: 10
            Text {
                anchors.verticalCenter: parent.verticalCenter
                text: root.currency + " " + vortex.money(root.price)
                color: Theme.green
                font.family: Theme.fontMono
                font.weight: Font.Medium
                font.pixelSize: 14
            }
            Rectangle {
                width: 54
                height: 24
                color: ma.containsMouse ? Qt.rgba(0, 0.9, 1, 0.16) : "transparent"
                border.color: Theme.cyan
                border.width: 1
                Text {
                    anchors.centerIn: parent
                    text: "BUY"
                    color: Theme.cyan
                    font.family: Theme.fontDisplay
                    font.weight: Font.Bold
                    font.pixelSize: 11
                    font.letterSpacing: 2
                }
            }
        }
    }

    MouseArea { id: ma; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: root.buy() }
    scale: ma.pressed ? 0.98 : 1.0
    Behavior on scale { NumberAnimation { duration: 90 } }
}
