import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import QtQuick.Shapes
import QtQuick.Dialogs
import "."

ApplicationWindow {
    id: win
    width: 1600
    height: 960
    minimumWidth: 1240
    minimumHeight: 760
    visible: true
    title: Store.video ? `${Store.video.name} – MeGaA Clipper` : "MeGaA Clipper"
    color: Theme.bg
    font.family: Theme.ui

    // a text box has the keyboard: the editor shortcuts stay quiet
    readonly property bool typing: activeFocusItem !== null && activeFocusItem.cursorPosition !== undefined
    readonly property bool keysOn: !!Store.video && !typing && !player.visible

    // test runs (testMode) stay behind other windows and never take the keyboard
    flags: testMode ? Qt.Window | Qt.WindowStaysOnBottomHint | Qt.WindowDoesNotAcceptFocus : Qt.Window
    Component.onCompleted: {
        if (testMode) { x = 0; y = 0; width = 1920; height = 1009 }
        else showMaximized()
    }

    // testing aid (MEGAA_TEST in clipper_qml.py): run a script against the editor
    function runTest(code) {
        try { new Function("Store", "stage", "win", "inspector", "backend", code)(Store, stage, win, inspector, backend) }
        catch (err) { console.warn(`test script failed: ${err}`) }
    }

    // ------------------------------------------------------------ backdrop: two soft neon glows
    Shape {
        anchors.fill: parent
        ShapePath {
            strokeWidth: -1
            fillGradient: RadialGradient {
                centerX: win.width * 0.12; centerY: -60; centerRadius: win.width * 0.45
                focalX: centerX; focalY: centerY
                GradientStop { position: 0; color: Qt.rgba(0, 229 / 255, 1, 0.10) }
                GradientStop { position: 1; color: "transparent" }
            }
            PathRectangle { width: win.width; height: win.height }
        }
        ShapePath {
            strokeWidth: -1
            fillGradient: RadialGradient {
                centerX: win.width * 0.92; centerY: win.height + 80; centerRadius: win.width * 0.42
                focalX: centerX; focalY: centerY
                GradientStop { position: 0; color: Qt.rgba(1, 43 / 255, 214 / 255, 0.08) }
                GradientStop { position: 1; color: "transparent" }
            }
            PathRectangle { width: win.width; height: win.height }
        }
    }

    Item { id: focusSink; focus: true }
    Connections {
        target: Store
        function onReleaseFocus() { focusSink.forceActiveFocus() }
        function onPlayClip(clip) { player.show(clip) }
        function onPickAudioRequested(kind) { audioDialog.kind = kind; audioDialog.open() }
        function onDialogRequested(name) {
            if (name === "settings") settingsDlg.show()
            else if (name === "moments") momentsDlg.show()
            else if (name === "campaigns") campaignsDlg.show()
            else if (name === "tracker") trackerDlg.show()
            else if (name === "posted") postedDlg.show(Store.postTarget)
        }
        function onAskRequested(title, text, okText, action) { askDlg.show(title, text, okText, action) }
    }

    // the text item under scene point p (walking down the top-most visible items), or null
    function textItemAt(p) {
        let item = contentItem
        while (item) {
            if (item.cursorPosition !== undefined) return item
            let next = null
            for (const c of item.children)
                if (c !== pressWatch && c.visible && c.contains(c.mapFromItem(null, p.x, p.y)) && (!next || c.z >= next.z)) next = c
            item = next
        }
        return null
    }

    // web: a mouse press outside the text box being typed in blurs it (its change / commit runs first),
    // so a click on Play, a chip, a tab, a switch or a slider gives the keys back to the shortcuts.
    // A press in another text box leaves the focus change to that box.
    function blurOnPress(p) {
        if (!typing) return
        const f = activeFocusItem
        if (f.visible && f.contains(f.mapFromItem(null, p.x, p.y))) return
        if (textItemAt(p)) return
        Store.releaseFocus()
    }

    // the text box with the keyboard was hidden (inspector tab switched, transcript row scrolled away):
    // a hidden box would still take every key
    Connections {
        target: win.activeFocusItem
        ignoreUnknownSignals: true
        function onVisibleChanged() { if (win.typing && !win.activeFocusItem.visible) Store.releaseFocus() }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 14
        spacing: 12

        TopBar {
            Layout.fillWidth: true
            Layout.preferredHeight: 58
            onOpenRequested: fileDialog.open()
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 12
            TranscriptPanel {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.minimumWidth: 330
            }
            StagePanel {
                id: stage
                Layout.preferredWidth: Math.min(470, Math.max(360, win.width * 0.27))
                Layout.fillHeight: true
            }
            Inspector {
                id: inspector
                Layout.preferredWidth: 380
                Layout.fillHeight: true
            }
        }

        QueuePanel {
            Layout.fillWidth: true
            Layout.preferredHeight: 236
        }
    }

    Welcome {
        anchors.fill: parent
        visible: !Store.video
        onOpenRequested: fileDialog.open()
    }

    ClipPlayer {
        id: player
        anchors.fill: parent
        onOpened: Store.pauseRequested()
    }

    SettingsDialog { id: settingsDlg }
    MomentsDialog { id: momentsDlg }
    CampaignsDialog { id: campaignsDlg }
    TrackerDialog { id: trackerDlg }
    PostedDialog { id: postedDlg }
    ConfirmDialog { id: askDlg }   // last: a question can come from another window

    Toasts {
        parent: Overlay.overlay   // above the windows (a toast can come from one)
        z: 1000
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.margins: 30
    }

    // above everything, so it sees each press before the control under it; it only watches (passive grab)
    Item {
        id: pressWatch
        anchors.fill: parent
        z: 100000
        PointHandler {
            acceptedButtons: Qt.AllButtons
            onActiveChanged: if (active) win.blurOnPress(point.scenePosition)
        }
    }

    FileDialog {
        id: fileDialog
        title: "Open a video"
        nameFilters: ["Videos (*.mp4 *.mov *.mkv *.webm *.avi *.m4v *.ts)", "All files (*)"]
        onAccepted: Store.openVideo(selectedFile.toString())
    }

    // background music / the sound on muted words (Edit tab); cancelling changes nothing
    FileDialog {
        id: audioDialog
        property string kind: "music"   // "music", "sfx" (Choose file) or "sfx-tile" (the Custom tile)
        title: kind === "music" ? "Choose background music" : "Choose a sound for muted words"
        nameFilters: ["Audio (*.mp3 *.m4a *.aac *.wav *.ogg *.flac)", "All files (*)"]
        onAccepted: Store.audioPicked(kind, selectedFile.toString())
    }

    // the engine runs jobs in its own threads; ask how they are going (faster while something runs)
    Timer {
        interval: 1500
        running: true
        repeat: true
        triggeredOnStart: true
        onTriggered: interval = Store.poll() ? 400 : 1500
    }

    // ------------------------------------------------------------ keyboard
    Shortcut { sequence: "Space"; enabled: win.keysOn; onActivated: stage.togglePlay() }
    Shortcut { sequence: "I"; enabled: win.keysOn; onActivated: Store.setIn() }
    Shortcut { sequence: "O"; enabled: win.keysOn; onActivated: Store.setOut() }
    Shortcut { sequence: "J"; enabled: win.keysOn; onActivated: stage.seek(Store.playhead - 5) }
    Shortcut { sequence: "L"; enabled: win.keysOn; onActivated: stage.seek(Store.playhead + 5) }
    Shortcut { sequence: "K"; enabled: win.keysOn; onActivated: stage.pause() }
    Shortcut { sequence: "Left"; enabled: win.keysOn; onActivated: stage.seek(Store.playhead - 1) }
    Shortcut { sequence: "Right"; enabled: win.keysOn; onActivated: stage.seek(Store.playhead + 1) }
    Shortcut { sequence: "Shift+Left"; enabled: win.keysOn; onActivated: stage.seek(Store.playhead - 0.1) }
    Shortcut { sequence: "Shift+Right"; enabled: win.keysOn; onActivated: stage.seek(Store.playhead + 0.1) }
    Shortcut { sequences: ["Return", "Enter"]; enabled: win.keysOn; onActivated: Store.addClip(false) }
    Shortcut { sequences: ["Shift+Return", "Shift+Enter"]; enabled: win.keysOn; onActivated: Store.addClip(true) }
    Shortcut { sequence: "/"; enabled: win.keysOn && Store.lines.length > 0; onActivated: Store.searchRequested() }
    Shortcut { sequences: ["X", "Shift+X"]; enabled: win.keysOn; onActivated: Store.setCutMode(!Store.cutMode) }
    Shortcut { sequences: ["M", "Shift+M"]; enabled: win.keysOn; onActivated: Store.setMuteMode(!Store.muteMode) }
    Shortcut { sequences: ["Ctrl+Z"]; enabled: win.keysOn; onActivated: Store.undo() }   // text boxes keep their own undo
    Shortcut { sequences: ["Ctrl+Y", "Ctrl+Shift+Z"]; enabled: win.keysOn; onActivated: Store.redo() }
    Timer { interval: 250; running: true; repeat: true; onTriggered: Store.historyTick() }
    Shortcut { sequences: ["S", "Shift+S"]; enabled: win.keysOn; onActivated: Store.addSplit() }
    Shortcut { sequences: ["Delete", "Backspace"]; enabled: win.keysOn && Store.selectedPart >= 0; onActivated: Store.deletePart() }
    Shortcut { sequence: "Escape"; enabled: win.keysOn && Store.selectedPart >= 0; onActivated: Store.selectedPart = -1 }
    Shortcut { sequence: "Ctrl+O"; enabled: !Store.busy; onActivated: fileDialog.open() }
    Shortcut { sequence: "Escape"; enabled: player.visible; onActivated: player.close() }
}
