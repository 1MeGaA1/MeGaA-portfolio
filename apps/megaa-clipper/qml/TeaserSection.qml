import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "."

// Edit tab, "Teaser at the start": a 3–5 s highlight played first, then the clip from the beginning
// (web ui/index.html 246-273, app.js 1270-1394). The body stays usable while there is no teaser, only dimmed.
Rectangle {
    id: sec
    readonly property var intro: Store.teaserSpan
    readonly property var info: Store.teaserInfo()   // follows the teaser and the words, not every edit change
    readonly property color amber: Theme.warn

    implicitHeight: col.implicitHeight + 20
    radius: 10
    color: Qt.rgba(amber.r, amber.g, amber.b, 0.05)
    border.color: Qt.rgba(amber.r, amber.g, amber.b, 0.28)

    // the from / to box and its I / O button; a typed time only counts when it was edited (web: change event)
    component TeaserTime: NeonField {
        id: box
        property int which: 0
        property bool dirty: false
        readonly property var value: Store.teaserSpan ? Store.teaserSpan[which] : null
        mono: true
        implicitHeight: 34
        rightPadding: 38
        placeholderText: which === 0 ? "from" : "to"

        // a function, not a bound property: onValueChanged may run before such a binding is redone
        function shown() { return value === null ? "" : Store.fmt(value) }
        // never rewrite the box while it is typed in; a rewrite shows a valid time again
        function show() {
            if (activeFocus) return
            text = shown()
            bad = false
        }
        // the shown time typed again keeps the exact edge (0.1 s rounded on screen), like the In / Out boxes
        function commit() {
            if (!dirty) return
            dirty = false
            if (text === shown()) { bad = false; return }
            bad = !Store.teaserTyped(which, text)
        }
        onValueChanged: show()
        Component.onCompleted: show()
        // Store.extra is replaced only by applyClip / newClip: another clip (or New) never shows this one's typed text
        Connections {
            target: Store
            function onExtraChanged() { box.dirty = false; box.bad = false; box.show() }
        }
        onTextEdited: dirty = true
        onEditingFinished: commit()
        // focus goes before editingFinished: commit the typed time first, a bad one stays in the box
        onActiveFocusChanged: if (!activeFocus) { commit(); if (!bad) show() }

        Rectangle {
            anchors.right: parent.right
            anchors.rightMargin: 4
            anchors.verticalCenter: parent.verticalCenter
            width: 28; height: 26; radius: 7
            color: markArea.containsMouse ? Theme.cyanSoft : Theme.raised
            border.color: markArea.containsMouse ? Qt.rgba(0, 229 / 255, 1, 0.5) : Theme.line2
            Text { anchors.centerIn: parent; text: box.which === 0 ? "I" : "O"; color: Theme.cyan; font.family: Theme.mono; font.pixelSize: 11; font.bold: true }
            MouseArea {
                id: markArea
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: {
                    Store.releaseFocus()
                    if (box.which === 0) Store.teaserMarkStart(); else Store.teaserMarkEnd()
                    box.show()
                }
            }
            ToolTip.visible: markArea.containsMouse
            ToolTip.delay: 400
            ToolTip.text: box.which === 0 ? "Teaser starts at the playhead" : "Teaser ends at the playhead"
        }
    }

    ColumnLayout {
        id: col
        x: 12
        y: 10
        width: sec.width - 24
        spacing: 7

        NeonSwitch {
            big: true
            accent: sec.amber
            accentFill: 0.22
            text: "Teaser at the start"
            checked: !!sec.intro
            onPressed: Store.releaseFocus()   // a typed time commits before the switch acts (web: blur on mousedown)
            onToggled: {
                Store.teaserSwitch(checked)
                checked = Qt.binding(() => !!sec.intro)   // a failed auto pick leaves edit.intro alone: switch back off
            }
        }
        Text {
            Layout.fillWidth: true
            text: "Plays a 3–5 s highlight first, then the clip from the beginning."
            wrapMode: Text.WordWrap
            color: Theme.dim
            font.pixelSize: 11
        }

        ColumnLayout {
            Layout.fillWidth: true
            Layout.topMargin: 1
            spacing: 8
            opacity: sec.intro ? 1 : 0.45

            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                TeaserTime { Layout.fillWidth: true; Layout.preferredWidth: 1; which: 0 }
                Text { text: "→"; color: Theme.dim; font.pixelSize: 14 }
                TeaserTime { Layout.fillWidth: true; Layout.preferredWidth: 1; which: 1 }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                NeonButton {
                    small: true
                    text: "Pick words"
                    active: Store.teaserPick !== ""
                    activeColor: sec.amber
                    ToolTip.visible: hovered
                    ToolTip.delay: 600
                    ToolTip.text: "Click the first word, then the last word"
                    onClicked: { Store.releaseFocus(); Store.toggleTeaserPick() }
                }
                NeonButton {
                    small: true
                    text: "Auto pick"
                    ToolTip.visible: hovered
                    ToolTip.delay: 600
                    ToolTip.text: "Find the most energetic 3–5 seconds"
                    onClicked: { Store.releaseFocus(); Store.teaserAutoPick() }
                }
                NeonButton {
                    small: true
                    text: "Play"
                    iconText: Theme.icPlay
                    ToolTip.visible: hovered
                    ToolTip.delay: 600
                    ToolTip.text: "Watch the teaser"
                    onClicked: { Store.releaseFocus(); Store.playTeaser() }
                }
                Item { Layout.fillWidth: true }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 10
                Text {
                    Layout.fillWidth: true
                    text: sec.info.text
                    wrapMode: Text.WordWrap
                    color: Theme.dim
                    font.pixelSize: 11
                    HoverHandler { id: infoHover }
                    ToolTip.visible: infoHover.hovered && sec.info.said !== ""
                    ToolTip.delay: 500
                    ToolTip.text: sec.info.said
                }
                NeonSwitch {
                    accent: sec.amber
                    accentFill: 0.22
                    text: "Flash"
                    checked: Store.edit.introFlash
                    onPressed: Store.releaseFocus()
                    onToggled: Store.setEdit({ introFlash: checked })
                }
            }
        }
    }
}
