import QtQuick
import QtQuick.Layouts
import QtQuick.Effects
import "."

// Shown while no video is open: big open button + recent projects.
Rectangle {
    id: welcome
    signal openRequested()
    color: Qt.rgba(4 / 255, 6 / 255, 11 / 255, 0.94)

    MouseArea { anchors.fill: parent; acceptedButtons: Qt.AllButtons; onWheel: (wheel) => wheel.accepted = true }

    Rectangle {
        id: card
        anchors.centerIn: parent
        width: Math.min(parent.width - 80, 720)
        height: body.implicitHeight + 80
        radius: 22
        color: Theme.panelSolid
        border.color: Theme.line2
        layer.enabled: true
        layer.effect: MultiEffect {
            shadowEnabled: true
            shadowColor: Theme.cyan
            shadowOpacity: 0.18
            shadowBlur: 1
            shadowHorizontalOffset: 0
            shadowVerticalOffset: 0
        }

        ColumnLayout {
            id: body
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.margins: 40
            spacing: 16

            Logo { Layout.preferredWidth: 58; Layout.preferredHeight: 58 }
            Text {
                textFormat: Text.StyledText
                text: `<font color="${Theme.magenta}">MeGaA</font> CLIPPER`
                color: Theme.text
                font.family: Theme.display
                font.pixelSize: 15
                font.weight: Font.Bold
                font.letterSpacing: 3
            }
            Column {
                spacing: 0
                Text {
                    text: "Long video in."
                    color: Theme.text
                    font.family: Theme.display
                    font.pixelSize: 44
                    font.weight: Font.Bold
                }
                // gradient text: a cyan → magenta bar masked by the words
                Item {
                    width: viral.implicitWidth
                    height: viral.implicitHeight
                    Text {
                        id: viral
                        text: "Viral clips out."
                        font.family: Theme.display
                        font.pixelSize: 44
                        font.weight: Font.Bold
                        visible: false
                        layer.enabled: true
                    }
                    Rectangle {
                        anchors.fill: parent
                        visible: false
                        id: grad
                        layer.enabled: true
                        gradient: Gradient {
                            orientation: Gradient.Horizontal
                            GradientStop { position: 0; color: Theme.cyan }
                            GradientStop { position: 1; color: Theme.magenta }
                        }
                    }
                    MultiEffect {
                        anchors.fill: parent
                        source: grad
                        maskEnabled: true
                        maskSource: viral
                    }
                }
            }
            Text {
                Layout.fillWidth: true
                text: "Transcribe on your GPU, pick the moments, and render vertical clips with word-by-word captions."
                wrapMode: Text.WordWrap
                color: Theme.muted
                font.pixelSize: 14
            }
            NeonButton {
                primary: true
                text: "Open a video"
                iconText: Theme.icOpen
                implicitHeight: 46
                font.pixelSize: 14
                Layout.topMargin: 6
                onClicked: welcome.openRequested()
            }

            ColumnLayout {
                visible: Store.recent.length > 0
                Layout.fillWidth: true
                Layout.topMargin: 10
                spacing: 10
                FieldLabel { label: "Recent projects" }
                GridLayout {
                    Layout.fillWidth: true
                    columns: 2
                    columnSpacing: 10
                    rowSpacing: 10
                    Repeater {
                        model: Store.recent.slice(0, 6)
                        Rectangle {
                            required property var modelData
                            Layout.fillWidth: true
                            Layout.preferredWidth: 1
                            implicitHeight: 56
                            radius: 12
                            color: area.containsMouse ? Qt.rgba(0, 229 / 255, 1, 0.06) : Theme.raised
                            border.color: area.containsMouse ? Qt.rgba(0, 229 / 255, 1, 0.45) : Theme.line2
                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: 12
                                anchors.rightMargin: 12
                                spacing: 11
                                Rectangle {
                                    Layout.preferredWidth: 32; Layout.preferredHeight: 32
                                    radius: 9
                                    color: Theme.cyanSoft
                                    Text {
                                        anchors.centerIn: parent
                                        text: Theme.icVideo
                                        font.family: Theme.icons
                                        font.pixelSize: 15
                                        color: Theme.cyan
                                    }
                                }
                                Column {
                                    Layout.fillWidth: true
                                    spacing: 2
                                    Text {
                                        width: parent.width
                                        text: modelData.name
                                        elide: Text.ElideMiddle
                                        color: Theme.text
                                        font.pixelSize: 13
                                        font.weight: Font.DemiBold
                                    }
                                    Text {
                                        text: `${modelData.clips} clip${modelData.clips === 1 ? "" : "s"}  ·  ${modelData.transcript ? "transcribed" : "no transcript"}`
                                        color: Theme.muted
                                        font.family: Theme.mono
                                        font.pixelSize: 10
                                    }
                                }
                            }
                            MouseArea {
                                id: area
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: Store.openVideo(modelData.path)
                            }
                        }
                    }
                }
            }
        }
    }
}
