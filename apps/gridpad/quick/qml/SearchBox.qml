import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// The find box in the top bar: search icon, input, then "Ctrl+F" until there is text and
// "3 of 10" + previous / next / close after. Typing searches every sheet as you go;
// Enter / Shift+Enter step through the matches, Esc closes find and returns to the grid.
Rectangle {
    id: box

    readonly property bool hasText: input.text.length > 0
    readonly property bool inputFocused: input.activeFocus
    readonly property bool active: input.activeFocus || box.hasText
    readonly property string text: input.text

    // Ctrl+F: focus the input with everything selected, so typing replaces the old query.
    function focusFind() {
        input.forceActiveFocus(Qt.ShortcutFocusReason)
        input.selectAll()
    }

    // Focus without touching the selection (back from a menu that was opened while typing).
    function focusInput() {
        input.forceActiveFocus(Qt.OtherFocusReason)
    }

    // Empties the box without searching again (the backend already reset its query).
    function clear() {
        input.clear()
    }

    implicitWidth: 300
    implicitHeight: 30
    radius: 4
    color: Theme.c.FIELD
    border.width: 1
    border.color: box.active ? Theme.c.ACCENT : Theme.c.BORDER
    Behavior on border.color { ColorAnimation { duration: 140; easing.type: Easing.OutCubic } }

    component FindButton: IconButton {
        implicitWidth: 22
        implicitHeight: 22
        iconSize: 14
        Layout.alignment: Qt.AlignVCenter
    }

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 10
        anchors.rightMargin: 6
        spacing: 6

        Icon {
            // Icon's implicit size is its 2x sourceSize: pin the layout size to `size`.
            Layout.preferredWidth: 15
            Layout.preferredHeight: 15
            Layout.alignment: Qt.AlignVCenter
            name: "search"
            color: Theme.c.MUTED
            size: 15
        }

        TextField {
            id: input

            Layout.fillWidth: true
            Layout.fillHeight: true
            padding: 0
            leftPadding: 0
            rightPadding: 0
            topPadding: 0
            bottomPadding: 0
            verticalAlignment: TextInput.AlignVCenter
            background: null
            selectByMouse: true
            font.family: Theme.sans
            font.pixelSize: 12
            font.weight: Font.Normal
            color: Theme.c.TEXT
            placeholderText: "Find in all sheets"
            placeholderTextColor: Theme.c.MUTED
            selectionColor: Theme.c.HI
            selectedTextColor: Theme.c.HI_TEXT

            // textEdited (not textChanged): clear() from searchCleared must not search again.
            onTextEdited: backend.setQuery(input.text)

            Keys.onReturnPressed: (event) => backend.stepMatch(event.modifiers & Qt.ShiftModifier ? -1 : 1)
            Keys.onEnterPressed: (event) => backend.stepMatch(event.modifiers & Qt.ShiftModifier ? -1 : 1)
            Keys.onEscapePressed: backend.closeFind()
        }

        Text {
            Layout.alignment: Qt.AlignVCenter
            visible: !box.hasText
            text: "Ctrl+F"
            font.family: Theme.sans
            font.pixelSize: 12
            font.weight: Font.Normal
            color: Theme.c.MUTED
        }

        Text {
            Layout.alignment: Qt.AlignVCenter
            visible: box.hasText
            text: backend.matchLabel
            font.family: Theme.sans
            font.pixelSize: 12
            font.weight: Font.Normal
            color: Theme.c.MUTED
        }

        FindButton {
            visible: box.hasText
            iconName: "chevron-up"
            tip: "Previous match (Shift+Enter)"
            onClicked: backend.stepMatch(-1)
        }

        FindButton {
            visible: box.hasText
            iconName: "chevron-down"
            tip: "Next match (Enter)"
            onClicked: backend.stepMatch(1)
        }

        FindButton {
            visible: box.hasText
            iconName: "x"
            tip: "Close find (Esc)"
            onClicked: backend.closeFind()
        }
    }
}
