import AppKit
import Foundation
import SwiftUI

private let pythonPath = "/usr/bin/python3"
private let notifierPath = FileManager.default.homeDirectoryForCurrentUser
    .appendingPathComponent(".codex/hooks/codex_spoken_notify.py")
    .path

struct NotifySettings: Codable, Equatable {
    var schemaVersion: Int = 4
    var successSound: String
    var attentionSound: String
    var effectVolume: Double
    var speechEnabled: Bool
    var speechContent: String
    var voiceProfile: String

    enum CodingKeys: String, CodingKey {
        case schemaVersion = "schema_version"
        case successSound = "success_sound"
        case attentionSound = "attention_sound"
        case effectVolume = "effect_volume"
        case speechEnabled = "speech_enabled"
        case speechContent = "speech_content"
        case voiceProfile = "voice_profile"
    }
}

struct ChoiceOption: Codable, Identifiable, Equatable {
    let id: String
    let name: String
    let mood: String
    let source: String?
}

struct SoundOption: Codable, Identifiable, Equatable {
    let name: String
    let mood: String
    let path: String
    let source: String

    var id: String { path }
}

struct SettingsData: Codable {
    let settings: NotifySettings
    let defaults: NotifySettings
    let successSounds: [SoundOption]
    let attentionSounds: [SoundOption]
    let voiceOptions: [ChoiceOption]
    let speechContentOptions: [ChoiceOption]
    let settingsPath: String

    enum CodingKeys: String, CodingKey {
        case settings, defaults
        case successSounds = "success_sounds"
        case attentionSounds = "attention_sounds"
        case voiceOptions = "voice_options"
        case speechContentOptions = "speech_content_options"
        case settingsPath = "settings_path"
    }
}

struct PreviewRequest: Codable {
    let status: String
    let settings: NotifySettings
    var title: String? = nil
}

enum BridgeError: LocalizedError {
    case failed(String)

    var errorDescription: String? {
        switch self {
        case .failed(let message): return message
        }
    }
}

@discardableResult
func runNotifier(arguments: [String], input: Data? = nil) throws -> Data {
    let process = Process()
    process.executableURL = URL(fileURLWithPath: pythonPath)
    process.arguments = [notifierPath] + arguments
    let output = Pipe()
    let errors = Pipe()
    process.standardOutput = output
    process.standardError = errors
    if let input {
        let stdin = Pipe()
        process.standardInput = stdin
        try process.run()
        stdin.fileHandleForWriting.write(input)
        try stdin.fileHandleForWriting.close()
    } else {
        try process.run()
    }
    process.waitUntilExit()
    let data = output.fileHandleForReading.readDataToEndOfFile()
    if process.terminationStatus != 0 {
        let errorData = errors.fileHandleForReading.readDataToEndOfFile()
        let message = String(data: errorData.isEmpty ? data : errorData, encoding: .utf8)
            ?? "本地通知工具执行失败。"
        throw BridgeError.failed(message.trimmingCharacters(in: .whitespacesAndNewlines))
    }
    return data
}

final class SettingsModel: ObservableObject {
    enum State {
        case loading
        case ready
        case dirty
        case saved
        case failed
    }

    @Published var successSounds: [SoundOption] = []
    @Published var attentionSounds: [SoundOption] = []
    @Published var successSound = ""
    @Published var attentionSound = ""
    @Published var effectVolume = 100.0
    @Published var speechEnabled = true
    @Published var speechContent = "title_status"
    @Published var voiceProfile = "warm_female"
    @Published var voiceOptions: [ChoiceOption] = []
    @Published var speechContentOptions: [ChoiceOption] = []
    @Published var state: State = .loading
    @Published var statusText = "载入中"
    @Published var previewing: String?
    @Published var isSaving = false

    private var savedSettings: NotifySettings?

    init() {
        reload()
    }

    var candidate: NotifySettings {
        NotifySettings(
            successSound: successSound,
            attentionSound: attentionSound,
            effectVolume: (effectVolume / 100.0 * 100).rounded() / 100,
            speechEnabled: speechEnabled,
            speechContent: speechContent,
            voiceProfile: voiceProfile
        )
    }

    var isBusy: Bool {
        state == .loading || previewing != nil || isSaving
    }

    var isDirty: Bool {
        guard let savedSettings else { return false }
        return candidate != savedSettings
    }

    func reload() {
        state = .loading
        statusText = "载入中"
        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            do {
                let data = try runNotifier(arguments: ["--settings-data"])
                let payload = try JSONDecoder().decode(SettingsData.self, from: data)
                DispatchQueue.main.async {
                    guard let self else { return }
                    self.successSounds = payload.successSounds
                    self.attentionSounds = payload.attentionSounds
                    self.successSound = payload.settings.successSound
                    self.attentionSound = payload.settings.attentionSound
                    self.effectVolume = payload.settings.effectVolume * 100
                    self.speechEnabled = payload.settings.speechEnabled
                    self.speechContent = payload.settings.speechContent
                    self.voiceProfile = payload.settings.voiceProfile
                    self.voiceOptions = payload.voiceOptions
                    self.speechContentOptions = payload.speechContentOptions
                    self.savedSettings = payload.settings
                    self.state = .ready
                    self.statusText = "就绪"
                }
            } catch {
                DispatchQueue.main.async {
                    self?.state = .failed
                    self?.statusText = "读取失败"
                }
            }
        }
    }

    func markChanged() {
        guard state != .loading, !isSaving else { return }
        if isDirty {
            state = .dirty
            statusText = "未保存"
        } else {
            state = .ready
            statusText = "就绪"
        }
    }

    func previewSound(_ previewStatus: String) {
        guard !isBusy else { return }
        let request = PreviewRequest(status: previewStatus, settings: candidate)
        previewing = previewStatus
        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            do {
                let input = try JSONEncoder().encode(request)
                _ = try runNotifier(arguments: ["--preview-sound-json"], input: input)
                DispatchQueue.main.async {
                    guard let self else { return }
                    self.previewing = nil
                    self.markChanged()
                }
            } catch {
                DispatchQueue.main.async {
                    self?.previewing = nil
                    self?.state = .failed
                    self?.statusText = "试听失败"
                }
            }
        }
    }

    func previewSpeech() {
        guard !isBusy, speechEnabled else { return }
        let request = PreviewRequest(
            status: "success",
            settings: candidate,
            title: "Codex 测试任务"
        )
        previewing = "speech"
        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            do {
                let input = try JSONEncoder().encode(request)
                _ = try runNotifier(arguments: ["--preview-speech-json"], input: input)
                DispatchQueue.main.async {
                    guard let self else { return }
                    self.previewing = nil
                    self.markChanged()
                }
            } catch {
                DispatchQueue.main.async {
                    self?.previewing = nil
                    self?.state = .failed
                    self?.statusText = "播报失败"
                }
            }
        }
    }

    func save() {
        guard !isBusy, isDirty else { return }
        let settings = candidate
        isSaving = true
        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            do {
                let input = try JSONEncoder().encode(settings)
                let data = try runNotifier(arguments: ["--save-settings-json"], input: input)
                let saved = try JSONDecoder().decode(NotifySettings.self, from: data)
                DispatchQueue.main.async {
                    guard let self else { return }
                    self.savedSettings = saved
                    self.successSound = saved.successSound
                    self.attentionSound = saved.attentionSound
                    self.effectVolume = saved.effectVolume * 100
                    self.speechEnabled = saved.speechEnabled
                    self.speechContent = saved.speechContent
                    self.voiceProfile = saved.voiceProfile
                    self.isSaving = false
                    self.state = .saved
                    self.statusText = "已保存"
                }
            } catch {
                DispatchQueue.main.async {
                    self?.isSaving = false
                    self?.state = .failed
                    self?.statusText = "保存失败"
                }
            }
        }
    }
}

private let backgroundTop = Color(red: 16 / 255, green: 31 / 255, blue: 46 / 255)
private let backgroundBottom = Color(red: 14 / 255, green: 26 / 255, blue: 39 / 255)
private let edgeColor = Color(red: 33 / 255, green: 56 / 255, blue: 79 / 255)
private let ink = Color(red: 233 / 255, green: 241 / 255, blue: 251 / 255)
private let inkDim = Color(red: 147 / 255, green: 168 / 255, blue: 189 / 255)
private let inkFaint = Color(red: 93 / 255, green: 115 / 255, blue: 139 / 255)
private let doneColor = Color(red: 240 / 255, green: 162 / 255, blue: 75 / 255)
private let lookColor = Color(red: 89 / 255, green: 166 / 255, blue: 240 / 255)
private let savedColor = Color(red: 73 / 255, green: 210 / 255, blue: 159 / 255)

private enum JingleVisual {
    // The A-direction reference is a quiet, solid monitoring surface. It is
    // deliberately not translucent: a menu item must remain legible over any
    // wallpaper or application below it.
    static let panelRadius: CGFloat = 18
    static let itemRadius: CGFloat = 11
    static let accent = Color(red: 228 / 255, green: 163 / 255, blue: 59 / 255)
    static let accentDeep = Color(red: 141 / 255, green: 92 / 255, blue: 13 / 255)
    static let danger = Color(red: 185 / 255, green: 101 / 255, blue: 88 / 255)
    static let dangerDeep = Color(red: 142 / 255, green: 68 / 255, blue: 54 / 255)
    static let panelFill = Color(nsColor: NSColor(name: nil) { appearance in
        appearance.bestMatch(from: [.darkAqua, .aqua]) == .darkAqua
            ? NSColor(red: 20 / 255, green: 28 / 255, blue: 37 / 255, alpha: 1)
            : NSColor(red: 249 / 255, green: 250 / 255, blue: 251 / 255, alpha: 1)
    })
    static let panelLine = Color(nsColor: NSColor(name: nil) { appearance in
        appearance.bestMatch(from: [.darkAqua, .aqua]) == .darkAqua
            ? NSColor(calibratedWhite: 1, alpha: 0.18)
            : NSColor(red: 43 / 255, green: 54 / 255, blue: 66 / 255, alpha: 0.20)
    })
    static let itemFill = Color(nsColor: NSColor(name: nil) { appearance in
        appearance.bestMatch(from: [.darkAqua, .aqua]) == .darkAqua
            ? NSColor(red: 35 / 255, green: 43 / 255, blue: 53 / 255, alpha: 1)
            : NSColor(red: 237 / 255, green: 240 / 255, blue: 243 / 255, alpha: 1)
    })
    static let divider = Color(nsColor: NSColor(name: nil) { appearance in
        appearance.bestMatch(from: [.darkAqua, .aqua]) == .darkAqua
            ? NSColor(calibratedWhite: 1, alpha: 0.10)
            : NSColor(red: 43 / 255, green: 54 / 255, blue: 66 / 255, alpha: 0.12)
    })
    static let attentionFill = Color(nsColor: NSColor(name: nil) { appearance in
        appearance.bestMatch(from: [.darkAqua, .aqua]) == .darkAqua
            ? NSColor(red: 62 / 255, green: 49 / 255, blue: 29 / 255, alpha: 1)
            : NSColor(red: 252 / 255, green: 244 / 255, blue: 226 / 255, alpha: 1)
    })
}

private struct JinglePanelSurface: ViewModifier {
    let calling: Bool

    func body(content: Content) -> some View {
        content
            .background(JingleVisual.panelFill)
            .clipShape(RoundedRectangle(cornerRadius: JingleVisual.panelRadius, style: .continuous))
            .overlay {
                RoundedRectangle(cornerRadius: JingleVisual.panelRadius, style: .continuous)
                    .stroke(calling ? JingleVisual.danger.opacity(0.48) : JingleVisual.panelLine, lineWidth: 1)
                    .overlay {
                        RoundedRectangle(cornerRadius: JingleVisual.panelRadius, style: .continuous)
                            .stroke(.white.opacity(0.08), lineWidth: 1)
                            .padding(1)
                    }
            }
            .shadow(color: .black.opacity(calling ? 0.28 : 0.24), radius: calling ? 28 : 18, y: 8)
    }
}

private extension View {
    func jinglePanelSurface(calling: Bool = false) -> some View {
        modifier(JinglePanelSurface(calling: calling))
    }
}

struct BrandMark: View {
    private let heights: [CGFloat] = [5, 12, 8, 15]

    var body: some View {
        HStack(alignment: .bottom, spacing: 2) {
            ForEach(Array(heights.enumerated()), id: \.offset) { index, height in
                Capsule()
                    .fill(index.isMultiple(of: 2) ? doneColor : lookColor)
                    .frame(width: 2.5, height: height)
                    .shadow(color: index.isMultiple(of: 2) ? doneColor.opacity(0.5) : lookColor.opacity(0.5), radius: 3)
            }
        }
        .frame(height: 15)
        .accessibilityHidden(true)
    }
}

struct PulseWave: View {
    let color: Color
    let active: Bool
    private let heights: [CGFloat] = [8, 16, 11, 20, 14, 9]

    var body: some View {
        HStack(alignment: .center, spacing: 2.5) {
            ForEach(Array(heights.enumerated()), id: \.offset) { index, height in
                Capsule()
                    .fill(color.opacity(active ? 1 : 0.38))
                    .frame(width: 3, height: active ? height : max(5, height * 0.45))
                    .animation(
                        active
                            ? .easeInOut(duration: 0.48).repeatForever(autoreverses: true).delay(Double(index) * 0.06)
                            : .easeOut(duration: 0.15),
                        value: active
                    )
            }
        }
        .frame(width: 40, height: 32, alignment: .trailing)
        .accessibilityHidden(true)
    }
}

struct PlayButton: View {
    let color: Color
    let isPlaying: Bool
    let disabled: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            ZStack {
                RoundedRectangle(cornerRadius: 11)
                    .fill(isPlaying ? color.opacity(0.16) : Color.black.opacity(0.18))
                RoundedRectangle(cornerRadius: 11)
                    .stroke(isPlaying ? color : edgeColor, lineWidth: 1)
                Image(systemName: isPlaying ? "pause.fill" : "play.fill")
                    .font(.system(size: 13, weight: .semibold))
                    .foregroundStyle(isPlaying ? color : ink)
            }
            .frame(width: 46, height: 46)
        }
        .buttonStyle(.plain)
        .disabled(disabled)
        .accessibilityLabel(isPlaying ? "停止试听" : "试听音效")
    }
}

struct SoundRow: View {
    let title: String
    let englishTitle: String
    let color: Color
    let options: [SoundOption]
    let menuID: String
    let menuOpensUp: Bool
    @Binding var selection: String
    @Binding var activeMenu: String?
    let isPlaying: Bool
    let disabled: Bool
    let preview: () -> Void

    private var selectedOption: SoundOption? {
        options.first(where: { $0.path == selection }) ?? options.first
    }

    var body: some View {
        HStack(spacing: 12) {
            PlayButton(color: color, isPlaying: isPlaying, disabled: disabled, action: preview)

            VStack(alignment: .leading, spacing: 6) {
                HStack(alignment: .firstTextBaseline, spacing: 7) {
                    Text(title)
                        .font(.system(size: 14, weight: .semibold))
                        .foregroundStyle(ink)
                    Text(englishTitle)
                        .font(.system(size: 10, weight: .medium, design: .monospaced))
                        .foregroundStyle(inkFaint)
                    Spacer(minLength: 4)
                    Text(selectedOption?.mood ?? "")
                        .font(.system(size: 10, weight: .semibold))
                        .foregroundStyle(color)
                        .padding(.horizontal, 7)
                        .padding(.vertical, 2)
                        .background(color.opacity(0.12), in: Capsule())
                }

                Button {
                    activeMenu = activeMenu == menuID ? nil : menuID
                } label: {
                    HStack(spacing: 7) {
                    Text(selectedOption?.name ?? "没有可用音效")
                        .font(.system(size: 11, weight: .medium))
                        .foregroundStyle(ink)
                        .lineLimit(1)
                        .frame(maxWidth: .infinity)

                        Image(systemName: activeMenu == menuID ? "chevron.up" : "chevron.down")
                            .font(.system(size: 9, weight: .bold))
                            .foregroundStyle(color)
                    }
                    .padding(.horizontal, 10)
                    .frame(height: 28)
                }
                .buttonStyle(.plain)
                .frame(maxWidth: 178)
                .background(Color.black.opacity(0.2), in: RoundedRectangle(cornerRadius: 7))
                .overlay {
                    RoundedRectangle(cornerRadius: 7)
                        .stroke(activeMenu == menuID ? color.opacity(0.75) : edgeColor, lineWidth: 1)
                }
                .overlay(alignment: menuOpensUp ? .bottom : .top) {
                    if activeMenu == menuID {
                        SoundDropdown(
                            options: options,
                            selection: $selection,
                            color: color,
                            select: { activeMenu = nil }
                        )
                        .offset(y: menuOpensUp ? -34 : 34)
                        .transition(.opacity.combined(with: .scale(scale: 0.97)))
                        .zIndex(30)
                    }
                }
                .opacity(disabled ? 0.5 : 1)
                .disabled(disabled || options.isEmpty)
                .accessibilityLabel("打开\(title)音效菜单，当前为\(selectedOption?.name ?? "无")，共\(options.count)种")
            }

            PulseWave(color: color, active: isPlaying)
        }
        .padding(.horizontal, 15)
        .frame(height: 88)
        .background(isPlaying ? color.opacity(0.08) : Color.clear)
        .overlay(alignment: .leading) {
            RoundedRectangle(cornerRadius: 2)
                .fill(color)
                .frame(width: 3, height: 64)
                .shadow(color: color.opacity(0.55), radius: 5)
        }
        .zIndex(activeMenu == menuID ? 20 : 0)
    }
}

struct SoundDropdown: View {
    let options: [SoundOption]
    @Binding var selection: String
    let color: Color
    let select: () -> Void

    private var menuHeight: CGFloat {
        min(CGFloat(options.count) * 24 + 10, 202)
    }

    var body: some View {
        ScrollView {
            LazyVStack(spacing: 0) {
                ForEach(options) { option in
                    Button {
                        selection = option.path
                        select()
                    } label: {
                        HStack(spacing: 7) {
                            Image(systemName: "checkmark")
                                .font(.system(size: 9, weight: .bold))
                                .foregroundStyle(color)
                                .frame(width: 12)
                                .opacity(selection == option.path ? 1 : 0)

                            Text(option.name)
                                .font(.system(size: 10.5, weight: .medium))
                                .foregroundStyle(ink)
                                .lineLimit(1)

                            Spacer(minLength: 4)

                            Text(option.mood)
                                .font(.system(size: 9, weight: .semibold))
                                .foregroundStyle(selection == option.path ? color : inkFaint)
                        }
                        .padding(.horizontal, 8)
                        .frame(height: 24)
                        .contentShape(Rectangle())
                        .background(
                            selection == option.path
                                ? color.opacity(0.12)
                                : Color.clear
                        )
                    }
                    .buttonStyle(.plain)
                }
            }
            .padding(.vertical, 5)
        }
        .scrollIndicators(.hidden)
        .frame(width: 222, height: menuHeight)
        .background(backgroundTop.opacity(0.98), in: RoundedRectangle(cornerRadius: 9))
        .overlay {
            RoundedRectangle(cornerRadius: 9)
                .stroke(edgeColor, lineWidth: 1)
        }
        .shadow(color: Color.black.opacity(0.45), radius: 14, y: 6)
    }
}

struct ChoiceDropdown: View {
    let options: [ChoiceOption]
    @Binding var selection: String
    let color: Color
    let width: CGFloat
    let select: () -> Void

    private var menuHeight: CGFloat {
        min(CGFloat(options.count) * 27 + 10, 160)
    }

    var body: some View {
        VStack(spacing: 0) {
            ForEach(options) { option in
                Button {
                    selection = option.id
                    select()
                } label: {
                    HStack(spacing: 7) {
                        Image(systemName: "checkmark")
                            .font(.system(size: 9, weight: .bold))
                            .foregroundStyle(color)
                            .frame(width: 12)
                            .opacity(selection == option.id ? 1 : 0)
                        Text(option.name)
                            .font(.system(size: 10.5, weight: .medium))
                            .foregroundStyle(ink)
                            .lineLimit(1)
                        Spacer(minLength: 4)
                        Text(option.mood)
                            .font(.system(size: 9, weight: .semibold))
                            .foregroundStyle(selection == option.id ? color : inkFaint)
                    }
                    .padding(.horizontal, 8)
                    .frame(height: 27)
                    .contentShape(Rectangle())
                    .background(selection == option.id ? color.opacity(0.12) : Color.clear)
                }
                .buttonStyle(.plain)
            }
        }
        .padding(.vertical, 5)
        .frame(width: width, height: menuHeight, alignment: .top)
        .background(backgroundTop.opacity(0.99), in: RoundedRectangle(cornerRadius: 9))
        .overlay {
            RoundedRectangle(cornerRadius: 9)
                .stroke(edgeColor, lineWidth: 1)
        }
        .shadow(color: Color.black.opacity(0.45), radius: 14, y: 6)
    }
}

struct CompactChoiceRow: View {
    let label: String
    let menuID: String
    let options: [ChoiceOption]
    @Binding var selection: String
    @Binding var activeMenu: String?
    let disabled: Bool

    private var selectedOption: ChoiceOption? {
        options.first(where: { $0.id == selection }) ?? options.first
    }

    var body: some View {
        HStack(spacing: 8) {
            Text(label)
                .font(.system(size: 9.5, weight: .semibold, design: .monospaced))
                .tracking(0.5)
                .foregroundStyle(inkFaint)
                .frame(width: 38, alignment: .leading)

            Button {
                activeMenu = activeMenu == menuID ? nil : menuID
            } label: {
                HStack(spacing: 6) {
                    Text(selectedOption?.name ?? "没有可用选项")
                        .font(.system(size: 10.5, weight: .medium))
                        .foregroundStyle(ink)
                        .lineLimit(1)
                    Spacer(minLength: 4)
                    Text(selectedOption?.mood ?? "")
                        .font(.system(size: 9, weight: .semibold))
                        .foregroundStyle(lookColor)
                    Image(systemName: activeMenu == menuID ? "chevron.up" : "chevron.down")
                        .font(.system(size: 8.5, weight: .bold))
                        .foregroundStyle(lookColor)
                }
                .padding(.horizontal, 9)
                .frame(height: 27)
            }
            .buttonStyle(.plain)
            .frame(maxWidth: .infinity)
            .background(Color.black.opacity(0.2), in: RoundedRectangle(cornerRadius: 7))
            .overlay {
                RoundedRectangle(cornerRadius: 7)
                    .stroke(activeMenu == menuID ? lookColor.opacity(0.75) : edgeColor, lineWidth: 1)
            }
            .overlay(alignment: .bottomTrailing) {
                if activeMenu == menuID {
                    ChoiceDropdown(
                        options: options,
                        selection: $selection,
                        color: lookColor,
                        width: 262,
                        select: { activeMenu = nil }
                    )
                    .offset(y: -31)
                    .transition(.opacity.combined(with: .scale(scale: 0.97)))
                    .zIndex(50)
                }
            }
            .disabled(disabled || options.isEmpty)
        }
        .zIndex(activeMenu == menuID ? 50 : 0)
    }
}

struct SpeechSettingsRow: View {
    @Binding var enabled: Bool
    let contentOptions: [ChoiceOption]
    let voiceOptions: [ChoiceOption]
    @Binding var contentSelection: String
    @Binding var voiceSelection: String
    @Binding var activeMenu: String?
    let isPlaying: Bool
    let disabled: Bool
    let preview: () -> Void

    var body: some View {
        VStack(spacing: 5) {
            HStack(spacing: 11) {
                Image(systemName: "quote.bubble.fill")
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundStyle(lookColor)
                    .frame(width: 26)

                VStack(alignment: .leading, spacing: 2) {
                    Text("语音播报")
                        .font(.system(size: 12, weight: .semibold))
                        .foregroundStyle(ink)
                    Text("仅主任务 · 本机增强语音 · 自动缓存")
                        .font(.system(size: 9.5, weight: .medium))
                        .foregroundStyle(inkFaint)
                }

                Spacer()

                Button(action: preview) {
                    Image(systemName: isPlaying ? "waveform" : "speaker.wave.2.fill")
                        .font(.system(size: 12, weight: .semibold))
                        .foregroundStyle(enabled ? lookColor : inkFaint)
                        .frame(width: 28, height: 27)
                        .background(Color.black.opacity(0.18), in: RoundedRectangle(cornerRadius: 7))
                        .overlay {
                            RoundedRectangle(cornerRadius: 7)
                                .stroke(edgeColor, lineWidth: 1)
                        }
                }
                .buttonStyle(.plain)
                .disabled(disabled || !enabled)
                .accessibilityLabel("单独试听语音播报")

                Toggle("", isOn: $enabled)
                    .labelsHidden()
                    .toggleStyle(.switch)
                    .controlSize(.mini)
                    .tint(lookColor)
                    .disabled(disabled)
                    .accessibilityLabel("启用语音播报")
            }
            .frame(height: 38)

            CompactChoiceRow(
                label: "内容",
                menuID: "speech-content",
                options: contentOptions,
                selection: $contentSelection,
                activeMenu: $activeMenu,
                disabled: disabled || !enabled
            )

            CompactChoiceRow(
                label: "音色",
                menuID: "voice-profile",
                options: voiceOptions,
                selection: $voiceSelection,
                activeMenu: $activeMenu,
                disabled: disabled || !enabled
            )
        }
        .padding(.horizontal, 15)
        .padding(.vertical, 7)
        .frame(height: 112)
        .background(Color.black.opacity(0.08))
        .zIndex(activeMenu?.hasPrefix("speech-") == true || activeMenu == "voice-profile" ? 40 : 0)
    }
}

struct ContentView: View {
    @StateObject private var model = SettingsModel()
    @State private var activeMenu: String?

    private var successSelection: Binding<String> {
        Binding(
            get: { model.successSound },
            set: { model.successSound = $0; model.markChanged() }
        )
    }

    private var attentionSelection: Binding<String> {
        Binding(
            get: { model.attentionSound },
            set: { model.attentionSound = $0; model.markChanged() }
        )
    }

    private var volumeSelection: Binding<Double> {
        Binding(
            get: { model.effectVolume },
            set: { model.effectVolume = $0; model.markChanged() }
        )
    }

    private var speechSelection: Binding<Bool> {
        Binding(
            get: { model.speechEnabled },
            set: { model.speechEnabled = $0; model.markChanged() }
        )
    }

    private var speechContentSelection: Binding<String> {
        Binding(
            get: { model.speechContent },
            set: { model.speechContent = $0; model.markChanged() }
        )
    }

    private var voiceProfileSelection: Binding<String> {
        Binding(
            get: { model.voiceProfile },
            set: { model.voiceProfile = $0; model.markChanged() }
        )
    }

    private var statusColor: Color {
        switch model.state {
        case .saved: return savedColor
        case .dirty: return doneColor
        case .failed: return Color(red: 235 / 255, green: 105 / 255, blue: 100 / 255)
        case .loading, .ready: return inkFaint
        }
    }

    var body: some View {
        VStack(spacing: 0) {
            HStack(spacing: 9) {
                BrandMark()
                Text("CODEX JINGLE")
                    .font(.system(size: 11, weight: .bold, design: .monospaced))
                    .tracking(1.7)
                    .foregroundStyle(ink)
                Spacer()
                HStack(spacing: 6) {
                    Circle()
                        .fill(statusColor)
                        .frame(width: 7, height: 7)
                        .shadow(color: statusColor.opacity(model.state == .ready ? 0 : 0.65), radius: 3)
                    Text(model.statusText)
                        .font(.system(size: 10, weight: .medium, design: .monospaced))
                        .foregroundStyle(model.state == .ready ? inkFaint : statusColor)
                }
                .accessibilityElement(children: .combine)
            }
            .padding(.horizontal, 15)
            .frame(height: 49)

            Divider().overlay(Color.white.opacity(0.05))

            SoundRow(
                title: "完成",
                englishTitle: "ALL GOOD",
                color: doneColor,
                options: model.successSounds,
                menuID: "success",
                menuOpensUp: false,
                selection: successSelection,
                activeMenu: $activeMenu,
                isPlaying: model.previewing == "success",
                disabled: model.isBusy,
                preview: { model.previewSound("success") }
            )

            Divider().overlay(Color.white.opacity(0.05))

            SoundRow(
                title: "需确认",
                englishTitle: "CHECK",
                color: lookColor,
                options: model.attentionSounds,
                menuID: "attention",
                menuOpensUp: true,
                selection: attentionSelection,
                activeMenu: $activeMenu,
                isPlaying: model.previewing == "attention",
                disabled: model.isBusy,
                preview: { model.previewSound("attention") }
            )

            Divider().overlay(Color.white.opacity(0.05))

            SpeechSettingsRow(
                enabled: speechSelection,
                contentOptions: model.speechContentOptions,
                voiceOptions: model.voiceOptions,
                contentSelection: speechContentSelection,
                voiceSelection: voiceProfileSelection,
                activeMenu: $activeMenu,
                isPlaying: model.previewing == "speech",
                disabled: model.isBusy,
                preview: { model.previewSpeech() }
            )

            Divider().overlay(Color.white.opacity(0.05))

            HStack(spacing: 10) {
                Text("VOL")
                    .font(.system(size: 10, weight: .medium, design: .monospaced))
                    .tracking(0.8)
                    .foregroundStyle(inkFaint)
                Slider(value: volumeSelection, in: 0...100, step: 1)
                    .controlSize(.small)
                    .tint(inkDim)
                    .disabled(model.isBusy)
                Button(model.isSaving ? "保存中" : "保存") {
                    model.save()
                }
                .font(.system(size: 12, weight: .semibold))
                .foregroundStyle(model.isDirty ? Color(red: 10 / 255, green: 17 / 255, blue: 25 / 255) : inkDim)
                .padding(.horizontal, 14)
                .frame(height: 28)
                .background(model.isDirty ? ink : Color.clear)
                .clipShape(RoundedRectangle(cornerRadius: 7, style: .continuous))
                .overlay {
                    RoundedRectangle(cornerRadius: 7, style: .continuous)
                        .stroke(model.isDirty ? Color.clear : edgeColor, lineWidth: 1)
                }
                .buttonStyle(.plain)
                .opacity(model.isBusy ? 0.55 : 1)
                .allowsHitTesting(!model.isBusy && model.isDirty)
            }
            .padding(.horizontal, 15)
            .frame(height: 62)
            .background(Color.black.opacity(0.12))
        }
        .frame(width: 344, height: 403)
        .background(
            LinearGradient(
                colors: [backgroundTop, backgroundBottom],
                startPoint: .top,
                endPoint: .bottom
            )
        )
        .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
        .overlay {
            RoundedRectangle(cornerRadius: 14, style: .continuous)
                .stroke(edgeColor, lineWidth: 1)
        }
        .preferredColorScheme(.dark)
    }
}

struct WorkUnit: Codable, Identifiable {
    let id: String
    let provider: String
    let sessionID: String
    let cwd: String
    let state: String
    let startedAt: Double
    let endedAt: Double?
    let transcriptPath: String?
    let summary: String?
    let tokenAccounting: TokenAccounting?
    let sessionLocator: SessionLocator?
    let seenAt: Double?
    let snoozedUntil: Double?
    let supersededAt: Double?
    let attentionSuppressed: Bool?
    let needsAttentionFlag: Bool?

    enum CodingKeys: String, CodingKey {
        case id, provider, cwd, state, summary
        case sessionID = "session_id"
        case startedAt = "started_at"
        case endedAt = "ended_at"
        case tokenAccounting = "token_accounting"
        case sessionLocator = "session_locator"
        case seenAt = "seen_at"
        case snoozedUntil = "snoozed_until"
        case supersededAt = "superseded_at"
        case attentionSuppressed = "attention_suppressed"
        case needsAttentionFlag = "needs_attention"
        case transcriptPath = "transcript_path"
    }

    var elapsed: String {
        let seconds = max(0, Int((endedAt ?? Date().timeIntervalSince1970) - startedAt))
        if seconds < 60 { return "\(seconds) 秒" }
        if seconds < 3_600 { return "\(seconds / 60) 分钟" }
        return "\(seconds / 3_600) 小时 \((seconds % 3_600) / 60) 分"
    }

    var needsAttention: Bool {
        // Old ledger rows predate unified attention. Do not wake historical
        // completions merely because the app was upgraded.
        guard let needsAttentionFlag else { return false }
        return needsAttentionFlag
    }
    var attentionPrefix: String { state == "blocked" ? "需要决定：" : "已完成：" }
    var startedLabel: String {
        let formatter = DateFormatter()
        formatter.dateFormat = "HH:mm"
        return "\(formatter.string(from: Date(timeIntervalSince1970: startedAt))) 开始"
    }
    var tokenLabel: String {
        guard let amount = tokenAccounting?.totalTokens else { return "token 不可用" }
        return amount >= 1_000 ? String(format: "+%.1fk", Double(amount) / 1_000) : "+\(amount) token"
    }
    var settlementLabel: String { "本轮 \(elapsed) · \(tokenLabel)" }
    var waitingLabel: String {
        guard let endedAt else { return "" }
        let seconds = max(0, Int(Date().timeIntervalSince1970 - endedAt))
        if seconds < 60 { return "等了 \(seconds) 秒" }
        if seconds < 3_600 { return "等了 \(seconds / 60) 分钟" }
        return "等了 \(seconds / 3_600) 小时"
    }
}

struct SessionLocator: Codable {
    let terminalApp: String?
    let terminalTTY: String?
    let terminalSessionID: String?
    let parentPID: Int?

    enum CodingKeys: String, CodingKey {
        case terminalApp = "terminal_app"
        case terminalTTY = "terminal_tty"
        case terminalSessionID = "terminal_session_id"
        case parentPID = "parent_pid"
    }
}

struct TokenAccounting: Codable {
    let status: String
    let totalTokens: Int?
    enum CodingKeys: String, CodingKey { case status; case totalTokens = "total_tokens" }
}

struct ResumeResult: Codable {
    let status: String
    let message: String
}

struct WorkUnitStore: Codable { let units: [String: WorkUnit] }

struct CodexThreadActivity: Decodable {
    let updatedAt: Double
    let archived: Bool
    let cwd: String
    let displayName: String?
    let lastTerminalAt: Double?

    enum CodingKeys: String, CodingKey {
        case updatedAt = "updated_at"
        case archived, cwd
        case displayName = "display_name"
        case lastTerminalAt = "last_terminal_at"
    }
}

struct CodexThreadActivityStore: Decodable { let sessions: [String: CodexThreadActivity] }

struct ProjectAlias: Decodable {
    let provider: String?
    let prefix: String
}

struct ProjectRule: Decodable {
    let projectID: String
    let name: String
    let color: String?
    let aliases: [ProjectAlias]

    enum CodingKeys: String, CodingKey { case projectID = "project_id"; case name, color, aliases, prefix }

    init(from decoder: Decoder) throws {
        let values = try decoder.container(keyedBy: CodingKeys.self)
        let legacyPrefix = try values.decodeIfPresent(String.self, forKey: .prefix)
        projectID = try values.decodeIfPresent(String.self, forKey: .projectID) ?? legacyPrefix ?? "unmapped"
        name = try values.decode(String.self, forKey: .name)
        color = try values.decodeIfPresent(String.self, forKey: .color)
        aliases = try values.decodeIfPresent([ProjectAlias].self, forKey: .aliases) ?? legacyPrefix.map { [ProjectAlias(provider: nil, prefix: $0)] } ?? []
    }
}

struct ProjectConfig: Decodable {
    let projects: [ProjectRule]
    let ignoredPrefixes: [String]

    enum CodingKeys: String, CodingKey { case projects; case ignoredPrefixes = "ignored_prefixes" }

    init(from decoder: Decoder) throws {
        let values = try decoder.container(keyedBy: CodingKeys.self)
        projects = try values.decodeIfPresent([ProjectRule].self, forKey: .projects) ?? []
        ignoredPrefixes = try values.decodeIfPresent([String].self, forKey: .ignoredPrefixes) ?? []
    }
}

struct ProjectIdentity {
    let id: String
    let name: String
    let color: Color
    let isMapped: Bool
}

struct AttentionGroup: Identifiable {
    let id: String
    let identity: ProjectIdentity
    let units: [WorkUnit]

    var hasBlocked: Bool { units.contains { $0.state == "blocked" } }
    // A smaller terminal timestamp means Park has been waiting longer.
    var oldestWaitingAt: Double { units.compactMap(\.endedAt).min() ?? .greatestFiniteMagnitude }
}

private func projectColor(_ raw: String?) -> Color {
    switch raw?.lowercased() {
    case "orange": return doneColor
    case "green": return savedColor
    case "red": return Color(red: 0.8, green: 0.36, blue: 0.3)
    default: return lookColor
    }
}

final class JingleModel: ObservableObject {
    @Published var units: [WorkUnit] = []
    @Published var actionMessage: String?
    @Published var routingUnitID: String?

    private let statePath: URL
    private let projectsPath: URL
    private let activityPath: String
    private var projects: [ProjectRule] = []
    private var ignoredPrefixes: [String] = []
    private var threadActivity: [String: CodexThreadActivity] = [:]
    private var activityResolvedSessionIDs: Set<String> = []
    private var activityRefreshInFlight = false

    init() {
        let environment = ProcessInfo.processInfo.environment
        statePath = URL(fileURLWithPath: environment["JINGLE_STATE_PATH"] ?? FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent(".codex/jingle/work-units.json").path)
        projectsPath = URL(fileURLWithPath: environment["JINGLE_PROJECTS_PATH"] ?? FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent(".codex/jingle/projects.json").path)
        activityPath = environment["JINGLE_ACTIVITY_HELPER_PATH"] ?? FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent(".codex/hooks/jingle_codex_activity.py").path
        reload()
        Timer.scheduledTimer(withTimeInterval: 2, repeats: true) { [weak self] _ in self?.reload() }
    }

    func reload() {
        let loadedUnits = (try? Data(contentsOf: statePath)).flatMap { try? JSONDecoder().decode(WorkUnitStore.self, from: $0) }
        let loadedProjects = (try? Data(contentsOf: projectsPath)).flatMap { try? JSONDecoder().decode(ProjectConfig.self, from: $0) }
        DispatchQueue.main.async {
            self.units = loadedUnits.map { Array($0.units.values) } ?? []
            self.projects = loadedProjects?.projects ?? []
            self.ignoredPrefixes = loadedProjects?.ignoredPrefixes ?? []
            self.refreshCodexActivity()
        }
    }

    private func refreshCodexActivity() {
        guard !activityRefreshInFlight else { return }
        let sessionIDs = Array(Set(trackedCodexUnits.map(\.sessionID).filter { !$0.isEmpty })).sorted()
        guard !sessionIDs.isEmpty else {
            threadActivity = [:]
            return
        }
        activityRefreshInFlight = true
        DispatchQueue.global(qos: .utility).async { [weak self] in
            guard let self else { return }
            defer { DispatchQueue.main.async { self.activityRefreshInFlight = false } }
            do {
                var transcripts: [String: String] = [:]
                for unit in self.trackedCodexUnits {
                    guard !unit.sessionID.isEmpty, let transcriptPath = unit.transcriptPath, !transcriptPath.isEmpty else { continue }
                    transcripts[unit.sessionID] = transcriptPath
                }
                let transcriptJSON = try String(data: JSONEncoder().encode(transcripts), encoding: .utf8) ?? "{}"
                let arguments = sessionIDs.flatMap { ["--session-id", $0] } + ["--transcripts-json", transcriptJSON]
                let data = try runLocalPython(script: self.activityPath, arguments: arguments)
                let store = try JSONDecoder().decode(CodexThreadActivityStore.self, from: data)
                DispatchQueue.main.async {
                    self.threadActivity = store.sessions
                    self.activityResolvedSessionIDs = Set(sessionIDs)
                }
            } catch {
                // A missing or busy local Codex database is not evidence that a
                // task is active. Keep the prior snapshot until the next probe.
            }
        }
    }

    private func activity(for unit: WorkUnit) -> CodexThreadActivity? {
        threadActivity[unit.sessionID]
    }

    private func hasLiveCodexThread(_ unit: WorkUnit) -> Bool {
        guard let activity = activity(for: unit), !activity.archived else { return false }
        return (activity.lastTerminalAt ?? 0) < unit.startedAt
    }

    private func sessionHasLiveCodexThread(_ sessionID: String) -> Bool {
        trackedCodexUnits.contains { $0.sessionID == sessionID && $0.state == "running" && hasLiveCodexThread($0) }
    }

    private func terminalWasSupersededBySessionCompletion(_ unit: WorkUnit) -> Bool {
        guard let terminalAt = activity(for: unit)?.lastTerminalAt else { return false }
        return terminalAt >= (unit.endedAt ?? unit.startedAt)
    }

    private func activityIsResolved(for unit: WorkUnit) -> Bool {
        activityResolvedSessionIDs.contains(unit.sessionID)
    }

    private func isIgnored(_ unit: WorkUnit) -> Bool {
        let cwd = URL(fileURLWithPath: unit.cwd).standardized.path
        return ignoredPrefixes.contains { rawPrefix in
            let prefix = URL(fileURLWithPath: rawPrefix).standardized.path
            return cwd == prefix || cwd.hasPrefix(prefix.hasSuffix("/") ? prefix : prefix + "/")
        }
    }

    func identity(for unit: WorkUnit) -> ProjectIdentity {
        let normalized = URL(fileURLWithPath: unit.cwd).standardized.path
        if let rule = projects
            .filter({ rule in rule.aliases.contains { alias in
                let prefix = URL(fileURLWithPath: alias.prefix).standardized.path
                return (alias.provider == nil || alias.provider == unit.provider)
                    && (normalized == prefix || normalized.hasPrefix(prefix.hasSuffix("/") ? prefix : prefix + "/"))
            } })
            .max(by: { left, right in
                (left.aliases.map { $0.prefix.count }.max() ?? 0) < (right.aliases.map { $0.prefix.count }.max() ?? 0)
            }) {
            return ProjectIdentity(id: rule.projectID, name: rule.name, color: projectColor(rule.color), isMapped: true)
        }
        if let label = activity(for: unit)?.displayName, !label.isEmpty {
            // Session-index names are intentionally read-only and short. They
            // disambiguate shared directories without exposing raw DB titles.
            return ProjectIdentity(id: "thread:\(unit.sessionID)", name: label, color: lookColor, isMapped: false)
        }
        let name = URL(fileURLWithPath: unit.cwd).lastPathComponent
        // An unmapped cwd deliberately keeps its full normalized path as the
        // identity. Equal basenames must not silently merge across projects.
        return ProjectIdentity(id: "unmapped:\(normalized)", name: name.isEmpty ? "未命名项目" : name, color: lookColor, isMapped: false)
    }

    // The ledger is append-only and may contain history from providers Jingle
    // no longer observes. Projection is Codex-only rather than deleting that
    // history, so an old Claude row can never affect the menu bar.
    private var codexUnits: [WorkUnit] { units.filter { $0.provider == "codex" && !isIgnored($0) } }

    // The menu is a project navigator, not a ledger browser. An unconfigured
    // cwd remains in the append-only ledger but cannot create a count, card,
    // token contribution, or activity probe in the user-facing projection.
    private var trackedCodexUnits: [WorkUnit] { codexUnits.filter { identity(for: $0).isMapped } }

    // A project can only surface one state. A live session wins over a stale
    // terminal result from another session in the same project, while normal
    // and blocked units outside the explicit project map remain ledger-only.
    private var visible: [WorkUnit] {
        trackedCodexUnits.filter {
            $0.needsAttention && $0.seenAt == nil && $0.supersededAt == nil
                && activityIsResolved(for: $0) && !sessionHasLiveCodexThread($0.sessionID)
                && !terminalWasSupersededBySessionCompletion($0)
                && !liveProjectIDs.contains(identity(for: $0).id)
        }
    }
    private var currentBySession: [WorkUnit] {
        Dictionary(grouping: visible, by: { "\($0.provider):\($0.sessionID)" })
            .compactMap { $0.value.max { $0.startedAt < $1.startedAt } }
    }
    private func preferredUnit(in items: [WorkUnit]) -> WorkUnit? {
        items.sorted {
            let leftBlocked = $0.state == "blocked"
            let rightBlocked = $1.state == "blocked"
            if leftBlocked != rightBlocked { return leftBlocked }
            let leftAt = $0.endedAt ?? $0.startedAt
            let rightAt = $1.endedAt ?? $1.startedAt
            return leftAt == rightAt ? $0.id > $1.id : leftAt > rightAt
        }.first
    }
    var attentionGroups: [AttentionGroup] {
        Dictionary(grouping: currentBySession, by: { identity(for: $0).id })
            .compactMap { groupID, items in
                guard let preferred = preferredUnit(in: items) else { return nil }
                return AttentionGroup(
                    id: groupID,
                    identity: identity(for: preferred),
                    units: [preferred]
                )
            }
            .sorted { left, right in
                if left.hasBlocked != right.hasBlocked { return left.hasBlocked }
                if left.oldestWaitingAt != right.oldestWaitingAt { return left.oldestWaitingAt < right.oldestWaitingAt }
                return left.id < right.id
            }
    }
    var runningUnits: [WorkUnit] {
        // A project is a destination, not a chronological work log. Its latest
        // live session replaces an older concurrent session in this surface.
        Dictionary(grouping: trackedCodexUnits.filter { $0.state == "running" && hasLiveCodexThread($0) }, by: { identity(for: $0).id })
            .compactMap { $0.value.max { left, right in
                let leftUpdated = activity(for: left)?.updatedAt ?? left.startedAt
                let rightUpdated = activity(for: right)?.updatedAt ?? right.startedAt
                return leftUpdated < rightUpdated
            } }
            .sorted { left, right in
                let leftUpdated = activity(for: left)?.updatedAt ?? 0
                let rightUpdated = activity(for: right)?.updatedAt ?? 0
                return leftUpdated == rightUpdated ? left.id < right.id : leftUpdated > rightUpdated
            }
    }
    private var liveProjectIDs: Set<String> { Set(runningUnits.map { identity(for: $0).id }) }
    var blocked: [WorkUnit] {
        attentionGroups.flatMap(\.units)
            .filter { $0.state == "blocked" }
            .sorted { ($0.endedAt ?? 0) < ($1.endedAt ?? 0) }
    }
    var callableBlocked: [WorkUnit] { blocked.filter { ($0.snoozedUntil ?? 0) <= Date().timeIntervalSince1970 } }
    var pendingCount: Int { attentionGroups.count }
    var hasSettlementContent: Bool { pendingCount > 0 || !runningUnits.isEmpty }

    // Token accounting is intentionally terminal-only. The headline therefore
    // sums only recorded Work Units completed today, never a live estimate.
    var todayTokenTotal: Int? {
        let startOfToday = Calendar.current.startOfDay(for: Date()).timeIntervalSince1970
        let recorded = trackedCodexUnits.compactMap { unit -> Int? in
            guard let endedAt = unit.endedAt,
                  endedAt >= startOfToday,
                  let total = unit.tokenAccounting?.totalTokens else { return nil }
            return total
        }
        guard !recorded.isEmpty else { return nil }
        return recorded.reduce(0, +)
    }

    var featuredAttentionGroup: AttentionGroup? { attentionGroups.first }

    func acknowledge(_ unit: WorkUnit) { runControl(["--acknowledge", unit.id], success: "已看") }
    func snooze(_ unit: WorkUnit) { runControl(["--snooze", unit.id, "--seconds", "600"], success: "10 分钟后再喊你") }

    func resume(_ unit: WorkUnit) {
        guard !unit.sessionID.isEmpty else { actionMessage = "无法回到会话：该 Work Unit 没有 session id。"; return }
        routingUnitID = unit.id
        let resumePath = FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent(".codex/hooks/jingle_resume.py").path
        DispatchQueue.global(qos: .userInitiated).async {
            do {
                let locator = try String(data: JSONEncoder().encode(unit.sessionLocator), encoding: .utf8) ?? "{}"
                let data = try runLocalPython(script: resumePath, arguments: ["--provider", unit.provider, "--session-id", unit.sessionID, "--cwd", unit.cwd, "--locator-json", locator])
                let result = try JSONDecoder().decode(ResumeResult.self, from: data)
                DispatchQueue.main.async { self.routingUnitID = nil; self.actionMessage = result.message }
            } catch {
                DispatchQueue.main.async {
                    self.routingUnitID = nil
                    self.actionMessage = "无法回到会话：\(error.localizedDescription)"
                }
            }
        }
    }

    private func runControl(_ arguments: [String], success: String) {
        let controlPath = FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent(".codex/hooks/jingle_control.py").path
        DispatchQueue.global(qos: .userInitiated).async {
            do {
                _ = try runLocalPython(script: controlPath, arguments: arguments)
                DispatchQueue.main.async { self.actionMessage = success; self.reload() }
            } catch {
                DispatchQueue.main.async { self.actionMessage = "操作失败：\(error.localizedDescription)" }
            }
        }
    }
}

@discardableResult
func runLocalPython(script: String, arguments: [String]) throws -> Data {
    let process = Process()
    process.executableURL = URL(fileURLWithPath: pythonPath)
    process.arguments = [script] + arguments
    let output = Pipe()
    let errors = Pipe()
    process.standardOutput = output
    process.standardError = errors
    try process.run()
    process.waitUntilExit()
    let data = output.fileHandleForReading.readDataToEndOfFile()
    guard process.terminationStatus == 0 else {
        let error = String(data: errors.fileHandleForReading.readDataToEndOfFile(), encoding: .utf8) ?? "本地操作失败"
        throw BridgeError.failed(error.trimmingCharacters(in: .whitespacesAndNewlines))
    }
    return data
}

struct DecisionDetails: View {
    let unit: WorkUnit
    let identity: ProjectIdentity

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(alignment: .center, spacing: 11) {
                ProjectPersona(identity: identity, compact: false)
                Text(identity.name)
                    .font(.system(size: 14, weight: .semibold))
                Spacer(minLength: 0)
            }
            Text("\(unit.attentionPrefix)\(unit.summary ?? "等待你的处理")")
                .font(.system(size: 13.5, weight: .regular))
                .lineLimit(3)
                .fixedSize(horizontal: false, vertical: true)
            Text("\(unit.startedLabel) · 本轮 \(unit.elapsed)")
                .font(.system(size: 11))
                .foregroundStyle(.secondary)
        }
    }
}

private struct ProjectPersona: View {
    let identity: ProjectIdentity
    let compact: Bool

    // Mockup persona measurements: 38px normally, 30px in compact rows.
    private var size: CGFloat { compact ? 30 : 38 }
    private var radius: CGFloat { compact ? 10 : 12 }
    private var initial: String {
        let trimmed = identity.name.trimmingCharacters(in: .whitespacesAndNewlines)
        return trimmed.first.map(String.init) ?? "J"
    }

    var body: some View {
        Text(initial)
            .font(.system(size: compact ? 12 : 15, weight: .bold))
            .foregroundStyle(.white)
            .frame(width: size, height: size)
            .background(
                // SwiftUI's diagonal endpoints are the native equivalent of
                // the mockup's measured 150-degree highlight-to-dark fill.
                LinearGradient(
                    colors: [identity.color.opacity(0.78), identity.color.opacity(0.98), .black.opacity(0.40)],
                    startPoint: UnitPoint(x: 0.15, y: 0),
                    endPoint: UnitPoint(x: 0.85, y: 1)
                ),
                in: RoundedRectangle(cornerRadius: radius, style: .continuous)
            )
            .overlay {
                RoundedRectangle(cornerRadius: radius, style: .continuous)
                    .stroke(JingleVisual.panelLine, lineWidth: 1)
            }
            .accessibilityLabel(identity.name)
    }
}

struct QueueItem: View {
    let unit: WorkUnit
    @ObservedObject var model: JingleModel
    let open: (WorkUnit) -> Void
    let acknowledge: (WorkUnit) -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            DecisionDetails(unit: unit, identity: model.identity(for: unit))
            HStack(alignment: .firstTextBaseline) {
                Text(unit.waitingLabel)
                    .font(.system(size: 11, weight: .semibold, design: .monospaced))
                    .foregroundStyle(unit.state == "blocked" ? JingleVisual.dangerDeep : .secondary)
                Spacer()
                Text(unit.settlementLabel)
                    .font(.system(size: 10.5, weight: .regular, design: .monospaced))
                    .foregroundStyle(.secondary)
            }
            HStack(spacing: 8) {
                Button("已处理") { acknowledge(unit) }
                    .buttonStyle(.bordered)
                    .controlSize(.small)
                Spacer()
                Button(model.routingUnitID == unit.id ? "正在跳转" : "回到会话") { open(unit) }
                    .buttonStyle(.borderedProminent)
                    .controlSize(.small)
                    .disabled(model.routingUnitID != nil)
            }
        }
        .padding(.top, 4)
    }
}

struct AttentionGroupItem: View {
    let group: AttentionGroup
    @ObservedObject var model: JingleModel
    let open: (WorkUnit) -> Void
    let acknowledge: (WorkUnit) -> Void
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            ForEach(group.units) { unit in
                QueueItem(unit: unit, model: model, open: open, acknowledge: acknowledge)
            }
        }
        .padding(14)
        .background(JingleVisual.attentionFill, in: RoundedRectangle(cornerRadius: JingleVisual.itemRadius, style: .continuous))
        .overlay {
            RoundedRectangle(cornerRadius: JingleVisual.itemRadius, style: .continuous)
                .stroke(JingleVisual.accent.opacity(0.46), lineWidth: 1)
        }
    }
}

private struct RunningItem: View {
    let unit: WorkUnit
    let identity: ProjectIdentity

    var body: some View {
        HStack(spacing: 11) {
            ProjectPersona(identity: identity, compact: true)
            VStack(alignment: .leading, spacing: 3) {
                Text(identity.name).font(.system(size: 13, weight: .semibold))
                Text("工作中  ·  \(unit.startedLabel)")
                    .font(.system(size: 10.5, design: .monospaced))
                    .foregroundStyle(.secondary)
            }
            Spacer()
            VStack(alignment: .trailing, spacing: 3) {
                Text(unit.elapsed)
                    .font(.system(size: 12, weight: .semibold, design: .monospaced))
                Text("进行中")
                    .font(.system(size: 9.5, design: .monospaced))
                    .foregroundStyle(JingleVisual.accent)
            }
        }
        .padding(.vertical, 9)
    }
}

private struct MetricBlock: View {
    let value: String
    let label: String

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(value)
                .font(.system(size: 22, weight: .bold, design: .monospaced))
                .foregroundStyle(.primary)
            Text(label)
                .font(.system(size: 10.5, weight: .medium))
                .foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(.vertical, 12)
    }
}

struct SettlementView: View {
    @ObservedObject var model: JingleModel
    let open: (WorkUnit) -> Void
    let acknowledge: (WorkUnit) -> Void
    let panelHeight: CGFloat

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 0) {
                header
                metrics
                if !model.runningUnits.isEmpty { running }
                if let group = model.featuredAttentionGroup { attention(group) }
                if model.pendingCount == 0 && model.runningUnits.isEmpty {
                    Text("现在没有待处理任务").font(.subheadline).foregroundStyle(.secondary).padding(.vertical, 30).frame(maxWidth: .infinity)
                }
                if let message = model.actionMessage {
                    Divider().overlay(JingleVisual.divider)
                    Text(message).font(.caption).foregroundStyle(.secondary).padding(.top, 10)
                }
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 14)
        }
        .frame(width: 380, height: panelHeight)
        .jinglePanelSurface()
    }

    private var header: some View {
        HStack(spacing: 8) {
            BrandMark()
            Text("JINGLE")
                .font(.system(size: 11, weight: .bold, design: .monospaced))
                .tracking(1.2)
            Spacer()
            if model.pendingCount > 0 {
                Text("待检查  \(model.pendingCount)")
                    .font(.system(size: 10.5, weight: .semibold, design: .monospaced))
                    .foregroundStyle(JingleVisual.accent)
            } else {
                Text("监控中")
                    .font(.system(size: 10.5, weight: .medium, design: .monospaced))
                    .foregroundStyle(.secondary)
            }
        }
        .padding(.bottom, 12)
    }

    private var metrics: some View {
        HStack(spacing: 0) {
            MetricBlock(value: "\(model.runningUnits.count)", label: "个任务正在工作")
            if let tokens = model.todayTokenTotal {
                Divider().overlay(JingleVisual.divider).padding(.vertical, 8)
                MetricBlock(value: tokenTotalLabel(tokens), label: "今日已结算 Token")
            }
        }
        .overlay(alignment: .bottom) { Divider().overlay(JingleVisual.divider) }
    }

    private var running: some View {
        VStack(alignment: .leading, spacing: 0) {
            sectionLabel("当前任务", trailing: "耗时")
            ForEach(model.runningUnits) { unit in
                RunningItem(unit: unit, identity: model.identity(for: unit))
                if unit.id != model.runningUnits.last?.id { Divider().overlay(JingleVisual.divider) }
            }
        }
        .padding(.vertical, 10)
    }

    private func attention(_ group: AttentionGroup) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Divider().overlay(JingleVisual.divider)
            sectionLabel("等你检查", trailing: "最高优先级")
                .padding(.top, 8)
            AttentionGroupItem(group: group, model: model, open: open, acknowledge: acknowledge)
        }
        .padding(.bottom, 4)
    }

    private func sectionLabel(_ title: String, trailing: String) -> some View {
        HStack {
            Text(title)
                .font(.system(size: 10.5, weight: .bold, design: .monospaced))
                .foregroundStyle(.secondary)
            Spacer()
            Text(trailing)
                .font(.system(size: 10, design: .monospaced))
                .foregroundStyle(.secondary)
        }
    }

    private func tokenTotalLabel(_ total: Int) -> String {
        total >= 1_000 ? String(format: "%.1fk", Double(total) / 1_000) : "\(total)"
    }
}

struct CallView: View {
    let unit: WorkUnit
    @ObservedObject var model: JingleModel
    let open: (WorkUnit) -> Void
    let snooze: (WorkUnit) -> Void
    let panelHeight: CGFloat

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                Text("需要你决定")
                    .font(.system(size: 15, weight: .semibold))
                    .foregroundStyle(JingleVisual.danger)
                DecisionDetails(unit: unit, identity: model.identity(for: unit))
                HStack(spacing: 8) {
                    Button(model.routingUnitID == unit.id ? "正在打开" : "回到这个会话") { open(unit) }
                        .buttonStyle(.borderedProminent)
                        .disabled(model.routingUnitID != nil)
                    Button("10 分钟后再喊我") { snooze(unit) }.buttonStyle(.bordered)
                }
                if let message = model.actionMessage { Text(message).font(.caption).foregroundStyle(.secondary) }
            }.padding(16)
        }
        .frame(width: 380, height: panelHeight)
        .jinglePanelSurface(calling: true)
    }
}

final class AppDelegate: NSObject, NSApplicationDelegate {
    private let model = JingleModel()
    private var item: NSStatusItem!
    private var panel: NSPanel?
    private var calledUnitIDs: Set<String> = []
    private var callUnitID: String?
    private var frontmostApplicationBeforePanel: pid_t?

    private enum PanelMode {
        case settlement
        case call(WorkUnit)

        var preferredHeight: CGFloat {
            switch self {
            case .settlement: return 448
            case .call: return 280
            }
        }
    }

    func applicationDidFinishLaunching(_ notification: Notification) {
        item = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        item.button?.target = self
        item.button?.action = #selector(toggle)
        NSWorkspace.shared.notificationCenter.addObserver(
            self,
            selector: #selector(closeForOtherApplication(_:)),
            name: NSWorkspace.didActivateApplicationNotification,
            object: nil
        )
        Timer.scheduledTimer(withTimeInterval: 2, repeats: true) { [weak self] _ in self?.refresh() }
        refresh()
    }

    @objc private func closeForOtherApplication(_ notification: Notification) {
        guard let application = notification.userInfo?[NSWorkspace.applicationUserInfoKey] as? NSRunningApplication,
              let originalApplication = frontmostApplicationBeforePanel,
              application.processIdentifier != ProcessInfo.processInfo.processIdentifier,
              application.processIdentifier != originalApplication else { return }
        dismissPanel()
    }

    private func makePanel() -> NSPanel {
        let panel = NSPanel(contentRect: .zero, styleMask: [.borderless, .nonactivatingPanel], backing: .buffered, defer: false)
        panel.level = .statusBar
        panel.isFloatingPanel = true
        // Accessory apps are not always allowed to become frontmost. Let the
        // panel remain visible after an automatic call, then close it from the
        // workspace activation observer above when the user changes apps.
        panel.hidesOnDeactivate = false
        panel.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary, .transient]
        panel.backgroundColor = .clear
        panel.isOpaque = false
        panel.hasShadow = true
        return panel
    }

    private func settlement(height: CGFloat) -> NSViewController {
        NSHostingController(rootView: SettlementView(model: model, open: open, acknowledge: acknowledge, panelHeight: height))
    }

    private func call(_ unit: WorkUnit, height: CGFloat) -> NSViewController {
        NSHostingController(rootView: CallView(unit: unit, model: model, open: open, snooze: snooze, panelHeight: height))
    }

    private func statusItemFrame(on button: NSStatusBarButton) -> CGRect? {
        guard let window = button.window else { return nil }
        return window.convertToScreen(button.convert(button.bounds, to: nil))
    }

    @discardableResult
    private func present(_ mode: PanelMode) -> Bool {
        guard model.hasSettlementContent, let button = item.button, let anchor = statusItemFrame(on: button) else {
            return false
        }
        let anchorCenter = CGPoint(x: anchor.midX, y: anchor.midY)
        let screen = button.window?.screen ?? NSScreen.screens.first(where: { $0.frame.contains(anchorCenter) }) ?? NSScreen.main
        guard let screen else { return false }
        let frame = JinglePanelLayout.frame(anchor: anchor, visibleFrame: screen.visibleFrame, preferredSize: CGSize(width: 380, height: mode.preferredHeight))
        guard !frame.isEmpty else {
            return false
        }
        let panel = self.panel ?? makePanel()
        self.panel = panel
        frontmostApplicationBeforePanel = NSWorkspace.shared.frontmostApplication?.processIdentifier
        switch mode {
        case .settlement:
            callUnitID = nil
            panel.contentViewController = settlement(height: frame.height)
        case .call(let unit):
            callUnitID = unit.id
            panel.contentViewController = call(unit, height: frame.height)
        }
        panel.setFrame(frame, display: true)
        panel.orderFrontRegardless()
        return panel.isVisible
    }

    private func dismissPanel() {
        panel?.orderOut(nil)
        panel?.close()
        panel = nil
        frontmostApplicationBeforePanel = nil
        callUnitID = nil
    }

    func refresh() {
        let count = model.pendingCount
        item.button?.title = count == 0 ? "•" : "\(count)"
        item.button?.contentTintColor = count == 0 ? .secondaryLabelColor : (model.blocked.isEmpty ? .labelColor : .systemOrange)
        if let callUnitID, !model.callableBlocked.contains(where: { $0.id == callUnitID }) { dismissPanel() }
        if !model.hasSettlementContent { dismissPanel() }
        if let first = model.callableBlocked.first(where: { !calledUnitIDs.contains($0.id) }), !(panel?.isVisible ?? false) {
            if present(.call(first)) { calledUnitIDs.insert(first.id) }
        }
    }

    @objc func toggle() {
        guard model.hasSettlementContent else { dismissPanel(); return }
        if panel?.isVisible ?? false { dismissPanel() }
        else { present(.settlement) }
    }

    private func open(_ unit: WorkUnit) {
        model.resume(unit)
    }

    private func snooze(_ unit: WorkUnit) {
        // Dismissing a call is quiet; only an explicit snooze makes this unit
        // eligible to call again after its requested delay.
        calledUnitIDs.remove(unit.id)
        model.snooze(unit)
        dismissPanel()
    }

    private func acknowledge(_ unit: WorkUnit) {
        model.acknowledge(unit)
        dismissPanel()
    }
}

@main
enum CodexNotificationSettingsApp {
    private static let appDelegate = AppDelegate()

    static func main() {
        let app = NSApplication.shared
        app.setActivationPolicy(.accessory)
        let mainMenu = NSMenu()
        let appMenuItem = NSMenuItem()
        let appMenu = NSMenu()
        appMenu.addItem(withTitle: "退出 Codex Jingle", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        appMenuItem.submenu = appMenu
        mainMenu.addItem(appMenuItem)
        app.mainMenu = mainMenu
        app.delegate = appDelegate
        app.run()
    }
}
