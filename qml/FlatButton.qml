import QtQuick
import QtQuick.Controls

Button {
    id: button

    property color textColor: Theme.foreground

    hoverEnabled: true
    leftPadding: Theme.spaceMd
    rightPadding: Theme.spaceMd
    topPadding: Theme.spaceXs
    bottomPadding: Theme.spaceXs
    opacity: enabled ? 1 : Theme.disabledOpacity

    contentItem: Text {
        text: button.text
        font: button.font
        color: button.textColor
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }

    background: Rectangle {
        implicitHeight: Theme.controlHeight
        radius: Theme.radiusMd
        color: button.down ? Theme.accent
             : button.hovered ? Theme.hover
                              : Theme.control
        border.width: Theme.strokeHairline
        border.color: Theme.border
        Behavior on color { ColorAnimation { duration: Theme.hoverDuration } }
    }
}
