import QtQuick
import QtQuick.Controls
import QtQuick.Layouts


Popup {
    id: menu

    property int edgeId: -1
    property string targetLabel: ""
    property string currentLine: "solid"
    property real currentWidth: Theme.edgeWidths[0]
    property string currentColor: Theme.nodePalette[0]
    property string currentClass: ""
    property bool currentDirected: false
    property var classes: []

    readonly property var classNames: classes.map(function (c) { return c.name })

    function refresh() {
        var info = backend.edgeInfo(edgeId)
        if (!info.klass) {
            close()
            return false
        }
        targetLabel = info.label
        currentLine = info.line
        currentWidth = info.width
        currentColor = String(info.color)
        currentClass = info.klass
        currentDirected = info.directed === true
        classCombo.currentIndex = classNames.indexOf(currentClass)
        return true
    }

    onClosed: edgeId = -1

    padding: 0
    modal: true
    dim: false
    focus: true
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

    readonly property var lineDefs: [
        { key: "solid", glyph: "──" },
        { key: "dash",  glyph: "╌╌" },
        { key: "dot",   glyph: "┈┈" }
    ]
    readonly property var widthDefs: Theme.edgeWidths

    background: Rectangle {
        color: Theme.popup
        radius: Theme.radiusLg
        border.color: Theme.popupBorder
        border.width: Theme.strokeHairline
    }

    contentItem: Item {
        implicitWidth: Math.max(Theme.menuMinWidth, col.implicitWidth + 2 * Theme.spaceMd)
        implicitHeight: col.implicitHeight + 2 * Theme.spaceMd

        ColumnLayout {
            id: col
            anchors.fill: parent
            anchors.margins: Theme.spaceMd
            spacing: Theme.spaceSm

            Label {
                text: "Ребро " + menu.targetLabel
                color: Theme.foreground
                font.bold: true
                font.pixelSize: 14
            }

            Label {
                text: "Лінія"; color: Theme.mutedText; font.pixelSize: 12
                Layout.topMargin: Theme.spaceXs
            }

            GridLayout {
                columns: 3
                columnSpacing: Theme.spaceSm
                Repeater {
                    model: menu.lineDefs
                    delegate: Rectangle {
                        required property var modelData
                        width: Theme.optionTile; height: Theme.optionTile
                        radius: Theme.radiusMd
                        color: menu.currentLine === modelData.key
                               ? Theme.accent
                               : lineHover.containsMouse ? Theme.hover
                                                         : Theme.control
                        border.width: menu.currentLine === modelData.key ? 0 : Theme.strokeHairline
                        border.color: Theme.border
                        Behavior on color { ColorAnimation { duration: Theme.hoverDuration } }

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
                            onClicked: {
                                backend.setEdgeLine(menu.edgeId, parent.modelData.key)
                                menu.refresh()
                            }
                        }
                    }
                }
            }

            Label {
                text: "Товщина"; color: Theme.mutedText; font.pixelSize: 12
                Layout.topMargin: Theme.spaceXs
            }

            GridLayout {
                columns: 3
                columnSpacing: Theme.spaceSm
                Repeater {
                    model: menu.widthDefs
                    delegate: Rectangle {
                        required property real modelData
                        width: Theme.optionTile; height: Theme.optionTile
                        radius: Theme.radiusMd
                        color: menu.currentWidth === modelData
                               ? Theme.accent
                               : widthHover.containsMouse ? Theme.hover
                                                          : Theme.control
                        border.width: menu.currentWidth === modelData ? 0 : Theme.strokeHairline
                        border.color: Theme.border
                        Behavior on color { ColorAnimation { duration: Theme.hoverDuration } }

                        Rectangle {
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
                            onClicked: {
                                backend.setEdgeWidth(menu.edgeId, parent.modelData)
                                menu.refresh()
                            }
                        }
                    }
                }
            }

            Label {
                text: "Колір"; color: Theme.mutedText; font.pixelSize: 12
                Layout.topMargin: Theme.spaceXs
            }

            GridLayout {
                columns: 4
                columnSpacing: Theme.spaceSm
                rowSpacing: Theme.spaceSm
                Repeater {
                    model: Theme.nodePalette
                    delegate: Rectangle {
                        required property string modelData
                        width: Theme.optionTile; height: Theme.optionTile
                        radius: Theme.optionTile / 2
                        color: modelData
                        scale: colorHover.containsMouse ? 1.15 : 1.0
                        Behavior on scale { NumberAnimation { duration: Theme.hoverDuration } }
                        border.width: menu.currentColor === modelData ? Theme.strokeRing : 0
                        border.color: Theme.foreground

                        MouseArea {
                            id: colorHover
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                backend.setEdgeColor(menu.edgeId, parent.modelData)
                                menu.refresh()
                            }
                        }
                    }
                }
            }

            Label {
                text: "Клас"; color: Theme.mutedText; font.pixelSize: 12
                Layout.topMargin: Theme.spaceXs
            }

            DropDown {
                id: classCombo
                Layout.fillWidth: true
                model: menu.classNames
                onActivated: function (index) {
                    backend.setEdgeClass(menu.edgeId, textAt(index))
                    menu.refresh()
                }
            }

            FlatButton {
                visible: menu.currentDirected
                text: "⇄ Перевернути напрям"
                Layout.fillWidth: true
                onClicked: {
                    backend.reverseEdge(menu.edgeId)
                    menu.refresh()
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.topMargin: Theme.spaceXs
                Layout.bottomMargin: Theme.spaceXs
                height: Theme.strokeHairline
                color: Theme.popupBorder
            }

            FlatButton {
                text: "🗑 Видалити ребро"
                Layout.fillWidth: true
                textColor: Theme.error
                onClicked: {
                    backend.removeEdge(menu.edgeId)
                    menu.close()
                }
            }
        }
    }
}
