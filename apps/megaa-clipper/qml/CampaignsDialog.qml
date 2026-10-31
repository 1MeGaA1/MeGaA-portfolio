import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "."

// Whop campaigns (web pro.js #campaigns): each campaign's rules, saved for every video. "Use for this video"
// checks every clip of the open video against them.
NeonDialog {
    id: dlg
    title: "Whop campaigns"
    width: Math.min(800, (parent ? parent.width : 860) - 80)
    property string editId: ""   // the campaign in the form ("" = a new one)

    function show() {
        Store.loadCampaigns()
        fill(Store.currentCampaign || Store.campaigns[0] || null)
        open()
    }

    function fill(c) {
        editId = c ? c.id : ""
        nameBox.text = c ? c.name : ""
        cpmBox.text = String(c ? c.cpm : 1)
        speedBox.text = String(c ? c.max_speed : 0)
        minBox.text = String(c ? c.min_len : 0)
        maxBox.text = String(c ? c.max_len : 0)
        tagsBox.text = c ? c.tags : ""
        markBox.text = c ? c.watermark : ""
        noHook.checked = !!(c && c.no_hook)
        needCaptions.checked = !!(c && c.need_captions)
        notesBox.text = c ? c.notes : ""
    }

    function save() {
        const num = text => { const v = parseFloat(text); return isFinite(v) ? v : 0 }
        const c = Store.saveCampaign({
            id: editId || null, name: nameBox.text, cpm: num(cpmBox.text), max_speed: num(speedBox.text),
            min_len: num(minBox.text), max_len: num(maxBox.text), tags: tagsBox.text, watermark: markBox.text,
            no_hook: noHook.checked, need_captions: needCaptions.checked, notes: notesBox.text
        })
        if (c) fill(c)
    }

    function remove() {
        const c = Store.campaigns.find(x => x.id === editId)
        if (!c) return
        Store.ask("Delete campaign?", `Delete the campaign “${c.name}”? Clips stay as they are.`, "Delete",
                  () => { if (Store.deleteCampaign(c.id)) dlg.fill(null) })
    }

    function summary(c) {
        const len = c.min_len || c.max_len ? `${c.min_len || 0}–${c.max_len || "∞"}s` : "any length"
        return `$${Number(c.cpm).toFixed(2)} / 1k views · ${len}`
    }

    component Labeled: ColumnLayout {
        property string label: ""
        default property alias inner: holder.data
        Layout.fillWidth: true
        spacing: 6
        FieldLabel { label: parent.label }
        Item { id: holder; Layout.fillWidth: true; implicitHeight: 34 }
    }

    RowLayout {
        Layout.fillWidth: true
        Layout.fillHeight: true
        spacing: 18

        // the saved campaigns
        ColumnLayout {
            Layout.preferredWidth: 230
            Layout.fillHeight: true
            spacing: 8
            ListView {
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                spacing: 6
                model: Store.campaigns
                boundsBehavior: Flickable.StopAtBounds
                ScrollBar.vertical: NeonScrollBar {}
                Text {
                    anchors.fill: parent
                    visible: !Store.campaigns.length
                    text: "No campaigns yet. Fill in the form to add your first Whop campaign."
                    wrapMode: Text.WordWrap
                    color: Theme.dim
                    font.pixelSize: 12
                }
                delegate: Rectangle {
                    id: item
                    required property var modelData
                    readonly property bool picked: modelData.id === dlg.editId
                    width: ListView.view.width
                    implicitHeight: itemCol.implicitHeight + 16
                    radius: 10
                    color: picked ? Theme.cyanSoft : itemArea.containsMouse ? Qt.rgba(0, 229 / 255, 1, 0.05) : Theme.field
                    border.color: picked ? Qt.rgba(0, 229 / 255, 1, 0.5) : Theme.line
                    Column {
                        id: itemCol
                        x: 10
                        y: 8
                        width: parent.width - 20
                        spacing: 3
                        RowLayout {
                            width: parent.width
                            spacing: 6
                            Text {
                                Layout.fillWidth: true
                                text: item.modelData.name
                                elide: Text.ElideRight
                                color: Theme.text
                                font.pixelSize: 13
                                font.weight: Font.DemiBold
                            }
                            Rectangle {
                                visible: item.modelData.id === Store.campaignId
                                implicitWidth: useText.implicitWidth + 12
                                implicitHeight: 18
                                radius: 6
                                color: Qt.rgba(43 / 255, 1, 160 / 255, 0.12)
                                border.color: Qt.rgba(43 / 255, 1, 160 / 255, 0.5)
                                Text {
                                    id: useText
                                    anchors.centerIn: parent
                                    text: "IN USE"
                                    color: Theme.ok
                                    font.family: Theme.mono
                                    font.pixelSize: 9
                                }
                            }
                        }
                        Text {
                            width: parent.width
                            text: dlg.summary(item.modelData)
                            elide: Text.ElideRight
                            color: Theme.muted
                            font.family: Theme.mono
                            font.pixelSize: 11
                        }
                    }
                    MouseArea {
                        id: itemArea
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: dlg.fill(item.modelData)
                    }
                }
            }
            NeonButton {
                small: true
                iconText: Theme.icAdd
                text: "New campaign"
                onClicked: { dlg.fill(null); nameBox.forceActiveFocus() }
            }
        }

        Rectangle { Layout.fillHeight: true; Layout.preferredWidth: 1; color: Theme.line }

        // the form
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 10
            Labeled { label: "Name"; NeonField { id: nameBox; anchors.fill: parent; placeholderText: "e.g. Kanine podcast clips" } }
            RowLayout {
                Layout.fillWidth: true
                spacing: 12
                Labeled { label: "Pay per 1,000 views ($)"; NeonField { id: cpmBox; anchors.fill: parent; mono: true } }
                Labeled { label: "Max speed (0 = any)"; NeonField { id: speedBox; anchors.fill: parent; mono: true } }
            }
            RowLayout {
                Layout.fillWidth: true
                spacing: 12
                Labeled { label: "Min length (s)"; NeonField { id: minBox; anchors.fill: parent; mono: true } }
                Labeled { label: "Max length (s)"; NeonField { id: maxBox; anchors.fill: parent; mono: true } }
            }
            Labeled {
                label: "Required tags in the post caption"
                NeonField { id: tagsBox; anchors.fill: parent; placeholderText: "#ad @brandname #partner" }
            }
            Labeled {
                label: "Required watermark text"
                NeonField { id: markBox; anchors.fill: parent; placeholderText: "leave empty if none" }
            }
            NeonSwitch { id: noHook; text: "No text on top (hook not allowed)" }
            NeonSwitch { id: needCaptions; text: "Captions are required" }
            FieldLabel { label: "Notes" }
            NeonArea {
                id: notesBox
                Layout.fillWidth: true
                Layout.preferredHeight: 58
                wrapMode: TextEdit.Wrap
                placeholderText: "anything else from the campaign brief"
            }
            RowLayout {
                Layout.fillWidth: true
                Layout.topMargin: 4
                spacing: 10
                NeonButton { primary: true; small: true; text: "Save campaign"; onClicked: dlg.save() }
                NeonButton {
                    small: true
                    visible: dlg.editId !== "" && !!Store.video
                    text: Store.campaignId === dlg.editId ? "Stop using for this video" : "Use for this video"
                    onClicked: Store.useCampaign(Store.campaignId === dlg.editId ? "" : dlg.editId)
                }
                Item { Layout.fillWidth: true }
                NeonButton { small: true; visible: dlg.editId !== ""; text: "Delete"; onClicked: dlg.remove() }
            }
        }
    }
}
