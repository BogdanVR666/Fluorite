import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

/*
 * Контекстне меню вершини: спливає при ПКМ на вершині, біля курсора.
 * Дозволяє змінити форму/колір саме цієї вершини або видалити її.
 * Суто презентаційний компонент — яку саме вершину редагувати
 * і що робити з натисканнями, вирішує власник (main.qml).
 */
Popup {
    id: menu

    property int targetId: -1          // яку вершину редагуємо/видаляємо
    property string targetLabel: ""
    property string currentShape: "circle"
    property string currentColor: Theme.nodePalette[0]
    property string currentClass: ""   // клас цієї вершини
    property var classes: []           // [{name, shape, color, count}]

    readonly property var classNames: classes.map(function (c) { return c.name })

    signal shapePicked(string shape)
    signal colorPicked(string color)
    signal classPicked(string name)
    signal connectToClassRequested(string name)
    signal removeRequested()

    // ComboBox рве прив'язку currentIndex після вибору користувача,
    // тож виставляємо індекс щоразу при відкритті
    onOpened: {
        classCombo.currentIndex = classNames.indexOf(currentClass)
        connectCombo.currentIndex = -1
    }

    padding: 0
    modal: false
    focus: true
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

    readonly property var shapeDefs: [
        { key: "circle",   glyph: "\u25CF" },  // ●
        { key: "square",   glyph: "\u25A0" },  // ■
        { key: "diamond",  glyph: "\u25C6" },  // ◆
        { key: "triangle", glyph: "\u25B2" }   // ▲
    ]
    readonly property var colorPalette: Theme.nodePalette

    background: Rectangle {
        color: Theme.popup
        radius: 10
        border.color: Theme.popupBorder
        border.width: 1
    }

    contentItem: Item {
        implicitWidth: 190
        implicitHeight: col.implicitHeight + 24

        ColumnLayout {
            id: col
            anchors.fill: parent
            anchors.margins: 12
            spacing: 10

            Label {
                text: "Вершина " + menu.targetLabel
                color: Theme.foreground
                font.bold: true
                font.pixelSize: 14
            }

            Label { text: "Форма"; color: Theme.mutedText; font.pixelSize: 12 }

            GridLayout {
                columns: 4
                columnSpacing: 6
                Repeater {
                    model: menu.shapeDefs
                    delegate: Rectangle {
                        required property var modelData
                        width: 38; height: 38; radius: 8
                        color: menu.currentShape === modelData.key
                               ? Theme.accent
                               : shapeHover.containsMouse ? Theme.hover
                                                          : Theme.control
                        border.width: menu.currentShape === modelData.key ? 0 : 1
                        border.color: Theme.border
                        Behavior on color { ColorAnimation { duration: 100 } }

                        Text {
                            anchors.centerIn: parent
                            text: parent.modelData.glyph
                            color: Theme.foreground
                            font.pixelSize: 18
                        }
                        MouseArea {
                            id: shapeHover
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: menu.shapePicked(parent.modelData.key)
                        }
                    }
                }
            }

            Label { text: "Колір"; color: Theme.mutedText; font.pixelSize: 12 }

            GridLayout {
                columns: 4
                columnSpacing: 6
                rowSpacing: 6
                Repeater {
                    model: menu.colorPalette
                    delegate: Rectangle {
                        required property string modelData
                        width: 38; height: 38; radius: 19
                        color: modelData
                        scale: colorHover.containsMouse ? 1.15 : 1.0
                        Behavior on scale { NumberAnimation { duration: 100 } }
                        border.width: menu.currentColor === modelData ? 3 : 0
                        border.color: Theme.foreground

                        MouseArea {
                            id: colorHover
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: menu.colorPicked(parent.modelData)
                        }
                    }
                }
            }

            Label { text: "Клас"; color: Theme.mutedText; font.pixelSize: 12 }

            ComboBox {
                id: classCombo
                Layout.fillWidth: true
                model: menu.classNames
                onActivated: function (index) {
                    menu.classPicked(textAt(index))
                }
            }

            // Діє як кнопка-меню: вибір пункту одразу з'єднує вершину
            // з усіма вершинами обраного класу
            ComboBox {
                id: connectCombo
                Layout.fillWidth: true
                displayText: "🔗 З'єднати з класом…"
                model: menu.classNames
                onActivated: function (index) {
                    menu.connectToClassRequested(textAt(index))
                    menu.close()
                }
            }

            Rectangle { Layout.fillWidth: true; height: 1; color: Theme.popupBorder }

            Button {
                text: "🗑 Видалити вершину"
                Layout.fillWidth: true
                palette.buttonText: Theme.error
                onClicked: menu.removeRequested()
            }
        }
    }
}
