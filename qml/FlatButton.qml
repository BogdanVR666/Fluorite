import QtQuick
import QtQuick.Controls

Button {
    id: button

    property color textColor: Theme.foreground

    hoverEnabled: true
    leftPadding: 10
    rightPadding: 10
    topPadding: 6
    bottomPadding: 6
    opacity: enabled ? 1 : 0.4

    contentItem: Text {
        text: button.text
        font: button.font
        color: button.textColor
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }

    background: Rectangle {
        implicitHeight: 32
        radius: 8
        color: button.down ? Theme.accent
             : button.hovered ? Theme.hover
                              : Theme.control
        border.width: 1
        border.color: Theme.border
        Behavior on color { ColorAnimation { duration: 100 } }
    }
}
