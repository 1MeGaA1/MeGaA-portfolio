import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// Shop / menu page. Products (name, category, price in minor units, picture) are managed in the
// admin panel and come from the server via vortex.shop(), refreshed live on vortex.shopChanged.
// BUY opens a confirm dialog; ORDER sends the order to the counter (vortex.order) where staff
// hand it over and take the payment.
Item {
    id: root
    signal notify(string msg)
    property string cat: "all"
    property var items: vortex.shop()

    function accentFor(i) { return [Theme.cyan, Theme.magenta, Theme.green, Theme.amber][i % 4] }
    function picUrl(it) { return (it && it.image_url) ? vortex.serverHttp + it.image_url : "" }
    function filtered() {
        return items.filter(function (it) { return root.cat === "all" || it.category === root.cat })
    }
    function bestsellers() { return items.filter(function (it) { return it.best }) }
    function askOrder(it) { confirm.item = it; confirm.qty = 1; confirm.busy = false; confirm.open() }

    Connections {
        target: vortex
        function onShopChanged() { root.items = vortex.shop() }
        function onOrderResult(ok, message, order) {
            confirm.busy = false
            if (!ok) { root.notify(message || "Order failed. Ask the counter."); return }
            var o = order || {}
            var name = o.product_name || (confirm.item ? confirm.item.name : "")
            var qty = o.qty || confirm.qty
            var total = (o.total !== undefined && o.total !== null) ? o.total
                      : (confirm.item ? confirm.item.price * confirm.qty : 0)
            confirm.close()
            root.notify("Order sent to the counter · " + name + " ×" + qty + " · " + vortex.currency + " " + vortex.money(total))
        }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 14
        RowLayout {
            Layout.fillWidth: true
            SectionLabel { label: "SHOP" }
            Item { Layout.fillWidth: true }
            Text { text: "ORDER HERE · PAY AT THE COUNTER"; color: Theme.textDim
                   font.family: Theme.fontMono; font.pixelSize: 10; font.letterSpacing: 2 }
        }
        FilterChips {
            Layout.fillWidth: true
            visible: root.items.length > 0
            model: Content.shopCats
            current: root.cat
            onPicked: (k) => root.cat = k
        }
        ScrollView {
            Layout.fillWidth: true; Layout.fillHeight: true
            visible: root.items.length > 0
            clip: true; contentWidth: availableWidth
            ColumnLayout {
                width: parent.width
                spacing: 14

                SectionLabel { visible: root.cat === "all" && root.bestsellers().length > 0; label: "BEST SELLERS"; accent: Theme.magenta }
                GridLayout {
                    visible: root.cat === "all" && root.bestsellers().length > 0
                    Layout.fillWidth: true
                    columns: Math.max(2, Math.floor(root.width / 175))
                    columnSpacing: 14; rowSpacing: 14
                    Repeater {
                        model: root.bestsellers()
                        delegate: ShopCard {
                            required property var modelData
                            required property int index
                            Layout.fillWidth: true; Layout.preferredHeight: 196
                            name: modelData.name; price: modelData.price; imageUrl: root.picUrl(modelData)
                            currency: vortex.currency; accent: Theme.magenta
                            onBuy: root.askOrder(modelData)
                        }
                    }
                }

                SectionLabel { label: root.cat === "all" ? "ALL ITEMS" : root.cat.toUpperCase() }
                GridLayout {
                    Layout.fillWidth: true
                    columns: Math.max(2, Math.floor(root.width / 175))
                    columnSpacing: 14; rowSpacing: 14
                    Repeater {
                        model: root.filtered()
                        delegate: ShopCard {
                            required property var modelData
                            required property int index
                            Layout.fillWidth: true; Layout.preferredHeight: 196
                            name: modelData.name; price: modelData.price; imageUrl: root.picUrl(modelData)
                            currency: vortex.currency; accent: root.accentFor(index)
                            onBuy: root.askOrder(modelData)
                        }
                    }
                }
                Text {
                    visible: root.filtered().length === 0
                    text: "NOTHING IN THIS CATEGORY"; color: Theme.textDim
                    font.family: Theme.fontMono; font.pixelSize: 12; font.letterSpacing: 2
                    Layout.alignment: Qt.AlignHCenter
                }
                Item { Layout.fillHeight: true; implicitHeight: 10 }
            }
        }
        // empty state: staff disabled / removed every product
        Item {
            visible: root.items.length === 0
            Layout.fillWidth: true; Layout.fillHeight: true
            Text {
                anchors.centerIn: parent
                text: "SHOP IS EMPTY"; color: Theme.textDim
                font.family: Theme.fontMono; font.pixelSize: 12; font.letterSpacing: 2
            }
        }
    }

    // ---- confirm dialog: picture, name, qty 1..10, total -> ORDER ----
    // Lives in the window overlay so the dim covers the whole hub, not just the page area.
    ModalOverlay {
        id: confirm
        parent: Overlay.overlay
        property var item: null
        property int qty: 1
        property bool busy: false
        readonly property int total: item ? item.price * qty : 0
        label: "ORDER"; title: item ? item.name : ""; accent: Theme.green; cardWidth: 400
        onClosed: busy = false

        RowLayout {
            Layout.fillWidth: true; spacing: 16
            Rectangle {
                Layout.preferredWidth: 88; Layout.preferredHeight: 88
                color: Theme.surface; border.color: Theme.border; border.width: 1
                Image {
                    id: cpic
                    anchors.fill: parent; anchors.margins: 8
                    source: root.picUrl(confirm.item)
                    sourceSize.width: 144; sourceSize.height: 144
                    fillMode: Image.PreserveAspectFit; smooth: true; asynchronous: true
                    visible: status === Image.Ready
                }
                Text {
                    visible: !cpic.visible; anchors.centerIn: parent
                    text: (confirm.item && confirm.item.name.length) ? confirm.item.name.charAt(0).toUpperCase() : "?"
                    color: Theme.green; font.family: Theme.fontDisplay; font.weight: Font.Bold; font.pixelSize: 36
                }
            }
            ColumnLayout {
                Layout.fillWidth: true; spacing: 4
                Text { text: "UNIT PRICE"; color: Theme.textDim; font.family: Theme.fontMono; font.pixelSize: 9; font.letterSpacing: 2 }
                Text { text: vortex.currency + " " + vortex.money(confirm.item ? confirm.item.price : 0); color: Theme.green
                       font.family: Theme.fontMono; font.weight: Font.Medium; font.pixelSize: 15 }
                Text { text: "Pay at the counter when it arrives."; color: Theme.textMuted
                       font.family: Theme.fontBody; font.pixelSize: 12; Layout.fillWidth: true; wrapMode: Text.WordWrap }
            }
        }
        RowLayout {
            Layout.fillWidth: true; spacing: 10
            Text { text: "QTY"; color: Theme.textDim; font.family: Theme.fontMono; font.pixelSize: 10; font.letterSpacing: 2 }
            QtyButton { text: "−"; enabled: confirm.qty > 1; onClicked: confirm.qty = Math.max(1, confirm.qty - 1) }
            Text { text: confirm.qty; color: Theme.textPrimary; horizontalAlignment: Text.AlignHCenter
                   Layout.preferredWidth: 30; font.family: Theme.fontMono; font.weight: Font.Medium; font.pixelSize: 16 }
            QtyButton { text: "+"; enabled: confirm.qty < 10; onClicked: confirm.qty = Math.min(10, confirm.qty + 1) }
            Item { Layout.fillWidth: true }
            Text { text: "TOTAL"; color: Theme.textDim; font.family: Theme.fontMono; font.pixelSize: 10; font.letterSpacing: 2 }
            Text { text: vortex.currency + " " + vortex.money(confirm.total); color: Theme.textPrimary
                   font.family: Theme.fontDisplay; font.weight: Font.Bold; font.pixelSize: 22 }
        }
        RowLayout {
            Layout.fillWidth: true; spacing: 10
            VxButton { Layout.fillWidth: true; text: "CANCEL"; filled: false; onClicked: confirm.close() }
            VxButton { Layout.fillWidth: true; text: confirm.busy ? "SENDING…" : "ORDER"; accent: Theme.green
                       enabled: !confirm.busy && confirm.item !== null
                       onClicked: { confirm.busy = true; vortex.order(confirm.item.id, confirm.qty) } }
        }
    }

    // small square − / + stepper button
    component QtyButton: Rectangle {
        property string text: ""
        signal clicked()
        implicitWidth: 34; implicitHeight: 34
        color: qma.containsMouse && enabled ? Qt.rgba(0, 0.9, 1, 0.10) : "transparent"
        border.color: enabled ? Theme.cyan : Theme.border; border.width: 1
        opacity: enabled ? 1 : 0.5
        Text { anchors.centerIn: parent; text: parent.text; color: parent.enabled ? Theme.cyan : Theme.textDim
               font.family: Theme.fontDisplay; font.weight: Font.Bold; font.pixelSize: 18 }
        MouseArea { id: qma; anchors.fill: parent; hoverEnabled: true
                    cursorShape: parent.enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
                    onClicked: if (parent.enabled) parent.clicked() }
    }
}
