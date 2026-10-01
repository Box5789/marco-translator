import AppKit
import Foundation
import Vision

struct OCRLine {
    let text: String
    let bounds: CGRect
}

struct OCRDocument {
    let text: String
    let lines: [OCRLine]
}

struct RuntimeTranslation {
    let sourceText: String
    let translatedText: String
    let path: String
    let confidence: Double
    let warnings: [String]

    var isResolved: Bool { path != "unresolved" && !translatedText.isEmpty }
}

enum CaptureHostError: LocalizedError {
    case noSupportedChineseLanguage
    case runtimeOpen(Int32)
    case runtimeRequest(Int32)
    case invalidRuntimeResponse

    var errorDescription: String? {
        switch self {
        case .noSupportedChineseLanguage:
            return "이 Mac의 Vision OCR에서 간체 중국어를 사용할 수 없습니다."
        case let .runtimeOpen(status):
            return "번역 런타임을 열지 못했습니다. 상태 코드: \(status)"
        case let .runtimeRequest(status):
            return "번역 런타임 요청이 실패했습니다. 상태 코드: \(status)"
        case .invalidRuntimeResponse:
            return "번역 런타임 응답이 계약 형식과 일치하지 않습니다."
        }
    }
}

final class RequestGeneration {
    private(set) var current: UInt64 = 0

    @discardableResult
    func begin() -> UInt64 {
        current &+= 1
        return current
    }

    func cancel() {
        current &+= 1
    }

    func accepts(_ request: UInt64) -> Bool {
        request == current
    }
}

func cropImage(_ image: CGImage, toTopLeftNormalizedRect rect: CGRect) -> CGImage? {
    let unit = CGRect(x: 0, y: 0, width: 1, height: 1)
    let selected = rect.standardized.intersection(unit)
    guard !selected.isNull, !selected.isEmpty else { return nil }

    let pixelBounds = CGRect(x: 0, y: 0, width: image.width, height: image.height)
    let pixelRect = CGRect(
        x: selected.minX * CGFloat(image.width),
        y: selected.minY * CGFloat(image.height),
        width: selected.width * CGFloat(image.width),
        height: selected.height * CGFloat(image.height)
    ).integral.intersection(pixelBounds)
    guard !pixelRect.isNull, pixelRect.width >= 2, pixelRect.height >= 2 else { return nil }
    return image.cropping(to: pixelRect)
}

func recognizeChineseText(in image: CGImage) throws -> OCRDocument {
    let request = VNRecognizeTextRequest()
    request.revision = VNRecognizeTextRequestRevision3
    request.recognitionLevel = .accurate
    request.recognitionLanguages = ["zh-Hans"]
    request.usesLanguageCorrection = true

    guard try request.supportedRecognitionLanguages().contains("zh-Hans") else {
        throw CaptureHostError.noSupportedChineseLanguage
    }
    try VNImageRequestHandler(cgImage: image, orientation: .up).perform([request])

    let lines = (request.results ?? []).compactMap { observation -> OCRLine? in
        guard let text = observation.topCandidates(1).first?.string else { return nil }
        return OCRLine(text: text, bounds: observation.boundingBox)
    }.sorted {
        if abs($0.bounds.midY - $1.bounds.midY) > 0.02 {
            return $0.bounds.midY > $1.bounds.midY
        }
        return $0.bounds.minX < $1.bounds.minX
    }
    return OCRDocument(text: lines.map(\.text).joined(separator: "\n"), lines: lines)
}

final class PortableRuntime {
    private var handle: OpaquePointer?

    init(databasePath: String = ":memory:") throws {
        let bytes = Array(databasePath.utf8)
        let status = bytes.withUnsafeBufferPointer { buffer in
            marco_runtime_open(buffer.baseAddress, buffer.count, &handle)
        }
        guard status == MARCO_RUNTIME_OK, handle != nil else {
            throw CaptureHostError.runtimeOpen(status)
        }
    }

    deinit {
        if let handle {
            marco_runtime_close(handle)
        }
    }

    func translate(_ text: String) throws -> RuntimeTranslation {
        let request: [String: Any] = [
            "contract_version": "marco-runtime.v1",
            "operation": "translate",
            "request": [
                "text": text,
                "source_language": "zh",
                "target_language": "ko",
                "domain": "gaming",
                "style": "neutral",
                "session_id": NSNull(),
            ],
        ]
        let input = try JSONSerialization.data(withJSONObject: request, options: [.sortedKeys])
        var output: UnsafeMutablePointer<CChar>?
        let status = input.withUnsafeBytes { buffer in
            marco_runtime_process_json(
                handle,
                buffer.baseAddress?.assumingMemoryBound(to: UInt8.self),
                buffer.count,
                &output
            )
        }
        guard status == MARCO_RUNTIME_OK, let output else {
            throw CaptureHostError.runtimeRequest(status)
        }
        defer { marco_runtime_string_free(output) }

        guard let data = String(cString: output).data(using: .utf8),
              let envelope = try JSONSerialization.jsonObject(with: data) as? [String: Any],
              envelope["contract_version"] as? String == "marco-runtime.v1",
              let result = envelope["result"] as? [String: Any],
              let sourceText = result["source_text"] as? String,
              let translatedText = result["translated_text"] as? String,
              let path = result["path"] as? String,
              let confidence = result["confidence"] as? Double else {
            throw CaptureHostError.invalidRuntimeResponse
        }
        return RuntimeTranslation(
            sourceText: sourceText,
            translatedText: translatedText,
            path: path,
            confidence: confidence,
            warnings: result["warnings"] as? [String] ?? []
        )
    }
}
