import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "."

// Captions tab: on/off, style preset, highlight colour, size, height, keyword colours + emojis.
ScrollPane {
    id: tab

    readonly property var st: Store.effectiveStyle()
    readonly property var kwColors: ["#39FF14", "#00E5FF", "#FF2BD6", "#FFD400", "#FF3B30", "#FF9500"]

    NeonSwitch {
        big: true
        text: "Show captions"
        checked: Store.captionsOn
        onToggled: Store.captionsOn = checked
    }

    ColumnLayout {
        Layout.fillWidth: true
        spacing: 7
        opacity: Store.captionsOn ? 1 : 0.4
        FieldLabel { label: "Style" }
        GridLayout {
            Layout.fillWidth: true
            columns: 2
            columnSpacing: 6
            rowSpacing: 6
            Repeater {
                model: Store.styleOrder
                StyleTile {
                    required property string modelData
                    Layout.fillWidth: true
                    Layout.preferredWidth: 1
                    st: Store.styles[modelData]
                    on: Store.cap.style === modelData
                    onClicked: Store.setCap({ style: modelData, color: null })
                }
            }
        }
    }

    ColumnLayout {
        Layout.fillWidth: true
        spacing: 8
        opacity: tab.st && tab.st.mode === "none" ? 0.35 : 1
        enabled: !(tab.st && tab.st.mode === "none")
        FieldLabel { label: "Highlight colour" }
        Swatches {
            Layout.fillWidth: true
            auto: true
            custom: true
            colors: Store.swatches
            current: Store.cap.color
            customStart: tab.st ? tab.st.accent : "#ffffff"
            onPicked: (color) => Store.setCap({ color: color })
        }
    }

    ColumnLayout {
        Layout.fillWidth: true
        spacing: 7
        FieldLabel { label: "Size"; note: `${Store.cap.size}%` }
        NeonSlider {
            Layout.fillWidth: true
            from: 60; to: 160; stepSize: 5
            value: Store.cap.size
            onMoved: Store.setCap({ size: Math.round(value) })
        }
    }

    ColumnLayout {
        Layout.fillWidth: true
        spacing: 7
        FieldLabel { label: "Height on screen"; note: tab.st ? `${Math.round(tab.st.margin_v / 1920 * 100)}% from bottom` : "" }
        NeonSlider {
            Layout.fillWidth: true
            from: 120; to: 1500; stepSize: 10
            value: tab.st ? tab.st.margin_v : 480
            onMoved: Store.setCap({ pos: Math.round(value) })
        }
    }

    ColumnLayout {
        Layout.fillWidth: true
        spacing: 10
        FieldLabel { label: "Keywords"; note: "numbers, money, power words" }
        NeonSwitch {
            big: true
            text: "Colour keywords"
            checked: Store.kw.on
            onToggled: Store.setKw({ on: checked })
        }
        Swatches {
            Layout.fillWidth: true
            opacity: Store.kw.on ? 1 : 0.4
            colors: tab.kwColors
            current: Store.kw.color
            onPicked: (color) => Store.setKw({ color: color, on: true })
        }
        NeonSwitch {
            big: true
            text: "Emojis on keywords"
            checked: Store.kw.emojis
            onToggled: Store.setKw({ emojis: checked })
        }
    }

    RowLayout {
        Layout.fillWidth: true
        spacing: 8
        NeonButton {
            small: true
            text: "Reset colour & size"
            onClicked: Store.setCap({ color: null, size: 100, pos: null })
        }
        NeonButton {
            small: true
            text: "Apply to all clips"
            onClicked: Store.applyToAll(Store.captionFields(), "Caption style")
        }
    }
}
