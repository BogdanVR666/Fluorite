import QtQuick
import QtQuick.Controls

ComboBox {
    id: box

    hoverEnabled: true
    opacity: enabled ? 1 : 0.4

    contentItem: Text {
        leftPadding: 10
        rightPadding: box.indicator.width + 14
        text: box.displayText
        font: box.font
        color: Theme.foreground
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }

    indicator: Text {
        x: box.width - width - 10
        y: (box.height - height) / 2
        text: "▾"
        color: Theme.mutedText
        font.pixelSize: 12
    }

    background: Rectangle {
        implicitWidth: 120
        implicitHeight: 32
        radius: 8
        color: box.hovered || box.popup.visible ? Theme.hover : Theme.control
        border.width: 1
        border.color: box.popup.visible ? Theme.marked : Theme.border
        Behavior on color { ColorAnimation { duration: 100 } }
    }

    delegate: ItemDelegate {
        required property int index

        width: box.popup.availableWidth
        highlighted: box.highlightedIndex === index
        leftPadding: 8
        rightPadding: 8

        contentItem: Text {
            text: box.textAt(parent.index)
            font: box.font
            color: Theme.foreground
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
        }
        background: Rectangle {
            implicitHeight: 30
            radius: 6
            color: box.currentIndex === parent.index ? Theme.accent
                 : parent.highlighted ? Theme.hover
                                      : "transparent"
        }
    }

    popup: Popup {
        y: box.height + 4
        width: box.width
        implicitHeight: Math.min(contentItem.implicitHeight + 8, 240)
        padding: 4

        contentItem: ListView {
            clip: true
            implicitHeight: contentHeight
            spacing: 2
            model: box.popup.visible ? box.delegateModel : null
            currentIndex: box.highlightedIndex
            ScrollIndicator.vertical: ScrollIndicator {}
        }

        background: Rectangle {
            color: Theme.popup
            radius: 8
            border.width: 1
            border.color: Theme.popupBorder
        }
    }
}
