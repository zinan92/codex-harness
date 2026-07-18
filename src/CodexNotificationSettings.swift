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

final class WidgetWindow: NSWindow {
    override var canBecomeKey: Bool { true }
    override var canBecomeMain: Bool { true }
}

final class AppDelegate: NSObject, NSApplicationDelegate {
    private var window: WidgetWindow?

    func applicationDidFinishLaunching(_ notification: Notification) {
        let content = NSHostingController(rootView: ContentView())
        let window = WidgetWindow(
            contentRect: NSRect(x: 0, y: 0, width: 344, height: 403),
            styleMask: [.borderless, .closable],
            backing: .buffered,
            defer: false
        )
        window.contentViewController = content
        window.title = "Codex Jingle"
        window.isMovableByWindowBackground = true
        window.isOpaque = false
        window.backgroundColor = .clear
        window.hasShadow = true
        window.hidesOnDeactivate = false
        window.isReleasedWhenClosed = false
        window.animationBehavior = .documentWindow
        window.center()
        self.window = window
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }

    func applicationDidBecomeActive(_ notification: Notification) {
        window?.makeKeyAndOrderFront(nil)
    }

    func applicationShouldHandleReopen(
        _ sender: NSApplication,
        hasVisibleWindows flag: Bool
    ) -> Bool {
        window?.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
        return true
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        false
    }
}

@main
enum CodexNotificationSettingsApp {
    private static let appDelegate = AppDelegate()

    static func main() {
        let app = NSApplication.shared
        app.setActivationPolicy(.regular)
        let mainMenu = NSMenu()
        let appMenuItem = NSMenuItem()
        let appMenu = NSMenu()
        appMenu.addItem(
            withTitle: "退出 Codex Jingle",
            action: #selector(NSApplication.terminate(_:)),
            keyEquivalent: "q"
        )
        appMenuItem.submenu = appMenu
        mainMenu.addItem(appMenuItem)
        app.mainMenu = mainMenu
        app.delegate = appDelegate
        app.run()
    }
}
