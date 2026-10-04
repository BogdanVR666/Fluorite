import QtQuick
import QtQuick.Controls

TextField {
    id: field

    color: Theme.foreground
    placeholderTextColor: Theme.faintText
    selectByMouse: true
    selectionColor: Theme.markedTextSelection
    selectedTextColor: Theme.foreground
    leftPadding: Theme.spaceXs
    rightPadding: Theme.spaceXs
    topPadding: Theme.spaceXs
    bottomPadding: Theme.spaceXs

    background: Item {
        Rectangle {
            anchors { left: parent.left; right: parent.right
                      bottom: parent.bottom }
            height: Theme.strokeNode
            radius: Theme.strokeNode / 2
            color: field.activeFocus ? Theme.marked : Theme.border
        }
    }
}
