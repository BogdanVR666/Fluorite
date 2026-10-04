import QtCore
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Popup {
    id: dialog

    property string title
    property string text
    property string confirmText: "Видалити"
    property string cancelText: "Скасувати"
    property string rememberText: "Більше не питати"
    property color confirmColor: Theme.error
    property string key: ""

    signal confirmed()

    function ask() {
        if (key !== "" && String(remembered.value(key, false)) === "true")
            confirmed()
        else
            open()
    }

    function accept() {
        if (key !== "" && rememberBox.checked)
            remembered.setValue(key, true)
        close()
        confirmed()
    }

    Settings {
        id: remembered
        category: "confirm"
    }

    parent: Overlay.overlay
    anchors.centerIn: parent
    width: Theme.dialogWidth
    padding: Theme.spaceLg
    modal: true
    focus: true
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

    onOpened: {
        rememberBox.checked = false
        body.forceActiveFocus()
    }

    Overlay.modal: Rectangle { color: Theme.modalScrim }

    background: Rectangle {
        color: Theme.popup
        radius: Theme.radiusLg
        border.width: Theme.strokeHairline
        border.color: Theme.popupBorder
    }

    contentItem: ColumnLayout {
        id: body
        spacing: Theme.spaceMd
        focus: true

        Keys.onReturnPressed: dialog.accept()
        Keys.onEnterPressed: dialog.accept()

        Label {
            text: dialog.title
            visible: text !== ""
            color: Theme.foreground
            font.bold: true
            font.pixelSize: 14
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
        }

        Label {
            text: dialog.text
            visible: text !== ""
            color: Theme.mutedText
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
        }

        CheckBox {
            id: rememberBox
            visible: dialog.key !== ""
            text: dialog.rememberText
            focusPolicy: Qt.NoFocus
            padding: 0

            indicator: Rectangle {
                x: rememberBox.leftPadding
                y: (rememberBox.height - height) / 2
                width: Theme.checkboxSize; height: Theme.checkboxSize
                radius: Theme.radiusSm
                color: rememberBox.checked ? Theme.accent : Theme.control
                border.width: rememberBox.checked ? 0 : Theme.strokeHairline
                border.color: Theme.border
                Text {
                    anchors.centerIn: parent
                    visible: rememberBox.checked
                    text: "✓"
                    color: Theme.foreground
                    font.pixelSize: 11
                }
            }
            contentItem: Text {
                leftPadding: rememberBox.indicator.width + Theme.spaceSm
                text: rememberBox.text
                font: rememberBox.font
                color: Theme.mutedText
                verticalAlignment: Text.AlignVCenter
            }
        }

        RowLayout {
            spacing: Theme.spaceSm
            Layout.fillWidth: true
            Layout.topMargin: Theme.spaceXs

            Item { Layout.fillWidth: true }
            FlatButton {
                text: dialog.cancelText
                focusPolicy: Qt.NoFocus
                onClicked: dialog.close()
            }
            FlatButton {
                text: dialog.confirmText
                textColor: dialog.confirmColor
                focusPolicy: Qt.NoFocus
                onClicked: dialog.accept()
            }
        }
    }
}
