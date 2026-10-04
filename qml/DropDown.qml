import QtQuick
import QtQuick.Controls

ComboBox {
    id: box

    hoverEnabled: true
    opacity: enabled ? 1 : Theme.disabledOpacity

    contentItem: Text {
        leftPadding: Theme.spaceMd
        rightPadding: box.indicator.width + Theme.spaceMd + Theme.spaceXs
        text: box.displayText
        font: box.font
        color: Theme.foreground
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }

    indicator: Text {
        x: box.width - width - Theme.spaceMd
        y: (box.height - height) / 2
        text: "▾"
        color: Theme.mutedText
        font.pixelSize: 12
    }

    background: Rectangle {
        implicitWidth: Theme.dropdownMinWidth
        implicitHeight: Theme.controlHeight
        radius: Theme.radiusMd
        color: box.hovered || box.popup.visible ? Theme.hover : Theme.control
        border.width: Theme.strokeHairline
        border.color: box.popup.visible ? Theme.marked : Theme.border
        Behavior on color { ColorAnimation { duration: Theme.hoverDuration } }
    }

    delegate: ItemDelegate {
        required property int index

        width: box.popup.availableWidth
        highlighted: box.highlightedIndex === index
        leftPadding: Theme.spaceSm
        rightPadding: Theme.spaceSm

        contentItem: Text {
            text: box.textAt(parent.index)
            font: box.font
            color: Theme.foreground
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
        }
        background: Rectangle {
            implicitHeight: Theme.listItemHeight
            radius: Theme.radiusSm
            color: box.currentIndex === parent.index ? Theme.accent
                 : parent.highlighted ? Theme.hover
                                      : "transparent"
        }
    }

    popup: Popup {
        y: box.height + Theme.spaceXs
        width: box.width
        implicitHeight: Math.min(contentItem.implicitHeight + 2 * Theme.spaceXs,
                                 Theme.dropdownListMaxHeight)
        padding: Theme.spaceXs

        contentItem: ListView {
            clip: true
            implicitHeight: contentHeight
            spacing: Theme.spaceXs
            model: box.popup.visible ? box.delegateModel : null
            currentIndex: box.highlightedIndex
            ScrollIndicator.vertical: ScrollIndicator {}
        }

        background: Rectangle {
            color: Theme.popup
            radius: Theme.radiusMd
            border.width: Theme.strokeHairline
            border.color: Theme.popupBorder
        }
    }
}
