import QtCore
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Підтвердження дії: заголовок, текст, «Скасувати» / дія.
// Використання: задати тексти й onConfirmed, викликати ask().
// Якщо задано key, з'являється галочка «Більше не питати»; позначена,
// вона запам'ятовується між запусками, і далі ask() одразу підтверджує.
// Enter — підтвердити, Escape чи клік поза вікном — скасувати.
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
    width: 340
    padding: 18
    modal: true
    focus: true
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

    onOpened: {
        rememberBox.checked = false
        body.forceActiveFocus()
    }

    Overlay.modal: Rectangle { color: Qt.alpha("black", 0.35) }

    background: Rectangle {
        color: Theme.popup
        radius: 10
        border.width: 1
        border.color: Theme.popupBorder
    }

    contentItem: ColumnLayout {
        id: body
        spacing: 12
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
                width: 16; height: 16; radius: 4
                color: rememberBox.checked ? Theme.accent : Theme.control
                border.width: rememberBox.checked ? 0 : 1
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
                leftPadding: rememberBox.indicator.width + 8
                text: rememberBox.text
                font: rememberBox.font
                color: Theme.mutedText
                verticalAlignment: Text.AlignVCenter
            }
        }

        RowLayout {
            spacing: 8
            Layout.fillWidth: true
            Layout.topMargin: 4

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
