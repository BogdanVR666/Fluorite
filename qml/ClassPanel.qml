import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

/*
 * Панель класів вершин. Суто презентаційний компонент:
 * показує зареєстровані класи (classes) і поточний клас для нових
 * вершин (currentClass), дає створити новий клас і повідомляє про
 * дії користувача сигналами. Що з ними робити — вирішує main.qml.
 */
Rectangle {
    id: panel

    // [{name, shape, color, count}] — з backend.classList()
    property var classes: []
    property string currentClass: ""   // клас для НОВИХ вершин

    signal classPicked(string name)
    signal connectClassRequested(string name)
    signal createRequested(string name, string shape, string color)
    signal saveRequested()
    signal openRequested()
    signal clearRequested()

    function resetForm() {
        nameField.text = ""
    }

    readonly property var shapeDefs: [
        { key: "circle",   glyph: "●" },  // ●
        { key: "square",   glyph: "■" },  // ■
        { key: "diamond",  glyph: "◆" },  // ◆
        { key: "triangle", glyph: "▲" }   // ▲
    ]
    function glyphFor(shape) {
        for (var i = 0; i < shapeDefs.length; i++)
            if (shapeDefs[i].key === shape)
                return shapeDefs[i].glyph
        return shapeDefs[0].glyph
    }

    // дизайн майбутнього класу
    property string newShape: "circle"
    property string newColor: Theme.nodePalette[0]

    width: 210
    color: Theme.panel

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 12
        spacing: 10

        Label {
            text: "Класи вершин"
            color: Theme.foreground
            font.bold: true
            font.pixelSize: 14
        }

        // ---- список класів; клік — клас для нових вершин ----
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
                        text: panel.glyphFor(modelData.shape)
                        color: modelData.color
                        font.pixelSize: 18
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
                    onClicked: panel.classPicked(parent.modelData.name)
                }
            }
        }

        Button {
            text: "🔗 З'єднати всі між собою"
            Layout.fillWidth: true
            onClicked: panel.connectClassRequested(panel.currentClass)
        }

        Rectangle { Layout.fillWidth: true; height: 1; color: Theme.border }

        // ---- створення нового класу ----
        Label { text: "Новий клас"; color: Theme.mutedText; font.pixelSize: 12 }

        TextField {
            id: nameField
            Layout.fillWidth: true
            placeholderText: "Назва класу"
        }

        GridLayout {
            columns: 4
            columnSpacing: 6
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
                        onClicked: panel.newShape = parent.modelData.key
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
                        onClicked: panel.newColor = parent.modelData
                    }
                }
            }
        }

        Button {
            text: "➕ Створити клас"
            Layout.fillWidth: true
            enabled: nameField.text.trim() !== ""
            onClicked: panel.createRequested(nameField.text.trim(),
                                             panel.newShape, panel.newColor)
        }

        Rectangle { Layout.fillWidth: true; height: 1; color: Theme.border }

        Label {
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            color: Theme.faintText
            font.pixelSize: 11
            text: "Нові вершини отримують обраний клас"
        }

        Button {
            text: "💾 Зберегти граф"
            Layout.fillWidth: true
            onClicked: panel.saveRequested()
        }
        Button {
            text: "📂 Відкрити граф"
            Layout.fillWidth: true
            onClicked: panel.openRequested()
        }
        Button {
            text: "🗑 Очистити"
            Layout.fillWidth: true
            onClicked: panel.clearRequested()
        }
    }
}
