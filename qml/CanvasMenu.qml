import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Popup {
    id: menu

    property point spot

    padding: 0
    modal: true
    dim: false
    focus: true
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

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

            FlatButton {
                text: "Нова група"
                Layout.fillWidth: true
                onClicked: {
                    backend.addGroup(menu.spot.x, menu.spot.y)
                    menu.close()
                }
            }

            FlatButton {
                visible: backend.selectionCount + backend.groupSelectionCount > 0
                text: "Обвести виділене групою"
                Layout.fillWidth: true
                onClicked: {
                    backend.groupSelection()
                    menu.close()
                }
            }
        }
    }
}
