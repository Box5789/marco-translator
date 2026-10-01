import AppKit
import CoreGraphics

final class RegionCropView: NSView {
    var image: CGImage? {
        didSet {
            selection = nil
            needsDisplay = true
            onSelectionChange?(nil)
        }
    }
    var onSelectionChange: ((CGRect?) -> Void)?

    private var dragStart: CGPoint?
    private var selection: CGRect?

    override var isFlipped: Bool { true }
    override var acceptsFirstResponder: Bool { true }

    override func draw(_ dirtyRect: NSRect) {
        NSColor.windowBackgroundColor.setFill()
        bounds.fill()
        guard let image, let context = NSGraphicsContext.current?.cgContext else { return }

        let destination = fittedRect(imageSize: CGSize(width: image.width, height: image.height), in: bounds)
        context.interpolationQuality = .high
        context.draw(image, in: destination)
        NSColor.separatorColor.setStroke()
        NSBezierPath(rect: destination).stroke()

        if let selection {
            let rect = CGRect(
                x: destination.minX + selection.minX * destination.width,
                y: destination.minY + selection.minY * destination.height,
                width: selection.width * destination.width,
                height: selection.height * destination.height
            )
            NSColor.systemBlue.withAlphaComponent(0.16).setFill()
            NSBezierPath(rect: rect).fill()
            NSColor.systemBlue.setStroke()
            let outline = NSBezierPath(rect: rect)
            outline.lineWidth = 2
            outline.stroke()
        }
    }

    override func mouseDown(with event: NSEvent) {
        guard let image else { return }
        let destination = fittedRect(imageSize: CGSize(width: image.width, height: image.height), in: bounds)
        let point = convert(event.locationInWindow, from: nil)
        guard destination.contains(point) else { return }
        dragStart = point
        selection = normalizedRect(from: point, to: point, in: destination)
        needsDisplay = true
        window?.makeFirstResponder(self)
    }

    override func mouseDragged(with event: NSEvent) {
        guard let image, let dragStart else { return }
        let destination = fittedRect(imageSize: CGSize(width: image.width, height: image.height), in: bounds)
        let point = clamped(convert(event.locationInWindow, from: nil), to: destination)
        selection = normalizedRect(from: dragStart, to: point, in: destination)
        needsDisplay = true
    }

    override func mouseUp(with event: NSEvent) {
        guard let image, let dragStart else { return }
        let destination = fittedRect(imageSize: CGSize(width: image.width, height: image.height), in: bounds)
        let point = clamped(convert(event.locationInWindow, from: nil), to: destination)
        selection = normalizedRect(from: dragStart, to: point, in: destination)
        self.dragStart = nil
        needsDisplay = true
        onSelectionChange?(selection)
    }

    func clearSelection() {
        selection = nil
        dragStart = nil
        needsDisplay = true
        onSelectionChange?(nil)
    }

    private func fittedRect(imageSize: CGSize, in bounds: CGRect) -> CGRect {
        guard imageSize.width > 0, imageSize.height > 0, bounds.width > 0, bounds.height > 0 else { return .zero }
        let scale = min(bounds.width / imageSize.width, bounds.height / imageSize.height)
        let size = CGSize(width: imageSize.width * scale, height: imageSize.height * scale)
        return CGRect(x: bounds.midX - size.width / 2, y: bounds.midY - size.height / 2,
                      width: size.width, height: size.height)
    }

    private func clamped(_ point: CGPoint, to bounds: CGRect) -> CGPoint {
        CGPoint(x: min(max(point.x, bounds.minX), bounds.maxX),
                 y: min(max(point.y, bounds.minY), bounds.maxY))
    }

    private func normalizedRect(from start: CGPoint, to end: CGPoint, in imageRect: CGRect) -> CGRect {
        let lowX = min(start.x, end.x)
        let lowY = min(start.y, end.y)
        let highX = max(start.x, end.x)
        let highY = max(start.y, end.y)
        return CGRect(
            x: (lowX - imageRect.minX) / imageRect.width,
            y: (lowY - imageRect.minY) / imageRect.height,
            width: (highX - lowX) / imageRect.width,
            height: (highY - lowY) / imageRect.height
        )
    }
}
