import CoreGraphics
import Foundation

func require(_ condition: @autoclosure () -> Bool, _ message: String) {
    guard condition() else { fatalError(message) }
}

func requireContained(_ frame: CGRect, in visible: CGRect, label: String) {
    require(visible.contains(frame), "\(label): \(frame) is outside \(visible)")
}

@main
struct JinglePanelLayoutTests {
    static func main() {
        let main = CGRect(x: 0, y: 0, width: 1440, height: 900)
        for (label, anchor) in [
            ("main-left", CGRect(x: 0, y: 876, width: 24, height: 24)),
            ("main-center", CGRect(x: 708, y: 876, width: 24, height: 24)),
            ("main-right", CGRect(x: 1416, y: 876, width: 24, height: 24)),
        ] {
            requireContained(JinglePanelLayout.frame(anchor: anchor, visibleFrame: main, preferredSize: CGSize(width: 380, height: 460)), in: main, label: label)
        }

let external = CGRect(x: -1920, y: -80, width: 1920, height: 1080)
for (label, anchor) in [
    ("external-left", CGRect(x: -1920, y: 976, width: 24, height: 24)),
    ("external-center", CGRect(x: -972, y: 976, width: 24, height: 24)),
    ("external-right", CGRect(x: -30, y: 976, width: 24, height: 24)),
] {
    requireContained(JinglePanelLayout.frame(anchor: anchor, visibleFrame: external, preferredSize: CGSize(width: 380, height: 460)), in: external, label: label)
}

        let constrained = CGRect(x: 0, y: 0, width: 400, height: 180)
        let constrainedFrame = JinglePanelLayout.frame(anchor: CGRect(x: 188, y: 156, width: 24, height: 24), visibleFrame: constrained, preferredSize: CGSize(width: 380, height: 920))
        requireContained(constrainedFrame, in: constrained, label: "constrained-height")
        require(constrainedFrame.height < 920, "constrained-height: panel must cap its height")

        print("JinglePanelLayoutTests passed")
    }
}
