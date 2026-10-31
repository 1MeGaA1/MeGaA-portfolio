import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs
import "." as GP  // our Grid.qml: plain `Grid` would be QtQuick's Grid positioner

// The GridPad window (Qt Quick edition): top bar / grid over the background effect / sheet bar.
// Owns the window-level shortcuts, the native file dialogs, the "save first?" flows,
// drag-and-drop, and the window's geometry and title. Behaviour lives in `backend`.
ApplicationWindow {
    id: win

    property bool _closeConfirmed: false
    property bool _closeAsking: false  // the close button's "save first?" prompt is up
    property bool _startMaximized: false
    property var _afterSave: null  // what to do once the Save dialog has saved (discard flows)
    property var _normalGeo: null  // last un-maximized [x, y, w, h], saved while maximized
    property bool _wasMaximized: false
    property bool _tagMenuFromSearch: false

    // ---------------------------------------------------------------- focus
    function anyDialogOpen() {
        const dialogs = [settingsDialog, exportDialog, importDialog, replaceDialog, helpDialog,
                         renameDialog, confirmDialog, saveDialog, openDialog, importFileDialog]
        for (const d of dialogs) {
            if (d.visible)
                return true
        }
        return false
    }

    // After a dialog or menu closes: the grid gets the keys back, unless another dialog took over.
    function refocusGrid() {
        Qt.callLater(win._refocusNow)
    }

    function _refocusNow() {
        if (!win.anyDialogOpen())
            grid.focusGrid()
    }

    // ---------------------------------------------------------------- files
    // Run `proceed` once dropping the current workbook is fine: saved, empty, or the user agreed.
    // `answered` (optional) runs first with whatever the prompt's answer was.
    function withDiscardCheck(proceed, answered) {
        grid.commitEdit()
        if (!backend.needsDiscardConfirm()) {
            proceed()
            return
        }
        confirmDialog.ask("Unsaved notes", "This workbook hasn't been saved yet. Save it first?",
                          ["Save", "Discard", "Cancel"], function (label) {
            if (answered)
                answered(label)
            if (label === "Save")
                win.saveThen(proceed)
            else if (label === "Discard")
                proceed()
        })
    }

    function saveThen(proceed) {
        if (backend.hasPath) {
            if (backend.save())
                proceed()
            return
        }
        win.openSaveDialog(proceed)
    }

    function openSaveDialog(after) {
        grid.commitEdit()
        win._afterSave = after || null
        saveDialog.currentFolder = backend.startFolder()
        saveDialog.selectedFile = backend.suggestedSavePath()
        saveDialog.open()
    }

    function openWorkbook() {
        grid.commitEdit()
        openDialog.currentFolder = backend.startFolder()
        openDialog.open()
    }

    function importFile() {
        grid.commitEdit()
        importFileDialog.currentFolder = backend.startFolder()
        importFileDialog.open()
    }

    function newWorkbook() {
        win.withDiscardCheck(function () { backend.newWorkbook() })
    }

    function showDialog(dialog) {
        grid.commitEdit()
        dialog.open()
    }

    // ---------------------------------------------------------------- tag menu
    function openTagMenu() {
        win._tagMenuFromSearch = topBar.search.inputFocused
        tagMenu.tags = backend.tagMenu()
        // QML has no global cursor position: open under the top bar, by the find box.
        tagMenu.popup(topBar, Math.max(8, topBar.width - tagMenu.width - 14), topBar.height + 4)
    }

    // ---------------------------------------------------------------- geometry
    function _screenAt(px, py) {
        const screens = Qt.application.screens
        for (let i = 0; i < screens.length; ++i) {
            const s = screens[i]
            if (px >= s.virtualX && px < s.virtualX + s.width && py >= s.virtualY && py < s.virtualY + s.height)
                return s
        }
        return null
    }

    // Geometry is applied now; showing waits for the event loop, so whoever created the window
    // (quick/main.py, or the test harness hiding it) has finished setting it up first.
    function _restoreGeometry() {
        const g = backend.windowGeometry()
        if (!g || g.length !== 5) {
            Qt.callLater(win._showRestored)
            return
        }
        let x = g[0], y = g[1]
        let w = Math.max(win.minimumWidth, g[2])
        let h = Math.max(win.minimumHeight, g[3])
        // Keep the title strip on a screen that still exists; else centre on the primary one.
        let s = win._screenAt(x + Math.min(w, 240) / 2, y + 12)
        if (s) {
            w = Math.min(w, s.width)
            h = Math.min(h, s.height)
            x = Math.max(s.virtualX - w + 120, Math.min(x, s.virtualX + s.width - 120))
            y = Math.max(s.virtualY + 30, Math.min(y, s.virtualY + s.height - 60))
        } else {
            s = Qt.application.screens[0]
            w = Math.min(w, s.width)
            h = Math.min(h, s.height)
            x = s.virtualX + Math.round((s.width - w) / 2)
            y = s.virtualY + Math.max(30, Math.round((s.height - h) / 2))
        }
        win.x = x
        win.y = y
        win.width = w
        win.height = h
        win._normalGeo = [x, y, w, h]
        win._startMaximized = !!g[4]
        Qt.callLater(win._showRestored)
    }

    function _showRestored() {
        if (win._startMaximized)
            win.showMaximized()
        else
            win.show()
    }

    function _saveGeometry() {
        const windowed = win.visibility === Window.Windowed
        const maximized = win.visibility === Window.Maximized || (!windowed && win._wasMaximized)
        const geo = (!windowed && win._normalGeo) ? win._normalGeo : [win.x, win.y, win.width, win.height]
        backend.saveWindowGeometry(Math.round(geo[0]), Math.round(geo[1]), Math.round(geo[2]),
                                   Math.round(geo[3]), maximized)
    }

    function _closeForReal() {
        win._closeConfirmed = true
        Qt.callLater(win.close)
    }

    width: 1280
    height: 800
    minimumWidth: 900
    minimumHeight: 560
    visible: false  // shown by _restoreGeometry once it sits where it was last time
    title: backend.windowTitle
    color: Theme.c.BG

    font.family: Theme.sans
    font.pixelSize: 13
    font.weight: Theme.wNormal

    // The Basic style's own bits (tooltips, scroll bars, selections) take the theme too.
    palette.window: Theme.c.BG
    palette.windowText: Theme.c.TEXT
    palette.base: Theme.c.FIELD
    palette.alternateBase: Theme.c.PANEL
    palette.text: Theme.c.TEXT
    palette.button: Theme.c.PANEL
    palette.buttonText: Theme.c.TEXT
    palette.highlight: Theme.c.HI
    palette.highlightedText: Theme.c.HI_TEXT
    palette.toolTipBase: Theme.c.MENU_BG
    palette.toolTipText: Theme.c.TEXT
    palette.placeholderText: Theme.c.MUTED
    palette.link: Theme.c.ACCENT
    palette.light: Theme.c.HOVER
    palette.midlight: Theme.c.BORDER
    palette.mid: Theme.c.SCROLL
    palette.dark: Theme.c.MENU_BORDER
    palette.shadow: "#000000"

    Component.onCompleted: {
        win._restoreGeometry()
        grid.focusGrid()
    }

    onClosing: (close) => {
        if (!win._closeConfirmed) {
            grid.commitEdit()
            if (backend.needsDiscardConfirm()) {
                close.accepted = false
                if (win._closeAsking)
                    return  // the close button again while its prompt is up: one prompt is enough
                win._closeAsking = true
                win.withDiscardCheck(win._closeForReal, function () { win._closeAsking = false })
                return
            }
        }
        win._saveGeometry()
        backend.shutdown()
    }

    onVisibilityChanged: {
        if (win.visibility === Window.Maximized)
            win._wasMaximized = true
        else if (win.visibility === Window.Windowed)
            win._wasMaximized = false
    }
    onXChanged: geoTimer.restart()
    onYChanged: geoTimer.restart()
    onWidthChanged: geoTimer.restart()
    onHeightChanged: geoTimer.restart()

    // Remember the un-maximized geometry (settled, so a maximize's own resize never counts).
    Timer {
        id: geoTimer
        interval: 250
        onTriggered: {
            if (win.visibility === Window.Windowed)
                win._normalGeo = [win.x, win.y, win.width, win.height]
        }
    }

    // ---------------------------------------------------------------- layout
    TopBar {
        id: topBar
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        height: 44
        onImportClicked: win.importFile()
        onExportClicked: win.showDialog(exportDialog)
        onSettingsClicked: win.showDialog(settingsDialog)
        onRefocusRequested: win.refocusGrid()
    }

    Item {
        id: centre
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: topBar.bottom
        anchors.bottom: sheetBar.top

        Effects {
            anchors.fill: parent
            effect: backend.effect
        }

        GP.Grid {
            id: grid
            anchors.fill: parent
        }
    }

    SheetBar {
        id: sheetBar
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        height: 32
        onRefocusRequested: win.refocusGrid()
        onDeleteRequested: (index) => {
            const notes = backend.sheetNoteCount(index)
            if (notes <= 0) {
                backend.deleteSheet(index)
                return
            }
            const name = backend.sheetNames[index]
            confirmDialog.ask("Delete sheet", "Delete “" + name + "” and its " + notes + " notes?",
                              ["Delete", "Cancel"], function (label) {
                if (label === "Delete")
                    backend.deleteSheet(index)
            }, "Cancel")  // like the classic: Enter keeps the sheet
        }
    }

    // ---------------------------------------------------------------- drag and drop
    DropArea {
        id: drop

        property string kind: ""
        property string fileName: ""

        anchors.fill: parent

        onEntered: (drag) => {
            const info = drag.hasUrls ? backend.classifyDrop(drag.urls) : null
            if (!info || info.kind === "") {
                drag.accepted = false
                return
            }
            // kind / fileName stay set after the drag leaves, so the card keeps its words while it fades.
            drop.kind = info.kind
            drop.fileName = String(info.path).split(/[\\/]/).pop()
            drag.accept(Qt.CopyAction)  // copy: Explorer must never move the file away
        }
        onDropped: (event) => {
            const info = event.hasUrls ? backend.classifyDrop(event.urls) : null
            if (!info || info.kind === "")
                return
            event.accept(Qt.CopyAction)
            const path = info.path
            if (info.kind === "open")
                win.withDiscardCheck(function () { backend.openPath(path) })
            else
                backend.beginImport(path)
        }
    }

    // Accent frame + a small card while a usable file hovers over the window.
    Item {
        id: dropHighlight
        anchors.fill: parent
        z: 1000
        opacity: drop.containsDrag ? 1 : 0  // only accepted drags count as contained
        visible: opacity > 0.01
        Behavior on opacity { NumberAnimation { duration: 160; easing.type: Easing.OutCubic } }

        Rectangle {
            anchors.fill: parent
            color: Theme.alpha(Theme.c.ACCENT, 0.06)
            border.width: 2
            border.color: Theme.c.ACCENT
        }

        Rectangle {
            anchors.centerIn: parent
            width: dropLabel.implicitWidth + 36
            height: 40
            radius: 6
            color: Theme.c.MENU_BG
            border.color: Theme.c.ACCENT
            scale: dropHighlight.opacity > 0.5 ? 1 : 0.94
            Behavior on scale { NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }

            Row {
                id: dropLabel
                anchors.centerIn: parent
                spacing: 8
                Icon {
                    anchors.verticalCenter: parent.verticalCenter
                    name: drop.kind === "open" ? "grid" : "upload"
                    color: Theme.c.ACCENT
                    size: 16
                }
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: (drop.kind === "open" ? "Open " : "Import ") + drop.fileName
                    textFormat: Text.PlainText
                    font.family: Theme.sans
                    font.pixelSize: 13
                    font.weight: Theme.wNormal
                    color: Theme.c.TEXT
                }
            }
        }
    }

    // ---------------------------------------------------------------- backend requests
    Connections {
        target: backend
        function onRenameRequested(index, name) { renameDialog.open(index, name) }
        function onImportReady(fileName, targetRef) { importDialog.open(fileName, targetRef) }
        function onAlert(title, message) { confirmDialog.alert(title, message) }
        function onSearchCleared() { topBar.search.clear() }
        function onSaveAsRequested() { win.openSaveDialog(null) }
    }

    // ---------------------------------------------------------------- shortcuts
    // Only Ctrl / F-key chords, so plain typing always reaches the grid or the find box. Text
    // inputs claim their own editing chords (Ctrl+Z/Y/C/V/A...) first, so while the cell editor
    // or the find box has focus, Ctrl+Z undoes typing there and these never fire on top.
    component WindowKey: Shortcut {
        context: Qt.WindowShortcut
        autoRepeat: false
    }

    WindowKey { sequence: "Ctrl+F"; onActivated: topBar.search.focusFind() }
    WindowKey { sequence: "Ctrl+S"; onActivated: backend.save() }
    WindowKey { sequence: "Ctrl+Shift+S"; onActivated: win.openSaveDialog(null) }
    WindowKey { sequence: "Ctrl+O"; onActivated: win.openWorkbook() }
    WindowKey { sequence: "Ctrl+N"; onActivated: win.newWorkbook() }
    WindowKey { sequence: "Ctrl+B"; onActivated: backend.toggleBold() }
    WindowKey { sequence: "Ctrl+K"; onActivated: backend.toggleCheck() }
    WindowKey { sequence: "Ctrl+L"; onActivated: grid.toggleBullet() }
    WindowKey { sequence: "Ctrl+E"; onActivated: win.showDialog(exportDialog) }
    WindowKey { sequence: "Ctrl+Shift+T"; onActivated: win.openTagMenu() }
    WindowKey { sequence: "F1"; onActivated: win.showDialog(helpDialog) }
    WindowKey { sequence: "Ctrl+,"; onActivated: win.showDialog(settingsDialog) }
    WindowKey {
        sequence: "Ctrl+Z"
        autoRepeat: true
        onActivated: {
            if (!grid.editorUndo())
                backend.undo()
        }
    }
    WindowKey {
        sequences: ["Ctrl+Y", "Ctrl+Shift+Z"]
        autoRepeat: true
        onActivated: {
            if (!grid.editorRedo())
                backend.redo()
        }
    }
    WindowKey { sequence: "Ctrl+I"; onActivated: win.importFile() }
    WindowKey {
        sequence: "Ctrl+H"
        onActivated: {
            grid.commitEdit()
            replaceDialog.open(backend.query)
        }
    }
    WindowKey { sequence: "F8"; onActivated: backend.toggleFreeze() }
    WindowKey { sequence: "Ctrl+T"; onActivated: backend.addSheet() }
    WindowKey { sequences: ["Ctrl+PgDown", "Ctrl+Tab"]; autoRepeat: true; onActivated: backend.stepSheet(1) }
    WindowKey { sequences: ["Ctrl+PgUp", "Ctrl+Shift+Tab"]; autoRepeat: true; onActivated: backend.stepSheet(-1) }

    // ---------------------------------------------------------------- menus
    GPMenu {
        id: tagMenu

        property var tags: []
        property Item clearItem: null

        function indexOfItem(object) {
            for (let i = 0; i < tagMenu.count; ++i) {
                if (tagMenu.itemAt(i) === object)
                    return i
            }
            return -1
        }

        onClosed: {
            if (win._tagMenuFromSearch)
                topBar.search.focusInput()
            else
                win.refocusGrid()
        }

        Instantiator {
            model: tagMenu.tags
            delegate: GPMenuItem {
                required property var modelData
                text: "#" + modelData.tag + "   ·   " + modelData.count
                checkable: true
                checked: modelData.checked
                onTriggered: backend.setFilter(modelData.tag)
            }
            onObjectAdded: (index, object) => tagMenu.insertItem(index, object)
            onObjectRemoved: (index, object) => tagMenu.takeItem(tagMenu.indexOfItem(object))
        }

        Instantiator {
            model: tagMenu.tags.length === 0 ? 1 : 0
            delegate: GPMenuItem {
                text: "No tags yet — write #word inside a note"
                enabled: false
            }
            onObjectAdded: (index, object) => tagMenu.insertItem(0, object)
            onObjectRemoved: (index, object) => tagMenu.takeItem(tagMenu.indexOfItem(object))
        }

        // Separator + "Clear filter" close the menu when there are tags. The two Instantiators
        // update in no fixed order, so the separator always slots in just before Clear.
        Instantiator {
            model: tagMenu.tags.length > 0 ? 1 : 0
            delegate: GPMenuSeparator { }
            onObjectAdded: (index, object) => {
                const at = tagMenu.clearItem ? tagMenu.indexOfItem(tagMenu.clearItem) : -1
                tagMenu.insertItem(at >= 0 ? at : tagMenu.count, object)
            }
            onObjectRemoved: (index, object) => tagMenu.takeItem(tagMenu.indexOfItem(object))
        }

        Instantiator {
            model: tagMenu.tags.length > 0 ? 1 : 0
            delegate: GPMenuItem {
                // Lined up with the tag items' text, which leaves room for their check mark.
                leftPadding: 30
                text: "Clear filter"
                enabled: backend.filterTag !== ""
                onTriggered: backend.setFilter("")
            }
            onObjectAdded: (index, object) => {
                tagMenu.clearItem = object
                tagMenu.addItem(object)
            }
            onObjectRemoved: (index, object) => {
                tagMenu.clearItem = null
                tagMenu.takeItem(tagMenu.indexOfItem(object))
            }
        }
    }

    // ---------------------------------------------------------------- file dialogs (native)
    FileDialog {
        id: saveDialog
        title: "Save workbook"
        fileMode: FileDialog.SaveFile
        nameFilters: ["GridPad workbook (*.gridpad)"]
        defaultSuffix: "gridpad"
        onAccepted: {
            const after = win._afterSave
            win._afterSave = null
            if (backend.saveTo(String(saveDialog.selectedFile)) && after)
                after()
            win.refocusGrid()
        }
        onRejected: {
            win._afterSave = null
            win.refocusGrid()
        }
    }

    FileDialog {
        id: openDialog
        title: "Open workbook"
        fileMode: FileDialog.OpenFile
        nameFilters: ["GridPad workbook (*.gridpad)"]
        onAccepted: {
            const url = String(openDialog.selectedFile)
            win.withDiscardCheck(function () { backend.openPath(url) })
            win.refocusGrid()
        }
        onRejected: win.refocusGrid()
    }

    FileDialog {
        id: importFileDialog
        title: "Import CSV or text"
        fileMode: FileDialog.OpenFile
        nameFilters: ["CSV or text (*.csv *.txt)", "All files (*.*)"]
        onAccepted: backend.beginImport(String(importFileDialog.selectedFile))
        onRejected: win.refocusGrid()
    }

    // ---------------------------------------------------------------- dialogs (one of each)
    SettingsDialog { id: settingsDialog; onClosed: win.refocusGrid() }
    ExportDialog { id: exportDialog; onClosed: win.refocusGrid() }
    ImportDialog { id: importDialog; onClosed: win.refocusGrid() }
    ReplaceDialog { id: replaceDialog; onClosed: win.refocusGrid() }
    HelpDialog { id: helpDialog; onClosed: win.refocusGrid() }
    RenameDialog { id: renameDialog; onClosed: win.refocusGrid() }
    ConfirmDialog { id: confirmDialog; onClosed: win.refocusGrid() }
}
