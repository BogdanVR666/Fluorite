import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Popup {
    id: menu

    property int targetId: -1
    property string targetLabel: ""
    property string currentDescription: ""
    property string currentShape: "circle"
    property string currentColor: Theme.nodePalette[0]
    property real currentOpacity: 1.0
    property string currentClass: ""
    property var classes: []

    property int selectionCount: 1
    readonly property bool group: selectionCount > 1

    property int groupId: -1
    property string groupLabel: ""

    property bool isGroup: false
    property int ownGroupId: -1
    property int memberCount: 0

    readonly property var classNames: classes.map(function (c) { return c.name })

    property string edgeClass: ""

    function refresh() {
        var info = backend.nodeInfo(targetId)
        if (!info.klass) {
            close()
            return false
        }
        targetLabel = info.label
        currentDescription = info.description
        currentShape = info.shape
        currentColor = String(info.color)
        currentOpacity = info.opacity
        currentClass = info.klass
        groupId = info.groupId
        groupLabel = info.groupLabel
        isGroup = info.isGroup === true
        ownGroupId = info.ownGroupId
        memberCount = info.memberCount
        classCombo.currentIndex = classNames.indexOf(currentClass)
        return true
    }

    property bool syncing: false

    onOpened: {
        syncing = true
        labelField.text = targetLabel
        descArea.text = currentDescription
        opacitySlider.value = currentOpacity
        connectCombo.currentIndex = -1
        syncing = false
    }

    onClosed: targetId = -1

    onCurrentOpacityChanged: opacitySlider.value = currentOpacity

    padding: 0
    modal: true
    dim: false
    focus: true
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

    readonly property var shapeDefs: [
        { key: "circle",   glyph: "\u25CF" },
        { key: "square",   glyph: "\u25A0" }
    ]
    readonly property var colorPalette: Theme.nodePalette

    background: Rectangle {
        color: Theme.popup
        radius: 10
        border.color: Theme.popupBorder
        border.width: 1
    }

    contentItem: Item {
        implicitWidth: Math.max(150, col.implicitWidth + 24)
        implicitHeight: col.implicitHeight + 24

        ColumnLayout {
            id: col
            anchors.fill: parent
            anchors.margins: 12
            spacing: 10

            Label {
                text: menu.group ? "Виділено вершин: " + menu.selectionCount
                    : menu.isGroup ? "Група " + menu.targetLabel
                                     + " (" + menu.memberCount + ")"
                                   : "Вершина " + menu.targetLabel
                color: Theme.foreground
                font.bold: true
                font.pixelSize: 14
            }

            FlatButton {
                visible: menu.isGroup && !menu.group
                text: "Розгорнути групу"
                Layout.fillWidth: true
                onClicked: {
                    backend.setGroupCollapsed(menu.ownGroupId, false)
                    menu.close()
                }
            }

            FlatButton {
                visible: menu.isGroup && !menu.group
                text: "Розгрупувати"
                Layout.fillWidth: true
                onClicked: {
                    backend.ungroup(menu.ownGroupId)
                    menu.close()
                }
            }

            Label {
                visible: !menu.group
                text: "Текст"; color: Theme.mutedText; font.pixelSize: 12
            }

            LineField {
                id: labelField
                visible: !menu.group
                Layout.fillWidth: true
                placeholderText: "Підпис вершини"
                onTextEdited: {
                    backend.setNodeLabel(menu.targetId, text)
                    menu.refresh()
                }
            }

            Label {
                visible: !menu.group
                text: "Опис"; color: Theme.mutedText; font.pixelSize: 12
            }

            ScrollView {
                visible: !menu.group
                Layout.fillWidth: true
                Layout.preferredHeight: 56
                clip: true

                TextBox {
                    id: descArea
                    placeholderText: "Опис вершини…"
                    font.pixelSize: 12
                    onTextChanged: {
                        if (menu.syncing)
                            return
                        backend.setNodeDescription(menu.targetId, text)
                        menu.refresh()
                    }
                }
            }

            Label {
                visible: !menu.isGroup
                text: "Форма"; color: Theme.mutedText; font.pixelSize: 12
            }

            GridLayout {
                visible: !menu.isGroup
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
                            onClicked: {
                                backend.setSelectionShape(parent.modelData.key)
                                menu.refresh()
                            }
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
                            onClicked: {
                                backend.setSelectionColor(parent.modelData)
                                menu.refresh()
                            }
                        }
                    }
                }
            }

            RowLayout {
                Layout.fillWidth: true
                Label {
                    text: "Прозорість"
                    color: Theme.mutedText
                    font.pixelSize: 12
                    Layout.fillWidth: true
                }
                Label {
                    text: Math.round(opacitySlider.value * 100) + "%"
                    color: Theme.mutedText
                    font.pixelSize: 12
                }
            }

            Slider {
                id: opacitySlider
                Layout.fillWidth: true
                from: 0.1
                to: 1.0
                onMoved: {
                    backend.setSelectionOpacity(value)
                    menu.refresh()
                }
            }

            Label { text: "Клас"; color: Theme.mutedText; font.pixelSize: 12 }

            DropDown {
                id: classCombo
                Layout.fillWidth: true
                model: menu.classNames
                onActivated: function (index) {
                    backend.setSelectionClass(textAt(index))
                    menu.refresh()
                }
            }

            DropDown {
                id: connectCombo
                Layout.fillWidth: true
                displayText: "З'єднати з класом…"
                model: menu.classNames
                onActivated: function (index) {
                    backend.connectSelectionToClass(textAt(index),
                                                    menu.edgeClass)
                    menu.close()
                }
            }

            FlatButton {
                visible: menu.group
                text: "З'єднати виділені між собою"
                Layout.fillWidth: true
                onClicked: {
                    backend.connectSelection(menu.edgeClass)
                    menu.close()
                }
            }

            FlatButton {
                visible: menu.group
                text: "Згорнути виділені у групу"
                Layout.fillWidth: true
                onClicked: {
                    backend.groupSelection()
                    menu.close()
                }
            }

            FlatButton {
                visible: menu.groupId !== -1
                text: "Згорнути групу «" + menu.groupLabel + "»"
                Layout.fillWidth: true
                onClicked: {
                    backend.setGroupCollapsed(menu.groupId, true)
                    menu.close()
                }
            }

            Rectangle { 
                Layout.fillWidth: true
                height: 1
                color: Theme.popupBorder 
            }

            FlatButton {
                text: menu.group ? "Видалити виділені (" + menu.selectionCount + ")"
                                 : "Видалити вершину"
                Layout.fillWidth: true
                textColor: Theme.error
                onClicked: {
                    backend.removeSelection()
                    menu.close()
                }
            }
        }
    }
}
