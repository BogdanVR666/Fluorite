import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: panel

    property var nodeClasses: []       // [{name, count, shape, color, opacity}]
    property var edgeClasses: []       // [{name, count, color, width, line, directed}]
    property string currentNodeClass: ""   // клас для НОВИХ вершин
    property string currentEdgeClass: ""   // клас для НОВИХ ребер

    property string family: "node"
    readonly property bool nodesShown: family === "node"
    readonly property var classes: nodesShown ? nodeClasses : edgeClasses
    readonly property string currentClass: nodesShown ? currentNodeClass
                                                      : currentEdgeClass

    readonly property bool editing: currentClass !== ""

    signal classPicked(string family, string name)
    signal connectClassRequested(string name)
    signal createRequested(string family, string name, var design)
    signal updateRequested(string family, string name, var design)
    signal saveRequested()
    signal openRequested()
    signal clearRequested()

    function resetForm() {
        nameField.text = ""
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
        updateRequested(family, currentClass, nodesShown
            ? { shape: newShape, color: newColor, opacity: newOpacity }
            : { color: newColor, width: newWidth, line: newLine,
                directed: newDirected })
    }

    onCurrentClassChanged: loadDesign()
    onClassesChanged: loadDesign()

    readonly property var familyDefs: [
        { key: "node", label: "Вершини" },
        { key: "edge", label: "Ребра" }
    ]
    readonly property var shapeDefs: [
        { key: "circle",   glyph: "●" },
        { key: "square",   glyph: "■" },
        { key: "diamond",  glyph: "◆" },
        { key: "triangle", glyph: "▲" }
    ]
    readonly property var lineDefs: [
        { key: "solid", glyph: "──" },
        { key: "dash",  glyph: "╌╌" },
        { key: "dot",   glyph: "┈┈" }
    ]
    readonly property var widthDefs: [2.5, 4, 6]
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
        return nodesShown ? glyphIn(shapeDefs, cls.shape)
                          : glyphIn(lineDefs, cls.line)
                            + (cls.directed === true ? "▶" : "")
    }

    property string newShape: "circle"
    property string newLine: "solid"
    property real newWidth: 2.5
    property string newColor: Theme.nodePalette[0]
    property real newOpacity: 1.0
    property bool newDirected: false

    width: 210
    color: Theme.panel

    MouseArea {
        anchors.fill: parent
        onClicked: panel.classPicked(panel.family, "")
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 12
        spacing: 10

        Label {
            text: "Класи"
            color: Theme.foreground
            font.bold: true
            font.pixelSize: 14
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 6
            Repeater {
                model: panel.familyDefs
                delegate: Rectangle {
                    required property var modelData
                    Layout.fillWidth: true
                    height: 30
                    radius: 8
                    color: panel.family === modelData.key
                           ? Theme.accent
                           : famHover.containsMouse ? Theme.hover
                                                    : Theme.control
                    border.width: panel.family === modelData.key ? 0 : 1
                    border.color: Theme.border
                    Behavior on color { ColorAnimation { duration: 100 } }

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
            spacing: 4
            model: panel.classes

            TapHandler {
                onTapped: panel.classPicked(panel.family, "")
            }

            delegate: Rectangle {
                required property var modelData
                width: classList.width
                height: 36
                radius: 8
                color: panel.currentClass === modelData.name
                       ? Theme.accent
                       : rowHover.containsMouse ? Theme.hover : "transparent"
                Behavior on color { ColorAnimation { duration: 100 } }

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 10
                    anchors.rightMargin: 10
                    spacing: 8

                    Text {
                        text: panel.classGlyph(modelData)
                        color: modelData.color
                        opacity: panel.nodesShown ? modelData.opacity : 1
                        font.pixelSize: panel.nodesShown ? 18 : 14
                        font.bold: !panel.nodesShown && modelData.width >= 4
                    }
                    Label {
                        text: modelData.name
                        color: Theme.foreground
                        elide: Text.ElideRight
                        Layout.fillWidth: true
                    }
                    Label {
                        text: modelData.count
                        color: Theme.mutedText
                        font.pixelSize: 11
                    }
                }

                MouseArea {
                    id: rowHover
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: panel.classPicked(
                        panel.family,
                        panel.currentClass === parent.modelData.name
                            ? "" : parent.modelData.name)
                }
            }
        }

        Button {
            text: "З'єднати всі"
            visible: panel.nodesShown
            enabled: panel.currentNodeClass !== ""
            Layout.fillWidth: true
            onClicked: panel.connectClassRequested(panel.currentNodeClass)
        }

        Rectangle { Layout.fillWidth: true; height: 1; color: Theme.border }

        Label {
            text: panel.editing ? "Клас «" + panel.currentClass + "»"
                                : "Новий клас"
            color: Theme.mutedText
            font.pixelSize: 12
            elide: Text.ElideRight
            Layout.fillWidth: true
        }

        TextField {
            id: nameField
            visible: !panel.editing
            Layout.fillWidth: true
            placeholderText: "Назва класу"
        }

        GridLayout {
            columns: 4
            columnSpacing: 6
            visible: panel.nodesShown
            Repeater {
                model: panel.shapeDefs
                delegate: Rectangle {
                    required property var modelData
                    width: 34; height: 34; radius: 8
                    color: panel.newShape === modelData.key
                           ? Theme.accent
                           : shapeHover.containsMouse ? Theme.hover
                                                      : Theme.control
                    border.width: panel.newShape === modelData.key ? 0 : 1
                    border.color: Theme.border
                    Behavior on color { ColorAnimation { duration: 100 } }

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
            columnSpacing: 6
            visible: !panel.nodesShown
            Repeater {
                model: panel.lineDefs
                delegate: Rectangle {
                    required property var modelData
                    width: 34; height: 34; radius: 8
                    color: panel.newLine === modelData.key
                           ? Theme.accent
                           : lineHover.containsMouse ? Theme.hover
                                                     : Theme.control
                    border.width: panel.newLine === modelData.key ? 0 : 1
                    border.color: Theme.border
                    Behavior on color { ColorAnimation { duration: 100 } }

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
            columnSpacing: 6
            visible: !panel.nodesShown
            Repeater {
                model: panel.widthDefs
                delegate: Rectangle {
                    required property real modelData
                    width: 34; height: 34; radius: 8
                    color: panel.newWidth === modelData
                           ? Theme.accent
                           : widthHover.containsMouse ? Theme.hover
                                                      : Theme.control
                    border.width: panel.newWidth === modelData ? 0 : 1
                    border.color: Theme.border
                    Behavior on color { ColorAnimation { duration: 100 } }

                    Rectangle {   // зразок товщини лінії
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
            columnSpacing: 6
            visible: !panel.nodesShown
            Repeater {
                model: panel.dirDefs
                delegate: Rectangle {
                    required property var modelData
                    width: 52; height: 34; radius: 8
                    color: panel.newDirected === modelData.key
                           ? Theme.accent
                           : dirHover.containsMouse ? Theme.hover
                                                    : Theme.control
                    border.width: panel.newDirected === modelData.key ? 0 : 1
                    border.color: Theme.border
                    Behavior on color { ColorAnimation { duration: 100 } }

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
            columnSpacing: 6
            rowSpacing: 6
            Repeater {
                model: Theme.nodePalette
                delegate: Rectangle {
                    required property string modelData
                    width: 34; height: 34; radius: 17
                    color: modelData
                    scale: colorHover.containsMouse ? 1.15 : 1.0
                    Behavior on scale { NumberAnimation { duration: 100 } }
                    border.width: panel.newColor === modelData ? 3 : 0
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

        Button {
            text: "Створити клас"
            visible: !panel.editing
            Layout.fillWidth: true
            enabled: nameField.text.trim() !== ""
            onClicked: {
                var design = panel.nodesShown
                    ? { shape: panel.newShape, color: panel.newColor,
                        opacity: panel.newOpacity }
                    : { color: panel.newColor, width: panel.newWidth,
                        line: panel.newLine, directed: panel.newDirected }
                panel.createRequested(panel.family, nameField.text.trim(),
                                      design)
            }
        }

        Rectangle { Layout.fillWidth: true; height: 1; color: Theme.border }

        Label {
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            color: Theme.faintText
            font.pixelSize: 11
            text: panel.editing
                  ? (panel.nodesShown
                     ? "Нові вершини отримують цей клас; зміни стилю застосовуються до всіх його вершин. Повторний клік по класу — зняти вибір"
                     : "Нові ребра отримують цей клас; зміни стилю застосовуються до всіх його ребер. Повторний клік по класу — зняти вибір")
                  : (panel.nodesShown
                     ? "Клас не обрано: нові вершини — «Звичайна». Форма створює новий клас"
                     : "Клас не обрано: нові ребра — «Звичайне». Форма створює новий клас")
        }

        RowLayout {
            Layout.maximumHeight: 36
            Button {
                text: "💾"
                Layout.fillWidth: true
                Layout.fillHeight: true
                onClicked: panel.saveRequested()
            }
            Button {
                text: "📂"
                Layout.fillWidth: true
                Layout.fillHeight: true
                onClicked: panel.openRequested()
            }
            Button {
                text: "🗑"
                Layout.fillWidth: true
                Layout.fillHeight: true
                onClicked: panel.clearRequested()
            }

        }
    }
}
