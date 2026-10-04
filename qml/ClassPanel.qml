import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs
import QtQuick.Layouts

Rectangle {
    id: panel

    property var nodeClasses: []
    property var edgeClasses: []
    property string currentNodeClass: "Звичайна"
    property string currentEdgeClass: "Звичайне"

    property string family: "node"
    readonly property bool nodesShown: family === "node"
    readonly property var classes: nodesShown ? nodeClasses : edgeClasses
    readonly property string currentClass: nodesShown ? currentNodeClass
                                                      : currentEdgeClass

    readonly property bool editing: currentClass !== ""

    function pick(name) {
        if (nodesShown)
            currentNodeClass = name
        else
            currentEdgeClass = name
    }

    function toggleFamily() {
        family = nodesShown ? "edge" : "node"
    }

    function stepClass(delta) {
        var names = classes.map(function (c) { return c.name })
        var i = names.indexOf(currentClass)
        if (i === -1) {
            if (delta < 0 && currentClass === "")
                nameField.forceActiveFocus()
            else if (delta < 0)
                pickAt(names.length - 1)
            return
        }
        i = Math.max(0, i + delta)
        pickAt(i)
        if (i === names.length)
            nameField.forceActiveFocus()
    }
    function pickAt(i) {
        var names = classes.map(function (c) { return c.name })
        pick(i < names.length ? names[i] : "")
        if (i < names.length)
            classList.positionViewAtIndex(i, ListView.Contain)
    }

    function indexOfClass(name) {
        for (var i = 0; i < classes.length; i++)
            if (classes[i].name === name)
                return i
        return -1
    }
    readonly property string defaultClass: {
        for (var i = 0; i < classes.length; i++)
            if (classes[i].default === true)
                return classes[i].name
        return ""
    }

    function moveCurrent(delta) {
        var i = indexOfClass(currentClass)
        var to = Math.max(0, Math.min(classes.length - 1, i + delta))
        if (i === -1 || to === i)
            return
        backend.moveClass(family, currentClass, to)
        classList.positionViewAtIndex(to, ListView.Contain)
    }

    function removeClass(name) {
        var cls = classes[indexOfClass(name)]
        if (!cls)
            return
        if (cls.default === true) {
            backend.removeClass(family, name)
            return
        }
        removeDialog.family = family
        removeDialog.name = name
        removeDialog.count = cls.count
        removeDialog.ask()
    }

    FileDialog {
        id: saveDialog
        title: "Зберегти граф"
        fileMode: FileDialog.SaveFile
        nameFilters: ["Граф JSON (*.json)", "Усі файли (*)"]
        defaultSuffix: "json"
        onAccepted: backend.saveToFile(selectedFile)
    }

    FileDialog {
        id: openDialog
        title: "Відкрити граф"
        fileMode: FileDialog.OpenFile
        nameFilters: ["Граф JSON (*.json)", "Усі файли (*)"]
        onAccepted: backend.loadFromFile(selectedFile)
    }

    ConfirmDialog {
        id: removeDialog
        property string family
        property string name
        property int count

        key: "removeClass"
        title: "Видалити клас «" + name + "»?"
        text: count === 0 ? "Клас порожній."
            : (family === "node" ? "Разом із ним буде видалено вершин: "
                                 : "Разом із ним буде видалено ребер: ")
              + count + "."
        onConfirmed: {
            backend.removeClass(family, name)
            if (family === "node" && panel.currentNodeClass === name)
                panel.currentNodeClass = ""
            else if (family === "edge" && panel.currentEdgeClass === name)
                panel.currentEdgeClass = ""
        }
    }

    property string renaming: ""
    function finishRename(newName) {
        var old = renaming
        renaming = ""
        newName = newName.trim()
        if (old === "" || newName === "" || newName === old
                || !backend.renameClass(family, old, newName))
            return
        if (currentClass === old)
            pick(newName)
    }
    onFamilyChanged: renaming = ""

    property int dragIndex: -1
    property real dragOffset: 0
    readonly property real rowStep: Theme.classRowHeight + classList.spacing
    readonly property int dropIndex: dragIndex === -1 ? -1
        : Math.max(0, Math.min(classes.length - 1,
                               dragIndex + Math.round(dragOffset / rowStep)))
    function rowShift(i) {
        if (dragIndex === -1)
            return 0
        if (i === dragIndex)
            return dragOffset
        if (i > dragIndex && i <= dropIndex)
            return -rowStep
        if (i < dragIndex && i >= dropIndex)
            return rowStep
        return 0
    }
    function finishDrag() {
        var from = dragIndex, to = dropIndex
        dragIndex = -1
        dragOffset = 0
        if (from !== -1 && to !== from)
            backend.moveClass(family, classes[from].name, to)
    }

    function cycle(list, value, delta) {
        var i = list.indexOf(value)
        return list[(i + delta + list.length) % list.length]
    }
    function keysOf(defs) {
        return defs.map(function (d) { return d.key })
    }
    function stepStyle(what, delta) {
        if (what === "color")
            newColor = cycle(Theme.nodePalette.map(String), newColor, delta)
        else if (what === "shape")
            newShape = cycle(keysOf(shapeDefs), newShape, delta)
        else if (what === "line")
            newLine = cycle(keysOf(lineDefs), newLine, delta)
        else if (what === "width")
            newWidth = cycle(widthDefs, newWidth, delta)
        else if (what === "directed")
            newDirected = !newDirected
        pushDesign()
    }

    function submitNew() {
        var name = nameField.text.trim()
        if (name === "") {
            nameField.forceActiveFocus()
            return
        }
        if (!backend.createClass(family, name, design()))
            return
        pick(name)
        nameField.text = ""
    }

    function design() {
        return nodesShown
            ? { shape: newShape, color: newColor, opacity: newOpacity }
            : { color: newColor, width: newWidth, line: newLine,
                directed: newDirected }
    }

    property bool keyboard: true
    property bool arrows: true

    Shortcut {
        sequence: "Tab"
        enabled: panel.keyboard
        onActivated: panel.toggleFamily()
    }
    Shortcut {
        sequences: ["Return", "Enter"]
        enabled: panel.keyboard && !panel.editing
        onActivated: panel.submitNew()
    }
    Shortcut {
        sequence: "Up"
        enabled: panel.keyboard && panel.arrows
        onActivated: panel.stepClass(-1)
    }
    Shortcut {
        sequence: "Down"
        enabled: panel.keyboard && panel.arrows
        onActivated: panel.stepClass(1)
    }
    Shortcut {
        sequence: "Alt+Up"
        enabled: panel.keyboard && panel.arrows && panel.editing
        onActivated: panel.moveCurrent(-1)
    }
    Shortcut {
        sequence: "Alt+Down"
        enabled: panel.keyboard && panel.arrows && panel.editing
        onActivated: panel.moveCurrent(1)
    }
    Shortcut {
        sequence: "Backspace"
        enabled: panel.keyboard && panel.arrows && panel.editing
        onActivated: panel.removeClass(panel.currentClass)
    }
    Shortcut {
        sequence: "Left"
        enabled: panel.keyboard && panel.arrows
        onActivated: panel.stepStyle("color", -1)
    }
    Shortcut {
        sequence: "Right"
        enabled: panel.keyboard && panel.arrows
        onActivated: panel.stepStyle("color", 1)
    }
    Shortcut {
        sequence: "Shift+Left"
        enabled: panel.keyboard && panel.arrows
        onActivated: panel.stepStyle(panel.nodesShown ? "shape" : "line", -1)
    }
    Shortcut {
        sequence: "Shift+Right"
        enabled: panel.keyboard && panel.arrows
        onActivated: panel.stepStyle(panel.nodesShown ? "shape" : "line", 1)
    }
    Shortcut {
        sequence: "Ctrl+Left"
        enabled: panel.keyboard && panel.arrows && !panel.nodesShown
        onActivated: panel.stepStyle("width", -1)
    }
    Shortcut {
        sequence: "Ctrl+Right"
        enabled: panel.keyboard && panel.arrows && !panel.nodesShown
        onActivated: panel.stepStyle("width", 1)
    }
    Shortcut {
        sequences: ["Ctrl+Shift+Left", "Ctrl+Shift+Right"]
        enabled: panel.keyboard && panel.arrows && !panel.nodesShown
        onActivated: panel.stepStyle("directed", 1)
    }

    function loadDesign() {
        if (!editing)
            return
        for (var i = 0; i < classes.length; i++) {
            var c = classes[i]
            if (c.name !== currentClass)
                continue
            newColor = String(c.color)
            if (nodesShown) {
                newShape = c.shape
                newOpacity = c.opacity
            } else {
                newLine = c.line
                newWidth = c.width
                newDirected = c.directed === true
            }
            return
        }
    }

    function pushDesign() {
        if (!editing)
            return
        backend.updateClass(family, currentClass, design())
    }

    onCurrentClassChanged: loadDesign()
    onClassesChanged: loadDesign()

    readonly property var familyDefs: [
        { key: "node", label: "Вершини" },
        { key: "edge", label: "Ребра" }
    ]
    readonly property var shapeDefs: [
        { key: "circle",   glyph: "●" },
        { key: "square",   glyph: "■" }
    ]
    readonly property var lineDefs: [
        { key: "solid", glyph: "──" },
        { key: "dash",  glyph: "╌╌" },
        { key: "dot",   glyph: "┈┈" }
    ]
    readonly property var widthDefs: Theme.edgeWidths
    readonly property var dirDefs: [
        { key: false, glyph: "──" },
        { key: true,  glyph: "──▶" }
    ]

    function glyphIn(defs, key) {
        for (var i = 0; i < defs.length; i++)
            if (defs[i].key === key)
                return defs[i].glyph
        return defs[0].glyph
    }
    function classGlyph(cls) {
        return nodesShown ? glyphIn(shapeDefs, cls.shape === "circle" ? "circle" : "square")
                          : glyphIn(lineDefs, cls.line)
                            + (cls.directed === true ? "▶" : "")
    }

    property string newShape: "circle"
    property string newLine: "solid"
    property real newWidth: Theme.edgeWidths[0]
    property string newColor: Theme.nodePalette[0]
    property real newOpacity: 1.0
    property bool newDirected: false

    width: Theme.panelWidth
    color: Theme.panel

    MouseArea {
        anchors.fill: parent
        onClicked: panel.pick("")
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.spaceMd
        spacing: Theme.spaceSm

        Label {
            text: "Класи"
            color: Theme.foreground
            font.bold: true
            font.pixelSize: 14
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.spaceSm
            Repeater {
                model: panel.familyDefs
                delegate: Rectangle {
                    required property var modelData
                    Layout.fillWidth: true
                    height: Theme.listItemHeight
                    radius: Theme.radiusMd
                    color: panel.family === modelData.key
                           ? Theme.accent
                           : famHover.containsMouse ? Theme.hover
                                                    : Theme.control
                    border.width: panel.family === modelData.key ? 0 : Theme.strokeHairline
                    border.color: Theme.border
                    Behavior on color { ColorAnimation { duration: Theme.hoverDuration } }

                    Text {
                        anchors.centerIn: parent
                        text: parent.modelData.label
                        color: Theme.foreground
                        font.pixelSize: 12
                    }
                    MouseArea {
                        id: famHover
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: panel.family = parent.modelData.key
                    }
                }
            }
        }

        ListView {
            id: classList
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            spacing: Theme.spaceXs
            model: panel.classes
            interactive: panel.dragIndex === -1

            TapHandler {
                onTapped: panel.pick("")
            }

            delegate: Item {
                id: slot
                required property var modelData
                required property int index
                readonly property bool dragged: panel.dragIndex === index
                readonly property bool renamingThis:
                    panel.renaming === modelData.name

                width: classList.width
                height: Theme.classRowHeight
                z: dragged ? 1 : 0

                Rectangle {
                    id: row
                    width: parent.width
                    height: parent.height
                    y: panel.rowShift(slot.index)
                    Behavior on y {
                        enabled: !slot.dragged
                        NumberAnimation { duration: 120; easing.type: Easing.OutQuad }
                    }
                    radius: Theme.radiusMd
                    color: panel.currentClass === slot.modelData.name
                           ? Theme.accent
                           : slot.dragged || rowHover.containsMouse
                             ? Theme.hover : "transparent"
                    border.width: slot.dragged ? Theme.strokeHairline : 0
                    border.color: Theme.border
                    Behavior on color { ColorAnimation { duration: Theme.hoverDuration } }

                    MouseArea {
                        id: rowHover
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: panel.pick(
                            panel.currentClass === slot.modelData.name
                                ? "" : slot.modelData.name)
                        onDoubleClicked: {
                            panel.pick(slot.modelData.name)
                            panel.renaming = slot.modelData.name
                        }
                    }

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: Theme.spaceXs
                        anchors.rightMargin: Theme.spaceSm
                        spacing: Theme.spaceSm

                        Text {
                            text: "⋮⋮"
                            color: grip.containsMouse || slot.dragged
                                   ? Theme.foreground
                                   : panel.currentClass === slot.modelData.name
                                     ? Qt.alpha(Theme.foreground, 0.6)
                                     : Theme.faintText
                            font.pixelSize: 12
                            Layout.preferredWidth: 14
                            horizontalAlignment: Text.AlignHCenter

                            MouseArea {
                                id: grip
                                anchors.fill: parent
                                anchors.margins: -Theme.spaceXs
                                hoverEnabled: true
                                preventStealing: true
                                cursorShape: slot.dragged ? Qt.ClosedHandCursor
                                                          : Qt.OpenHandCursor
                                property real pressY: 0
                                onPressed: function (mouse) {
                                    pressY = mapToItem(classList, 0, mouse.y).y
                                    panel.dragIndex = slot.index
                                }
                                onPositionChanged: function (mouse) {
                                    if (slot.dragged)
                                        panel.dragOffset =
                                            mapToItem(classList, 0, mouse.y).y
                                            - pressY
                                }
                                onReleased: panel.finishDrag()
                                onCanceled: {
                                    panel.dragIndex = -1
                                    panel.dragOffset = 0
                                }
                            }
                        }
                        Text {
                            text: panel.classGlyph(slot.modelData)
                            color: slot.modelData.color
                            opacity: (panel.nodesShown ? slot.modelData.opacity : 1)
                                     * (slot.modelData.hidden ? 0.4 : 1)
                            font.pixelSize: panel.nodesShown ? 18 : 14
                            font.bold: !panel.nodesShown && slot.modelData.width >= 4
                        }
                        Label {
                            visible: !slot.renamingThis
                            text: slot.modelData.name
                            color: Theme.foreground
                            opacity: slot.modelData.hidden ? 0.5 : 1
                            elide: Text.ElideRight
                            Layout.fillWidth: true
                        }
                        LineField {
                            id: renameField
                            visible: slot.renamingThis
                            Layout.fillWidth: true
                            onVisibleChanged: if (visible) {
                                text = slot.modelData.name
                                selectAll()
                                forceActiveFocus()
                            }
                            onAccepted: panel.forceActiveFocus()
                            onActiveFocusChanged:
                                if (!activeFocus && slot.renamingThis)
                                    panel.finishRename(text)
                            Keys.onShortcutOverride: function (event) {
                                event.accepted = event.key === Qt.Key_Escape
                            }
                            Keys.onEscapePressed: {
                                panel.renaming = ""
                                panel.forceActiveFocus()
                            }
                        }
                        Label {
                            text: slot.modelData.count
                            color: Theme.mutedText
                            font.pixelSize: 11
                        }
                        Text {
                            text: "👁"
                            font.pixelSize: 13
                            color: Theme.foreground
                            opacity: slot.modelData.hidden ? 0.25
                                   : eye.containsMouse ? 1 : 0.6
                            Layout.preferredWidth: 16
                            horizontalAlignment: Text.AlignHCenter

                            Rectangle {
                                visible: slot.modelData.hidden
                                anchors.centerIn: parent
                                width: parent.width + 2
                                height: 1.5
                                rotation: -35
                                color: Theme.foreground
                            }
                            MouseArea {
                                id: eye
                                anchors.fill: parent
                                anchors.margins: -Theme.spaceXs
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: backend.setClassHidden(
                                    panel.family, slot.modelData.name,
                                    !slot.modelData.hidden)
                            }
                        }
                    }
                }
            }
        }

        FlatButton {
            text: "З'єднати всі"
            visible: panel.nodesShown
            enabled: panel.currentNodeClass !== ""
            Layout.fillWidth: true
            onClicked: backend.connectClassNodes(panel.currentNodeClass,
                                                 panel.currentEdgeClass)
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.topMargin: Theme.spaceXs
            Layout.bottomMargin: Theme.spaceXs
            height: Theme.strokeHairline
            color: Theme.border
        }

        Label {
            text: panel.editing ? "Клас «" + panel.currentClass + "»"
                                : "Новий клас"
            color: Theme.mutedText
            font.pixelSize: 12
            elide: Text.ElideRight
            Layout.fillWidth: true
        }

        LineField {
            id: nameField
            visible: !panel.editing
            Layout.fillWidth: true
            placeholderText: "Назва класу"

            onAccepted: panel.submitNew()
            Keys.onShortcutOverride: function (event) {
                event.accepted = event.key === Qt.Key_Escape
            }
            Keys.onEscapePressed: panel.forceActiveFocus()
            Keys.onDownPressed: panel.forceActiveFocus()
            Keys.onUpPressed: {
                panel.forceActiveFocus()
                panel.pickAt(panel.classes.length - 1)
            }
        }

        GridLayout {
            columns: 4
            columnSpacing: Theme.spaceSm
            visible: panel.nodesShown
            Repeater {
                model: panel.shapeDefs
                delegate: Rectangle {
                    required property var modelData
                    width: Theme.optionTileSm; height: Theme.optionTileSm
                    radius: Theme.radiusMd
                    color: panel.newShape === modelData.key
                           ? Theme.accent
                           : shapeHover.containsMouse ? Theme.hover
                                                      : Theme.control
                    border.width: panel.newShape === modelData.key ? 0 : Theme.strokeHairline
                    border.color: Theme.border
                    Behavior on color { ColorAnimation { duration: Theme.hoverDuration } }

                    Text {
                        anchors.centerIn: parent
                        text: parent.modelData.glyph
                        color: Theme.foreground
                        font.pixelSize: 16
                    }
                    MouseArea {
                        id: shapeHover
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            panel.newShape = parent.modelData.key
                            panel.pushDesign()
                        }
                    }
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            visible: panel.nodesShown
            Label {
                text: "Прозорість"
                color: Theme.mutedText
                font.pixelSize: 12
                Layout.fillWidth: true
            }
            Label {
                text: Math.round(panel.newOpacity * 100) + "%"
                color: Theme.mutedText
                font.pixelSize: 12
            }
        }
        Slider {
            id: opacitySlider
            Layout.fillWidth: true
            visible: panel.nodesShown
            from: 0.1
            to: 1.0
            value: panel.newOpacity
            onMoved: {
                panel.newOpacity = value
                panel.pushDesign()
            }
            Connections {
                target: panel
                function onNewOpacityChanged() {
                    opacitySlider.value = panel.newOpacity
                }
            }
        }

        GridLayout {
            columns: 3
            columnSpacing: Theme.spaceSm
            visible: !panel.nodesShown
            Repeater {
                model: panel.lineDefs
                delegate: Rectangle {
                    required property var modelData
                    width: Theme.optionTileSm; height: Theme.optionTileSm
                    radius: Theme.radiusMd
                    color: panel.newLine === modelData.key
                           ? Theme.accent
                           : lineHover.containsMouse ? Theme.hover
                                                     : Theme.control
                    border.width: panel.newLine === modelData.key ? 0 : Theme.strokeHairline
                    border.color: Theme.border
                    Behavior on color { ColorAnimation { duration: Theme.hoverDuration } }

                    Text {
                        anchors.centerIn: parent
                        text: parent.modelData.glyph
                        color: Theme.foreground
                        font.pixelSize: 14
                    }
                    MouseArea {
                        id: lineHover
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            panel.newLine = parent.modelData.key
                            panel.pushDesign()
                        }
                    }
                }
            }
        }

        GridLayout {
            columns: 3
            columnSpacing: Theme.spaceSm
            visible: !panel.nodesShown
            Repeater {
                model: panel.widthDefs
                delegate: Rectangle {
                    required property real modelData
                    width: Theme.optionTileSm; height: Theme.optionTileSm
                    radius: Theme.radiusMd
                    color: panel.newWidth === modelData
                           ? Theme.accent
                           : widthHover.containsMouse ? Theme.hover
                                                      : Theme.control
                    border.width: panel.newWidth === modelData ? 0 : Theme.strokeHairline
                    border.color: Theme.border
                    Behavior on color { ColorAnimation { duration: Theme.hoverDuration } }

                    Rectangle {
                        anchors.centerIn: parent
                        width: 20
                        height: parent.modelData
                        radius: height / 2
                        color: Theme.foreground
                    }
                    MouseArea {
                        id: widthHover
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            panel.newWidth = parent.modelData
                            panel.pushDesign()
                        }
                    }
                }
            }
        }

        GridLayout {
            columns: 2
            columnSpacing: Theme.spaceSm
            visible: !panel.nodesShown
            Repeater {
                model: panel.dirDefs
                delegate: Rectangle {
                    required property var modelData
                    width: Theme.directionTileWidth; height: Theme.optionTileSm
                    radius: Theme.radiusMd
                    color: panel.newDirected === modelData.key
                           ? Theme.accent
                           : dirHover.containsMouse ? Theme.hover
                                                    : Theme.control
                    border.width: panel.newDirected === modelData.key ? 0 : Theme.strokeHairline
                    border.color: Theme.border
                    Behavior on color { ColorAnimation { duration: Theme.hoverDuration } }

                    Text {
                        anchors.centerIn: parent
                        text: parent.modelData.glyph
                        color: Theme.foreground
                        font.pixelSize: 14
                    }
                    MouseArea {
                        id: dirHover
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            panel.newDirected = parent.modelData.key
                            panel.pushDesign()
                        }
                    }
                }
            }
        }

        GridLayout {
            columns: 4
            columnSpacing: Theme.spaceSm
            rowSpacing: Theme.spaceSm
            Repeater {
                model: Theme.nodePalette
                delegate: Rectangle {
                    required property string modelData
                    width: Theme.optionTileSm; height: Theme.optionTileSm
                    radius: Theme.optionTileSm / 2
                    color: modelData
                    scale: colorHover.containsMouse ? 1.15 : 1.0
                    Behavior on scale { NumberAnimation { duration: Theme.hoverDuration } }
                    border.width: panel.newColor === modelData ? Theme.strokeRing : 0
                    border.color: Theme.foreground

                    MouseArea {
                        id: colorHover
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            panel.newColor = parent.modelData
                            panel.pushDesign()
                        }
                    }
                }
            }
        }

        FlatButton {
            text: "Створити клас"
            visible: !panel.editing
            Layout.fillWidth: true
            enabled: nameField.text.trim() !== ""
            onClicked: panel.submitNew()
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.topMargin: Theme.spaceXs
            Layout.bottomMargin: Theme.spaceXs
            height: Theme.strokeHairline
            color: Theme.border
        }

        Label {
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            color: Theme.faintText
            font.pixelSize: 11
            text: panel.editing
                  ? (panel.nodesShown
                     ? "Нові вершини отримують цей клас; зміни стилю застосовуються до всіх його вершин. Повторний клік по класу — зняти вибір"
                     : "Нові ребра отримують цей клас; зміни стилю застосовуються до всіх його ребер. Повторний клік по класу — зняти вибір")
                    + ". Подвійний клік — перейменувати, ⋮⋮ чи Alt+↑/↓ — перемістити, Backspace — видалити"
                  : (panel.nodesShown
                     ? "Клас не обрано: нові вершини — «" + panel.defaultClass + "». Форма створює новий клас"
                     : "Клас не обрано: нові ребра — «" + panel.defaultClass + "». Форма створює новий клас")
        }

        RowLayout {
            Layout.maximumHeight: Theme.controlHeight
            spacing: Theme.spaceSm
            FlatButton {
                text: "💾"
                Layout.fillWidth: true
                Layout.fillHeight: true
                onClicked: saveDialog.open()
            }
            FlatButton {
                text: "📂"
                Layout.fillWidth: true
                Layout.fillHeight: true
                onClicked: openDialog.open()
            }
            FlatButton {
                text: "🗑"
                Layout.fillWidth: true
                Layout.fillHeight: true
                onClicked: backend.clear()
            }

        }
    }
}
