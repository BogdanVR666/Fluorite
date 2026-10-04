import QtQuick
import QtQuick.Controls

TextArea {
    id: area

    color: Theme.foreground
    placeholderTextColor: Theme.faintText
    selectByMouse: true
    selectionColor: Theme.markedTextSelection
    selectedTextColor: Theme.foreground
    wrapMode: TextArea.Wrap
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
            color: area.activeFocus ? Theme.marked : Theme.border
        }
    }
}
