import QtQuick
import QtQuick.Controls

// Context / dropdown menu. Fill it with GPMenuItem and GPMenuSeparator.
Menu {
    id: m

    padding: 6
    // As wide as the widest item, so long labels ("Sort rows A → Z by column B in A1:C9") never clip.
    contentWidth: {
        let widest = 160
        for (let i = 0; i < m.count; ++i) {
            const item = m.itemAt(i)
            if (item)
                widest = Math.max(widest, item.implicitWidth)
        }
        return widest
    }
    font.family: Theme.sans
    font.pixelSize: 13
    font.weight: Theme.wNormal

    delegate: GPMenuItem { }

    background: Rectangle {
        implicitWidth: 200
        color: Theme.c.MENU_BG
        border.color: Theme.c.MENU_BORDER
        radius: 6
    }

    enter: Transition {
        ParallelAnimation {
            NumberAnimation { property: "opacity"; from: 0; to: 1; duration: 110; easing.type: Easing.OutCubic }
            NumberAnimation { property: "scale"; from: 0.97; to: 1; duration: 130; easing.type: Easing.OutCubic }
        }
    }
    exit: Transition {
        NumberAnimation { property: "opacity"; to: 0; duration: 80 }
    }
}
