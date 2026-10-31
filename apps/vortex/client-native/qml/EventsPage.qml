import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// Events page. Events are managed in the admin panel and come from the server via
// vortex.events() (enabled + show_events), refreshed live on vortex.eventsChanged.
Item {
    id: root
    signal notify(string msg)
    property string cat: "all"
    property var events: vortex.events()

    function filtered() {
        return events.filter(function (e) {
            return root.cat === "all" || (e.cats && e.cats.indexOf(root.cat) >= 0)
        })
    }
    function joinMsg(e) {
        if (e.kind === "offer") return "Show this offer at the counter · " + e.title
        return (e.status === "live" ? "Joined " : "Registered for ") + e.title
    }

    Connections {
        target: vortex
        function onEventsChanged() { root.events = vortex.events() }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 14
        SectionLabel { label: "EVENTS & TOURNAMENTS" }
        FilterChips {
            Layout.fillWidth: true
            visible: root.events.length > 0
            model: Content.eventCats
            current: root.cat
            onPicked: (k) => root.cat = k
        }
        ScrollView {
            Layout.fillWidth: true; Layout.fillHeight: true
            visible: root.filtered().length > 0
            clip: true; contentWidth: availableWidth
            GridLayout {
                width: parent.width
                columns: Math.max(1, Math.floor(root.width / 320))
                columnSpacing: 14; rowSpacing: 14
                Repeater {
                    model: root.filtered()
                    delegate: EventCard {
                        required property var modelData
                        Layout.fillWidth: true; Layout.preferredHeight: 170
                        ev: modelData
                        onJoin: root.notify(root.joinMsg(modelData))
                    }
                }
            }
        }
        // empty state: no events at all (staff disabled them) or none in this category
        Item {
            visible: root.filtered().length === 0
            Layout.fillWidth: true; Layout.fillHeight: true
            Text {
                anchors.centerIn: parent
                text: root.events.length === 0 ? "NO EVENTS RIGHT NOW" : "NO EVENTS IN THIS CATEGORY"
                color: Theme.textDim
                font.family: Theme.fontMono; font.pixelSize: 12; font.letterSpacing: 2
            }
        }
    }
}
