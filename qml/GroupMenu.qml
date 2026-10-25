import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Popup {
    id: menu

    property int groupId: -1
    property string targetLabel: ""
    property bool collapsed: false
    property string mode: "frame"
    property int memberCount: 0

    function refresh() {
        var info = backend.groupInfo(groupId)
        if (info.label === undefined) {
            close()
            return false
        }
        targetLabel = info.label
        collapsed = info.collapsed
        mode = info.mode
        memberCount = info.memberCount
        return true
    }

    onOpened: nameField.text = targetLabel
    onClosed: groupId = -1

    padding: 0
    modal: true
    dim: false
    focus: true
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

    readonly property var modeDefs: [
        { key: "frame", label: "Рамка" },
        { key: "tree",  label: "Дерево" }
    ]

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
                text: "Група " + menu.targetLabel + " (" + menu.memberCount + ")"
                color: Theme.foreground
                font.bold: true
                font.pixelSize: 14
            }

            Label {
                text: "Назва"; color: Theme.mutedText; font.pixelSize: 12
                Layout.topMargin: Theme.spaceXs
            }

            LineField {
                id: nameField
                Layout.fillWidth: true
                placeholderText: "Назва групи"
                onTextEdited: {
                    backend.renameGroup(menu.groupId, text)
                    menu.refresh()
                }
            }

            Label {
                text: "Вигляд"; color: Theme.mutedText; font.pixelSize: 12
                Layout.topMargin: Theme.spaceXs
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: Theme.spaceSm
                Repeater {
                    model: menu.modeDefs
                    delegate: Rectangle {
                        required property var modelData
                        Layout.fillWidth: true
                        height: Theme.optionTileSm
                        radius: Theme.radiusMd
                        color: menu.mode === modelData.key
                               ? Theme.accent
                               : modeHover.containsMouse ? Theme.hover
                                                         : Theme.control
                        border.width: menu.mode === modelData.key ? 0 : Theme.strokeHairline
                        border.color: Theme.border
                        Behavior on color { ColorAnimation { duration: Theme.hoverDuration } }

                        Text {
                            anchors.centerIn: parent
                            text: parent.modelData.label
                            color: Theme.foreground
                            font.pixelSize: 12
                        }
                        MouseArea {
                            id: modeHover
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                backend.setGroupMode(menu.groupId, parent.modelData.key)
                                menu.refresh()
                            }
                        }
                    }
                }
            }

            FlatButton {
                text: menu.collapsed ? "Розгорнути" : "Згорнути"
                Layout.fillWidth: true
                Layout.topMargin: Theme.spaceXs
                onClicked: {
                    backend.setGroupCollapsed(menu.groupId, !menu.collapsed)
                    menu.close()
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
                text: "Видалити рамку"
                Layout.fillWidth: true
                textColor: Theme.error
                onClicked: {
                    backend.removeGroup(menu.groupId)
                    menu.close()
                }
            }
        }
    }
}
