import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

/*
 * Панель класів елементів графа. Суто презентаційний компонент:
 * перемикач родини (вершини/ребра), список зареєстрованих класів
 * обраної родини та форма стилю. Форма дворежимна: коли клас обрано —
 * редагує його дизайн (зміни застосовуються одразу), коли вибір знято
 * (повторний клік по класу) — створює новий клас. Про дії користувача
 * повідомляє сигналами — що з ними робити, вирішує main.qml.
 */
Rectangle {
    id: panel

    // з backend.classList("node") / classList("edge")
    property var nodeClasses: []       // [{name, count, shape, color, opacity}]
    property var edgeClasses: []       // [{name, count, color, width, line}]
    property string currentNodeClass: ""   // клас для НОВИХ вершин
    property string currentEdgeClass: ""   // клас для НОВИХ ребер

    // родина, показана зараз; від неї залежить список і форма створення
    property string family: "node"
    readonly property bool nodesShown: family === "node"
    readonly property var classes: nodesShown ? nodeClasses : edgeClasses
    readonly property string currentClass: nodesShown ? currentNodeClass
                                                      : currentEdgeClass

    // клас обрано — форма редагує його; інакше — створює новий
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

    // заповнює форму дизайном обраного класу
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
            }
            return
        }
    }

    // шле поточний дизайн форми як новий дизайн обраного класу
    function pushDesign() {
        if (!editing)
            return
        updateRequested(family, currentClass, nodesShown
            ? { shape: newShape, color: newColor, opacity: newOpacity }
            : { color: newColor, width: newWidth, line: newLine })
    }

    onCurrentClassChanged: loadDesign()
    // список приходить пізніше за вибір (та оновлюється після pushDesign
    // тими самими значеннями) — перечитуємо без побічних ефектів
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

    function glyphIn(defs, key) {
        for (var i = 0; i < defs.length; i++)
            if (defs[i].key === key)
                return defs[i].glyph
        return defs[0].glyph
    }
    // значок класу в списку: форма вершини або лінія ребра
    function classGlyph(cls) {
        return nodesShown ? glyphIn(shapeDefs, cls.shape)
                          : glyphIn(lineDefs, cls.line)
    }

    // дизайн майбутнього класу
    property string newShape: "circle"
    property string newLine: "solid"
    property real newWidth: 2.5
    property string newColor: Theme.nodePalette[0]
    property real newOpacity: 1.0

    width: 210
    color: Theme.panel

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

        // ---- перемикач родини ----
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

        // ---- список класів; клік — клас для нових елементів ----
        ListView {
            id: classList
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            spacing: 4
            model: panel.classes

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
                    // повторний клік по обраному класу знімає вибір —
                    // форма перемикається у режим створення нового
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

        // ---- форма стилю: редагування обраного класу або створення ----
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

        // форма вершини (лише родина "node")
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

        // прозорість вершини (лише родина "node")
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
            // взаємодія рве прив'язку value — відновлюємо її вручну,
            // коли дизайн завантажується з обраного класу
            Connections {
                target: panel
                function onNewOpacityChanged() {
                    opacitySlider.value = panel.newOpacity
                }
            }
        }

        // стиль лінії (лише родина "edge")
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

        // товщина лінії (лише родина "edge")
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
                        line: panel.newLine }
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
