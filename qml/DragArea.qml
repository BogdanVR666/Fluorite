import QtQuick

MouseArea {
    id: area

    property Item space
    property point origin
    property Item grid

    property point pressPoint
    property point grabOffset
    property bool dragged: false
    property bool snapping: false

    signal moved(real x, real y, bool snap)

    hoverEnabled: true

    onPressed: function (mouse) {
        area.forceActiveFocus()
        pressPoint = mapToItem(space, mouse.x, mouse.y)
        grabOffset = Qt.point(pressPoint.x - origin.x, pressPoint.y - origin.y)
        dragged = false
        snapping = false
    }
    onPositionChanged: function (mouse) {
        if (!pressed)
            return
        var p = mapToItem(space, mouse.x, mouse.y)
        if (!dragged && Math.hypot(p.x - pressPoint.x, p.y - pressPoint.y)
                < Qt.styleHints.startDragDistance)
            return
        dragged = true
        snapping = (mouse.modifiers & Qt.ShiftModifier) !== 0
        area.moved(p.x - grabOffset.x, p.y - grabOffset.y, snapping)
    }

    Binding {
        target: area.grid
        property: "visible"
        value: true
        when: area.pressed && area.snapping
    }
}
