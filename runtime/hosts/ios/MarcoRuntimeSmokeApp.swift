import CryptoKit
import Foundation
import UIKit

@UIApplicationMain
final class MarcoRuntimeSmokeApp: UIResponder, UIApplicationDelegate {
    var window: UIWindow?

    func application(
        _ application: UIApplication,
        didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?
    ) -> Bool {
        window = UIWindow(frame: UIScreen.main.bounds)
        window?.rootViewController = UIViewController()
        window?.makeKeyAndVisible()
        do {
            try runSmoke()
        } catch {
            fatalError("P1-F iOS smoke failed: \(error)")
        }
        return true
    }

    private func runSmoke() throws {
        guard
            let fixtureURL = Bundle.main.url(forResource: "conformance-v1", withExtension: "json"),
            let fixtureData = try? Data(contentsOf: fixtureURL),
            let fixture = try JSONSerialization.jsonObject(with: fixtureData) as? [String: Any],
            let cases = fixture["cases"] as? [[String: Any]]
        else {
            throw SmokeError.invalidFixture
        }

        let folder = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
        let database = folder.appendingPathComponent("p1f-runtime.sqlite")
        try? FileManager.default.removeItem(at: database)
        try? FileManager.default.removeItem(atPath: database.path + "-wal")
        try? FileManager.default.removeItem(atPath: database.path + "-shm")

        let openStart = ProcessInfo.processInfo.systemUptime
        var runtime: OpaquePointer?
        let path = Data(database.path.utf8)
        let openStatus = path.withUnsafeBufferPointer { bytes in
            marco_runtime_open(bytes.baseAddress, path.count, &runtime)
        }
        guard openStatus == MARCO_RUNTIME_OK, let handle = runtime else {
            throw SmokeError.status("open", statusName(openStatus))
        }
        let openedAt = ProcessInfo.processInfo.systemUptime
        defer {
            if let openHandle = runtime {
                marco_runtime_close(openHandle)
            }
        }

        for item in cases {
            guard
                let request = item["request"] as? [String: Any],
                let expected = item["expected"] as? [String: Any]
            else {
                throw SmokeError.invalidFixture
            }
            let actual = try process(handle, [
                "contract_version": fixture["contract_version"] as? String ?? "",
                "operation": "translate",
                "request": request,
            ])
            guard NSDictionary(dictionary: actual).isEqual(to: expected) else {
                throw SmokeError.fixtureMismatch(item["id"] as? String ?? "unknown")
            }
        }

        try checkBoundaryFailures(handle)
        _ = try process(handle, [
            "contract_version": "marco-runtime.v1",
            "operation": "add_terminology",
            "source": "portable-term",
            "target": "용어",
            "source_language": "zh",
            "target_language": "ko",
            "domain": NSNull(),
            "concept": "PORTABLE_TERM",
            "confidence": 1.0,
            "origin": "user",
        ])
        let overlay = try translate(handle, text: "portable-term", domain: NSNull())
        try require(overlay["path"] as? String == "rule" && overlay["translated_text"] as? String == "용어", "overlay read")

        _ = try process(handle, [
            "contract_version": "marco-runtime.v1",
            "operation": "bind_session_entity",
            "session_id": "p1f-smoke",
            "source": "西边有狙",
            "target": "임시 결과",
            "source_language": "zh",
            "target_language": "ko",
            "domain": "gaming",
            "concept": "SESSION_TERM",
        ])
        let session = try translate(handle, text: "西边有狙", domain: "gaming", sessionID: "p1f-smoke")
        try require(session["path"] as? String == "session" && session["translated_text"] as? String == "임시 결과", "session precedence")

        let correction = try process(handle, [
            "contract_version": "marco-runtime.v1",
            "operation": "correct",
            "request": ["text": "memory-source", "source_language": "zh", "target_language": "ko", "domain": NSNull(), "style": "neutral", "session_id": NSNull()],
            "corrected_text": "기억 번역",
            "generated_text": NSNull(),
        ])
        try require((correction["result"] as? [String: Any])?["tm_written"] as? Bool == true, "correction TM write")
        let memory = try translate(handle, text: "memory-source", domain: NSNull())
        try require(memory["path"] as? String == "tm" && memory["translated_text"] as? String == "기억 번역", "TM read")
        marco_runtime_close(handle)
        runtime = nil

        var reopened: OpaquePointer?
        let reopenStatus = path.withUnsafeBufferPointer { bytes in
            marco_runtime_open(bytes.baseAddress, path.count, &reopened)
        }
        guard reopenStatus == MARCO_RUNTIME_OK, let reopenedHandle = reopened else {
            throw SmokeError.status("reopen", statusName(reopenStatus))
        }
        defer { marco_runtime_close(reopenedHandle) }
        let persisted = try translate(reopenedHandle, text: "memory-source", domain: NSNull())
        try require(persisted["path"] as? String == "tm" && persisted["translated_text"] as? String == "기억 번역", "TM persistence")
        let persistedTerm = try translate(reopenedHandle, text: "portable-term", domain: NSNull())
        try require(persistedTerm["path"] as? String == "rule" && persistedTerm["translated_text"] as? String == "용어", "overlay persistence")
        let sessionAfterReopen = try translate(reopenedHandle, text: "西边有狙", domain: "gaming", sessionID: "p1f-smoke")
        try require(sessionAfterReopen["path"] as? String == "rule" && sessionAfterReopen["translated_text"] as? String == "서쪽에 저격수 있음", "session is ephemeral")

        let finishedAt = ProcessInfo.processInfo.systemUptime
        let hash = SHA256.hash(data: fixtureData).map { String(format: "%02x", $0) }.joined()
        let report: [String: Any] = [
            "contract_version": fixture["contract_version"] as? String ?? "",
            "fixture_sha256": hash,
            "fixture_cases": cases.count,
            "platform": "iOS Simulator \(UIDevice.current.systemVersion)",
            "network_dependency": "none",
            "startup_ms": (openedAt - openStart) * 1000,
            "runtime_ms": (finishedAt - openedAt) * 1000,
            "checks": ["fixtures", "ffi_errors", "overlay", "session", "tm", "reopen"],
        ]
        let reportURL = folder.appendingPathComponent("p1f-report.json")
        try JSONSerialization.data(withJSONObject: report, options: [.sortedKeys]).write(to: reportURL)
        print("P1F_REPORT \(String(data: try JSONSerialization.data(withJSONObject: report, options: [.sortedKeys]), encoding: .utf8)!)")
    }

    private func translate(_ handle: OpaquePointer, text: String, domain: Any, sessionID: String? = nil) throws -> [String: Any] {
        try process(handle, [
            "contract_version": "marco-runtime.v1",
            "operation": "translate",
            "request": ["text": text, "source_language": "zh", "target_language": "ko", "domain": domain, "style": "neutral", "session_id": sessionID as Any? ?? NSNull()],
        ])["result"] as? [String: Any] ?? [:]
    }

    private func process(_ handle: OpaquePointer, _ document: [String: Any]) throws -> [String: Any] {
        let input = try JSONSerialization.data(withJSONObject: document, options: [.sortedKeys])
        var output: UnsafeMutablePointer<CChar>? = nil
        let status = input.withUnsafeBytes { bytes in
            marco_runtime_process_json(handle, bytes.bindMemory(to: UInt8.self).baseAddress, input.count, &output)
        }
        guard status == MARCO_RUNTIME_OK, let json = output else {
            throw SmokeError.status("process", statusName(status))
        }
        defer { marco_runtime_string_free(json) }
        let data = Data(String(cString: json).utf8)
        guard let response = try JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            throw SmokeError.invalidResponse
        }
        return response
    }

    private func checkBoundaryFailures(_ handle: OpaquePointer) throws {
        var output: UnsafeMutablePointer<CChar>?
        let badUTF8 = [UInt8(0xff)]
        let utf8Status = badUTF8.withUnsafeBufferPointer {
            marco_runtime_process_json(handle, $0.baseAddress, badUTF8.count, &output)
        }
        try require(utf8Status == MARCO_RUNTIME_INVALID_UTF8 && output == nil, "invalid UTF-8")
        let invalidJSON = Data("{".utf8)
        let jsonStatus = invalidJSON.withUnsafeBytes {
            marco_runtime_process_json(handle, $0.bindMemory(to: UInt8.self).baseAddress, invalidJSON.count, &output)
        }
        try require(jsonStatus == MARCO_RUNTIME_INVALID_JSON && output == nil, "invalid JSON")
        let unsupported = Data("{\"contract_version\":\"marco-runtime.v2\",\"operation\":\"translate\"}".utf8)
        let contractStatus = unsupported.withUnsafeBytes {
            marco_runtime_process_json(handle, $0.bindMemory(to: UInt8.self).baseAddress, unsupported.count, &output)
        }
        try require(contractStatus == MARCO_RUNTIME_UNSUPPORTED_CONTRACT && output == nil, "unsupported contract")
        let oversized = Data(repeating: 0x20, count: 1024 * 1024 + 1)
        let sizeStatus = oversized.withUnsafeBytes {
            marco_runtime_process_json(handle, $0.bindMemory(to: UInt8.self).baseAddress, oversized.count, &output)
        }
        try require(sizeStatus == MARCO_RUNTIME_INPUT_TOO_LARGE && output == nil, "oversized input")
        try require(String(cString: marco_runtime_status_name(999)) == "unknown_status", "unknown status")
    }

    private func statusName(_ status: Int32) -> String {
        String(cString: marco_runtime_status_name(status))
    }

    private func require(_ condition: @autoclosure () -> Bool, _ message: String) throws {
        if !condition() { throw SmokeError.checkFailed(message) }
    }
}

private enum SmokeError: Error {
    case invalidFixture
    case invalidResponse
    case fixtureMismatch(String)
    case checkFailed(String)
    case status(String, String)
}
