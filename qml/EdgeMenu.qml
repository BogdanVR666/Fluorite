import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

/*
 * Контекстне меню ребра: спливає при ПКМ на ребрі, біля курсора.
 * Дозволяє змінити стиль лінії саме цього ребра, його клас,
 * або видалити ребро. Суто презентаційний компонент — яке саме ребро
 * редагувати і що робити з натисканнями, вирішує власник (main.qml).
 */
Popup {
    id: menu

    property int targetA: -1           // кінці ребра, яке редагуємо
    property int targetB: -1
    property string targetLabel: ""
    property string currentLine: "solid"
    property real currentWidth: 2.5
    property string currentColor: Theme.nodePalette[0]
    property string currentClass: ""   // клас цього ребра
    property bool currentDirected: false   // спрямоване (з дизайну класу)
    property var classes: []           // [{name, count, color, width, line,
                                       //   directed}]

    readonly property var classNames: classes.map(function (c) { return c.name })

    signal linePicked(string line)
    signal widthPicked(real width)
    signal colorPicked(string color)
    signal classPicked(string name)
    signal reverseRequested()
    signal removeRequested()

    // ComboBox рве прив'язку currentIndex після вибору користувача,
    // тож виставляємо індекс щоразу при відкритті
    onOpened: classCombo.currentIndex = classNames.indexOf(currentClass)

    padding: 0
    modal: false
    focus: true
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

    readonly property var lineDefs: [
        { key: "solid", glyph: "──" },
        { key: "dash",  glyph: "╌╌" },
        { key: "dot",   glyph: "┈┈" }
    ]
    readonly property var widthDefs: [2.5, 4, 6]

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
                text: "Ребро " + menu.targetLabel
                color: Theme.foreground
                font.bold: true
                font.pixelSize: 14
            }

            Label { text: "Лінія"; color: Theme.mutedText; font.pixelSize: 12 }

            GridLayout {
                columns: 3
                columnSpacing: 6
                Repeater {
                    model: menu.lineDefs
                    delegate: Rectangle {
                        required property var modelData
                        width: 38; height: 38; radius: 8
                        color: menu.currentLine === modelData.key
                               ? Theme.accent
                               : lineHover.containsMouse ? Theme.hover
                                                         : Theme.control
                        border.width: menu.currentLine === modelData.key ? 0 : 1
                        border.color: Theme.border
                        Behavior on color { ColorAnimation { duration: 100 } }

                        Text {
                            anchors.centerIn: parent
                            text: parent.modelData.glyph
                            color: Theme.foreground
                            font.pixelSize: 16
                        }
                        MouseArea {
                            id: lineHover
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: menu.linePicked(parent.modelData.key)
                        }
                    }
                }
            }

            Label { text: "Товщина"; color: Theme.mutedText; font.pixelSize: 12 }

            GridLayout {
                columns: 3
                columnSpacing: 6
                Repeater {
                    model: menu.widthDefs
                    delegate: Rectangle {
                        required property real modelData
                        width: 38; height: 38; radius: 8
                        color: menu.currentWidth === modelData
                               ? Theme.accent
                               : widthHover.containsMouse ? Theme.hover
                                                          : Theme.control
                        border.width: menu.currentWidth === modelData ? 0 : 1
                        border.color: Theme.border
                        Behavior on color { ColorAnimation { duration: 100 } }

                        Rectangle {   // зразок товщини лінії
                            anchors.centerIn: parent
                            width: 22
                            height: parent.modelData
                            radius: height / 2
                            color: Theme.foreground
                        }
                        MouseArea {
                            id: widthHover
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: menu.widthPicked(parent.modelData)
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
                    model: Theme.nodePalette
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

            // Напрям задає клас, а куди саме дивиться стрілка — це вже
            // дані ребра, тож перемикач живе тут, а не в панелі класів
            Button {
                visible: menu.currentDirected
                text: "⇄ Перевернути напрям"
                Layout.fillWidth: true
                onClicked: menu.reverseRequested()
            }

            Rectangle { Layout.fillWidth: true; height: 1; color: Theme.popupBorder }

            Button {
                text: "🗑 Видалити ребро"
                Layout.fillWidth: true
                palette.buttonText: Theme.error
                onClicked: menu.removeRequested()
            }
        }
    }
}
