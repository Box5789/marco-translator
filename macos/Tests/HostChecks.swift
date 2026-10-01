import AppKit
import Foundation

@main
enum HostChecks {
    static func main() throws {
        try checkRequestCancellationAndReentry()
        try checkVisionOCRAndGeometry()
        try checkPortableRuntime()
        print("P2_HOST_CHECK status=passed ocr=zh-Hans geometry=normalized known=grounded unknown=unresolved persistence=:memory:")
    }

    private static func checkRequestCancellationAndReentry() throws {
        let generations = RequestGeneration()
        let first = generations.begin()
        var staleCommitted = false
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.04) {
            staleCommitted = generations.accepts(first)
        }

        generations.cancel()
        let second = generations.begin()
        precondition(second != first)
        precondition(generations.accepts(second))
        RunLoop.main.run(until: Date().addingTimeInterval(0.08))
        precondition(!staleCommitted, "cancelled request must not commit after re-entry")
        precondition(generations.accepts(second), "new request remains current")
    }

    private static func checkVisionOCRAndGeometry() throws {
        let image = makeFixtureImage(text: "西边有狙")
        let document = try recognizeChineseText(in: image)
        precondition(document.text == "西边有狙", "Vision OCR text differs from the frozen oracle: \(document.text)")
        guard let line = document.lines.first else { preconditionFailure("Vision returned no text geometry") }

        let x = line.bounds.minX * CGFloat(image.width)
        let top = (1 - line.bounds.maxY) * CGFloat(image.height)
        let width = line.bounds.width * CGFloat(image.width)
        let height = line.bounds.height * CGFloat(image.height)
        precondition(x >= 70 && x <= 440, "OCR x-coordinate outside oracle: \(x)")
        precondition(top >= 55 && top <= 150, "OCR y-coordinate outside oracle: \(top)")
        precondition(width >= 250 && width <= 430, "OCR width outside oracle: \(width)")
        precondition(height >= 50 && height <= 120, "OCR height outside oracle: \(height)")

        let selected = CGRect(x: 0.04, y: 0.08, width: 0.54, height: 0.82)
        guard let cropped = cropImage(image, toTopLeftNormalizedRect: selected) else {
            preconditionFailure("controlled region did not crop")
        }
        let twoPixelRegion = CGRect(x: 0.1, y: 0.1, width: 2 / CGFloat(image.width), height: 2 / CGFloat(image.height))
        precondition(cropImage(image, toTopLeftNormalizedRect: twoPixelRegion) != nil,
                     "small non-empty screen regions must remain selectable")
        let onePixelRegion = CGRect(x: 0.1, y: 0.1, width: 1 / CGFloat(image.width), height: 2 / CGFloat(image.height))
        precondition(cropImage(image, toTopLeftNormalizedRect: onePixelRegion) == nil,
                     "sub-two-pixel crops must be rejected")
        let croppedDocument = try recognizeChineseText(in: cropped)
        precondition(croppedDocument.text == "西边有狙", "region OCR differs from the frozen oracle")
        guard let croppedLine = croppedDocument.lines.first else { preconditionFailure("cropped OCR returned no geometry") }
        precondition(croppedLine.bounds.minX > 0 && croppedLine.bounds.maxX < 1)
        precondition(croppedLine.bounds.minY > 0 && croppedLine.bounds.maxY < 1)
        print(String(format: "P2_OCR_FIXTURE text=%@ bbox_px_top_left=%.1f,%.1f,%.1f,%.1f crop=%dx%d",
                     document.text, x, top, width, height, cropped.width, cropped.height))
    }

    private static func checkPortableRuntime() throws {
        let runtime = try PortableRuntime(databasePath: ":memory:")
        let known = try runtime.translate("西边有狙")
        precondition(known.isResolved && known.translatedText == "서쪽에 저격수 있음")
        precondition(known.path == "rule")

        let unknown = try runtime.translate("完全未知的新句子")
        precondition(!unknown.isResolved && unknown.translatedText.isEmpty)
        precondition(unknown.path == "unresolved")
    }

    private static func makeFixtureImage(text: String) -> CGImage {
        let width = 1200
        let height = 280
        let bitmap = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: width, pixelsHigh: height,
                                      bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true,
                                      isPlanar: false, colorSpaceName: .deviceRGB,
                                      bytesPerRow: 0, bitsPerPixel: 0)!
        NSGraphicsContext.saveGraphicsState()
        let context = NSGraphicsContext(bitmapImageRep: bitmap)!
        NSGraphicsContext.current = context
        NSColor.white.setFill()
        NSBezierPath(rect: CGRect(x: 0, y: 0, width: width, height: height)).fill()
        let font = NSFont(name: "PingFang SC", size: 82) ?? NSFont.systemFont(ofSize: 82)
        (text as NSString).draw(at: CGPoint(x: 96, y: 88),
                               withAttributes: [.font: font, .foregroundColor: NSColor.black])
        context.flushGraphics()
        NSGraphicsContext.restoreGraphicsState()
        return bitmap.cgImage!
    }
}
