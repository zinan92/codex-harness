import CoreGraphics
import Foundation

struct JinglePanelLayout {
    static let margin: CGFloat = 8

    /// Produces a frame that is always contained by the usable part of the
    /// display. AppKit popovers choose an edge heuristically; Jingle owns this
    /// calculation so call and settlement cards obey the same geometry.
    static func frame(anchor: CGRect, visibleFrame: CGRect, preferredSize: CGSize) -> CGRect {
        let usable = visibleFrame.insetBy(dx: margin, dy: margin)
        guard usable.width > 0, usable.height > 0 else { return .zero }

        let size = CGSize(
            width: min(max(1, preferredSize.width), usable.width),
            height: min(max(1, preferredSize.height), usable.height)
        )
        let x = clamp(anchor.midX - size.width / 2, lower: usable.minX, upper: usable.maxX - size.width)
        let below = anchor.minY - margin - size.height
        let above = anchor.maxY + margin
        let y: CGFloat
        if below >= usable.minY {
            y = below
        } else if above + size.height <= usable.maxY {
            y = above
        } else {
            y = clamp(anchor.midY - size.height / 2, lower: usable.minY, upper: usable.maxY - size.height)
        }
        return CGRect(origin: CGPoint(x: x, y: y), size: size).integral
    }

    private static func clamp(_ value: CGFloat, lower: CGFloat, upper: CGFloat) -> CGFloat {
        min(max(value, lower), max(lower, upper))
    }
}
