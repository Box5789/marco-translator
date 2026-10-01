import AppKit
import CoreGraphics
import ScreenCaptureKit

@MainActor
final class AppDelegate: NSObject, NSApplicationDelegate, @preconcurrency SCContentSharingPickerObserver {
    private let generations = RequestGeneration()
    private let picker = SCContentSharingPicker.shared
    private var activeRequest: UInt64?
    private var pendingSelection: UInt64?
    private var capturedFrame: CGImage?
    private var captureStartedAt: TimeInterval?
    private var captureMilliseconds = 0.0
    private var runtime: PortableRuntime?
    private var overlay: TranslationOverlay?
    private var window: NSWindow!
    private var captureButton: NSButton!
    private var cancelButton: NSButton!
    private var translateButton: NSButton!
    private var settingsButton: NSButton!
    private var statusLabel: NSTextField!
    private var timingLabel: NSTextField!
    private var cropView: RegionCropView!
    private var selectedRegion: CGRect?
    private var timingSamples: [String: [Double]] = [:]

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApplication.shared.setActivationPolicy(.regular)
        installPickerConfiguration()
        picker.add(self)
        createMainWindow()
        do {
            runtime = try PortableRuntime()
        } catch {
            setStatus("번역 런타임을 준비하지 못했습니다: \(error.localizedDescription)")
        }
        window.makeKeyAndOrderFront(nil)
        NSApplication.shared.activate(ignoringOtherApps: true)
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }

    func contentSharingPicker(_ picker: SCContentSharingPicker, didUpdateWith filter: SCContentFilter, for stream: SCStream?) {
        DispatchQueue.main.async { [weak self] in
            guard let self,
                  let request = self.pendingSelection,
                  self.generations.accepts(request) else { return }
            self.pendingSelection = nil
            self.picker.isActive = false
            self.capture(filter, request: request)
        }
    }

    func contentSharingPicker(_ picker: SCContentSharingPicker, didCancelFor stream: SCStream?) {
        DispatchQueue.main.async { [weak self] in
            guard let self,
                  let request = self.pendingSelection,
                  self.generations.accepts(request) else { return }
            self.picker.isActive = false
            self.cancelCurrentRequest()
            self.setStatus("캡처를 취소했습니다. 다시 시작할 수 있습니다.")
        }
    }

    func contentSharingPickerStartDidFailWithError(_ error: Error) {
        DispatchQueue.main.async { [weak self] in
            guard let self, let request = self.pendingSelection,
                  self.generations.accepts(request) else { return }
            self.cancelCurrentRequest()
            self.setStatus("시스템 선택기를 열지 못했습니다: \(error.localizedDescription)")
        }
    }

    @objc private func startCapture(_ sender: NSButton) {
        cancelCurrentRequest()
        if !CGPreflightScreenCaptureAccess() {
            let granted = CGRequestScreenCaptureAccess()
            guard granted && CGPreflightScreenCaptureAccess() else {
                setStatus("화면 기록 권한이 필요합니다. 권한을 허용한 뒤 앱에서 다시 시도하세요.")
                return
            }
        }

        let request = generations.begin()
        activeRequest = request
        pendingSelection = request
        selectedRegion = nil
        capturedFrame = nil
        cropView.image = nil
        cropView.clearSelection()
        translateButton.isEnabled = false
        overlay?.close()
        overlay = nil
        setStatus("시스템 선택기에서 번역할 창 또는 디스플레이를 고르세요.")
        picker.isActive = true
        picker.present()
    }

    @objc private func cancelCapture(_ sender: NSButton) {
        cancelCurrentRequest()
        setStatus("현재 요청을 취소했습니다. 원본 화면은 변경되지 않았습니다.")
    }

    @objc private func translateSelection(_ sender: NSButton) {
        guard let request = activeRequest,
              generations.accepts(request),
              let capturedFrame,
              let selectedRegion,
              let cropped = cropImage(capturedFrame, toTopLeftNormalizedRect: selectedRegion) else {
            setStatus("번역할 영역을 드래그해서 선택하세요.")
            return
        }
        guard self.runtime != nil else {
            setStatus("번역 런타임을 사용할 수 없습니다.")
            return
        }

        captureButton.isEnabled = false
        translateButton.isEnabled = false
        setStatus("선택 영역에서 중국어 텍스트를 읽고 있습니다.")
        let processingStartedAt = ProcessInfo.processInfo.systemUptime
        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            let ocrStartedAt = ProcessInfo.processInfo.systemUptime
            let ocrResult = Result { try recognizeChineseText(in: cropped) }
            let ocrMilliseconds = (ProcessInfo.processInfo.systemUptime - ocrStartedAt) * 1000

            DispatchQueue.main.async {
                guard let self, self.generations.accepts(request) else { return }
                switch ocrResult {
                case let .failure(error):
                    self.finishWithError("OCR에 실패했습니다: \(error.localizedDescription)")
                case let .success(document):
                    guard !document.text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
                        self.finishWithError("선택 영역에서 텍스트를 찾지 못했습니다.")
                        return
                    }
                    self.setStatus("OCR이 텍스트를 찾았습니다. 기존 번역 계약에 전달합니다.")
                    guard let runtime = self.runtime else {
                        self.finishWithError("번역 런타임을 사용할 수 없습니다.")
                        return
                    }
                    let translationStartedAt = ProcessInfo.processInfo.systemUptime
                    let translationResult = Result { try runtime.translate(document.text) }
                    let translationMilliseconds = (ProcessInfo.processInfo.systemUptime - translationStartedAt) * 1000
                    guard self.generations.accepts(request) else { return }
                    switch translationResult {
                    case let .failure(error):
                        self.finishWithError(error.localizedDescription)
                    case let .success(translation):
                        self.showTranslation(
                            translation,
                            request: request,
                            captureMS: self.captureMilliseconds,
                            ocrMS: ocrMilliseconds,
                            translationMS: translationMilliseconds,
                            processingStartedAt: processingStartedAt
                        )
                    }
                }
            }
        }
    }

    @objc private func openScreenRecordingSettings(_ sender: NSButton) {
        guard let url = URL(string: "x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture") else { return }
        NSWorkspace.shared.open(url)
    }

    private func installPickerConfiguration() {
        var configuration = SCContentSharingPickerConfiguration()
        configuration.allowedPickerModes = [.singleWindow, .singleDisplay]
        configuration.allowsChangingSelectedContent = false
        configuration.excludedBundleIDs = [Bundle.main.bundleIdentifier ?? "com.box5789.marco-translator.p2"]
        picker.defaultConfiguration = configuration
    }

    private func capture(_ filter: SCContentFilter, request: UInt64) {
        guard generations.accepts(request) else { return }
        setStatus("선택한 화면을 메모리에서 한 번 캡처합니다.")
        captureStartedAt = ProcessInfo.processInfo.systemUptime

        let configuration = SCStreamConfiguration()
        configuration.showsCursor = false
        let info = SCShareableContent.info(for: filter)
        let pixelScale = CGFloat(info.pointPixelScale)
        if info.contentRect.width > 0, info.contentRect.height > 0, pixelScale > 0 {
            configuration.width = max(1, Int(info.contentRect.width * pixelScale))
            configuration.height = max(1, Int(info.contentRect.height * pixelScale))
        }

        SCScreenshotManager.captureImage(contentFilter: filter, configuration: configuration) { [weak self] image, error in
            DispatchQueue.main.async {
                guard let self, self.generations.accepts(request) else { return }
                guard let image, error == nil else {
                    let message = error?.localizedDescription ?? "캡처된 이미지가 없습니다."
                    self.activeRequest = nil
                    self.setStatus(CGPreflightScreenCaptureAccess()
                        ? "화면을 캡처하지 못했습니다: \(message)"
                        : "화면 기록 권한이 없거나 제한되어 있습니다. 시스템 설정에서 허용한 뒤 다시 시도하세요.")
                    return
                }
                self.captureMilliseconds = self.captureStartedAt.map {
                    (ProcessInfo.processInfo.systemUptime - $0) * 1000
                } ?? 0
                self.capturedFrame = image
                self.cropView.image = image
                self.activeRequest = request
                self.captureButton.isEnabled = true
                self.setStatus("캡처 완료 (\(image.width) × \(image.height) px). 이미지에서 번역할 영역을 드래그하세요.")
            }
        }
    }

    private func showTranslation(
        _ translation: RuntimeTranslation,
        request: UInt64,
        captureMS: Double,
        ocrMS: Double,
        translationMS: Double,
        processingStartedAt: TimeInterval
    ) {
        guard generations.accepts(request) else { return }
        let overlayStartedAt = ProcessInfo.processInfo.systemUptime
        let message = translation.isResolved
            ? translation.translatedText
            : "확정된 번역이 없어 결과를 표시하지 않았습니다."
        let panel = TranslationOverlay(message: message) { [weak self] in
            self?.overlay = nil
            self?.activeRequest = nil
        }
        panel.show()
        overlay = panel
        let overlayMS = (ProcessInfo.processInfo.systemUptime - overlayStartedAt) * 1000
        let processingMS = captureMS + (ProcessInfo.processInfo.systemUptime - processingStartedAt) * 1000
        recordTiming("capture", captureMS)
        recordTiming("ocr", ocrMS)
        recordTiming("translation", translationMS)
        recordTiming("overlay", overlayMS)
        recordTiming("processing", processingMS)

        capturedFrame = nil
        cropView.image = nil
        cropView.clearSelection()
        selectedRegion = nil
        captureButton.isEnabled = true
        let resultDescription = translation.isResolved
            ? "번역 결과를 임시 패널에 표시했습니다."
            : "미등록 입력을 미확정 상태로 처리했습니다. 추측 결과는 표시하지 않았습니다."
        setStatus("\(resultDescription) · 경로 \(translation.path)")
        updateTimingLabel()
    }

    private func recordTiming(_ stage: String, _ milliseconds: Double) {
        timingSamples[stage, default: []].append(milliseconds)
    }

    private func updateTimingLabel() {
        let stages = ["capture", "ocr", "translation", "overlay", "processing"]
        let count = timingSamples["processing"]?.count ?? 0
        let measurements = stages.map { stage in
            let values = timingSamples[stage] ?? []
            return "\(stage)=p50 \(percentile(values, 0.50)) / p90 \(percentile(values, 0.90)) ms"
        }
        timingLabel.stringValue = "처리 시간 n=\(count): " + measurements.joined(separator: " · ")
    }

    private func percentile(_ values: [Double], _ quantile: Double) -> String {
        guard !values.isEmpty else { return "—" }
        let sorted = values.sorted()
        let index = max(0, Int(ceil(quantile * Double(sorted.count))) - 1)
        return String(format: "%.1f", sorted[index])
    }

    private func cancelCurrentRequest() {
        generations.cancel()
        activeRequest = nil
        pendingSelection = nil
        picker.isActive = false
        capturedFrame = nil
        captureStartedAt = nil
        selectedRegion = nil
        cropView?.image = nil
        cropView?.clearSelection()
        translateButton?.isEnabled = false
        captureButton?.isEnabled = true
        overlay?.close()
        overlay = nil
    }

    private func finishWithError(_ message: String) {
        activeRequest = nil
        capturedFrame = nil
        selectedRegion = nil
        cropView.image = nil
        cropView.clearSelection()
        captureButton.isEnabled = true
        translateButton.isEnabled = false
        setStatus(message)
    }

    private func setStatus(_ message: String) {
        statusLabel?.stringValue = message
    }

    private func createMainWindow() {
        let content = NSView()
        content.translatesAutoresizingMaskIntoConstraints = false

        captureButton = NSButton(title: "창 또는 디스플레이 선택", target: self, action: #selector(startCapture(_:)))
        cancelButton = NSButton(title: "취소", target: self, action: #selector(cancelCapture(_:)))
        translateButton = NSButton(title: "선택 영역 번역", target: self, action: #selector(translateSelection(_:)))
        settingsButton = NSButton(title: "화면 기록 권한 설정 열기", target: self, action: #selector(openScreenRecordingSettings(_:)))
        translateButton.isEnabled = false

        statusLabel = NSTextField(wrappingLabelWithString: "명시적으로 선택한 창 또는 디스플레이를 한 번 캡처합니다.")
        statusLabel.maximumNumberOfLines = 3
        timingLabel = NSTextField(wrappingLabelWithString: "처리 시간은 메모리에만 집계됩니다.")
        timingLabel.maximumNumberOfLines = 3
        cropView = RegionCropView()
        cropView.translatesAutoresizingMaskIntoConstraints = false
        cropView.setAccessibilityLabel("번역할 화면 영역 선택")
        cropView.onSelectionChange = { [weak self] region in
            self?.selectedRegion = region
            self?.translateButton.isEnabled = region != nil && self?.capturedFrame != nil
        }

        let controls = NSStackView(views: [captureButton, translateButton, cancelButton, settingsButton])
        controls.orientation = .horizontal
        controls.alignment = .centerY
        controls.distribution = .fill
        controls.spacing = 8

        let stack = NSStackView(views: [controls, statusLabel, cropView, timingLabel])
        stack.orientation = .vertical
        stack.alignment = .leading
        stack.distribution = .fill
        stack.spacing = 12
        stack.translatesAutoresizingMaskIntoConstraints = false
        content.addSubview(stack)

        NSLayoutConstraint.activate([
            stack.leadingAnchor.constraint(equalTo: content.leadingAnchor, constant: 16),
            stack.trailingAnchor.constraint(equalTo: content.trailingAnchor, constant: -16),
            stack.topAnchor.constraint(equalTo: content.topAnchor, constant: 16),
            stack.bottomAnchor.constraint(equalTo: content.bottomAnchor, constant: -16),
            cropView.widthAnchor.constraint(equalTo: stack.widthAnchor),
            cropView.heightAnchor.constraint(equalToConstant: 430),
            statusLabel.widthAnchor.constraint(equalTo: stack.widthAnchor),
            timingLabel.widthAnchor.constraint(equalTo: stack.widthAnchor),
        ])

        window = NSWindow(contentRect: CGRect(x: 0, y: 0, width: 940, height: 560),
                          styleMask: [.titled, .closable, .miniaturizable, .resizable],
                          backing: .buffered, defer: false)
        window.title = "Marco Translator · 화면 번역"
        window.contentView = content
        window.center()
        window.sharingType = .none
    }
}

@MainActor
private final class TranslationOverlay: NSObject, NSWindowDelegate {
    private let panel: NSPanel
    private let onClose: () -> Void
    private var didNotifyClose = false

    init(message: String, onClose: @escaping () -> Void) {
        self.onClose = onClose
        let panel = NSPanel(contentRect: CGRect(x: 0, y: 0, width: 400, height: 150),
                            styleMask: [.titled, .closable, .nonactivatingPanel, .utilityWindow],
                            backing: .buffered, defer: false)
        self.panel = panel
        super.init()
        panel.title = "Marco Translator"
        panel.level = .floating
        panel.collectionBehavior = [.canJoinAllSpaces, .transient, .ignoresCycle]
        panel.sharingType = .none
        panel.hidesOnDeactivate = false
        panel.isReleasedWhenClosed = false
        panel.isMovableByWindowBackground = true
        panel.delegate = self

        let label = NSTextField(wrappingLabelWithString: message)
        label.maximumNumberOfLines = 5
        label.setAccessibilityLabel("번역 결과")
        let closeButton = NSButton(title: "닫기", target: self, action: #selector(closePanel(_:)))
        let stack = NSStackView(views: [label, closeButton])
        stack.orientation = .vertical
        stack.alignment = .leading
        stack.distribution = .fill
        stack.spacing = 12
        stack.translatesAutoresizingMaskIntoConstraints = false
        let content = NSView()
        content.addSubview(stack)
        NSLayoutConstraint.activate([
            stack.leadingAnchor.constraint(equalTo: content.leadingAnchor, constant: 16),
            stack.trailingAnchor.constraint(equalTo: content.trailingAnchor, constant: -16),
            stack.topAnchor.constraint(equalTo: content.topAnchor, constant: 16),
            stack.bottomAnchor.constraint(equalTo: content.bottomAnchor, constant: -16),
            label.widthAnchor.constraint(equalTo: stack.widthAnchor),
        ])
        panel.contentView = content
    }

    func show() {
        if let screen = NSScreen.main?.visibleFrame {
            panel.setFrameOrigin(CGPoint(x: screen.maxX - panel.frame.width - 24,
                                         y: screen.maxY - panel.frame.height - 48))
        }
        panel.orderFrontRegardless()
    }

    func close() {
        guard panel.isVisible else { return }
        panel.close()
    }

    @objc private func closePanel(_ sender: NSButton) { close() }

    func windowWillClose(_ notification: Notification) {
        guard !didNotifyClose else { return }
        didNotifyClose = true
        onClose()
    }
}

@main
enum MarcoCaptureMain {
    @MainActor
    static func main() {
        let application = NSApplication.shared
        let delegate = AppDelegate()
        application.delegate = delegate
        application.run()
    }
}
