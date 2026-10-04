import QtQuick
import QtQuick.Controls

TextField {
    id: field

    color: Theme.foreground
    placeholderTextColor: Theme.faintText
    selectByMouse: true
    selectionColor: Qt.alpha(Theme.marked, 0.45)
    selectedTextColor: Theme.foreground
    leftPadding: 2
    rightPadding: 2
    topPadding: 4
    bottomPadding: 6

    background: Item {
        Rectangle {
            anchors { left: parent.left; right: parent.right
                      bottom: parent.bottom }
            height: 2
            radius: 1
            color: field.activeFocus ? Theme.marked : Theme.border
        }
    }
}
