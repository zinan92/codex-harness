#!/usr/bin/python3
"""Play a status sound and optionally announce a Codex task when a turn completes.

The Codex `notify` callback returns quickly after launching a detached worker.
Workers serialize notification playback with an advisory file lock and persist
turn IDs for at-most-once delivery.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from typing import Any


CODEX_DIR = Path.home() / ".codex"
RUNTIME_DIR = CODEX_DIR / "spoken-notify"
STATE_PATH = RUNTIME_DIR / "state.json"
LOCK_PATH = RUNTIME_DIR / "sound.lock"
EVENT_LOG_PATH = RUNTIME_DIR / "events.jsonl"
SETTINGS_PATH = RUNTIME_DIR / "settings.json"
IMPORTED_SOUNDS_DIR = RUNTIME_DIR / "sounds"
INSTALLED_SOUNDS_DIR = Path(__file__).with_name("sounds")
REPOSITORY_SOUNDS_DIR = Path(__file__).parent.parent / "assets" / "sounds"
BUNDLED_SOUNDS_DIR = (
    INSTALLED_SOUNDS_DIR
    if INSTALLED_SOUNDS_DIR.is_dir()
    else REPOSITORY_SOUNDS_DIR
)
SETTINGS_APP_PATH = Path.home() / "Applications" / "Codex 通知设置.app"
SESSION_INDEX_PATH = CODEX_DIR / "session_index.jsonl"
STATE_DATABASES = (
    CODEX_DIR / "state_5.sqlite",
    CODEX_DIR / "sqlite" / "state_5.sqlite",
)
MAX_TITLE_LENGTH = 36
MAX_CLASSIFIER_CHARS = 4_000
SOUND_TIMEOUT_SECONDS = 3
SPEECH_TIMEOUT_SECONDS = 30
MAX_SPEECH_CACHE_FILES = 96
FALLBACK_VOICE = "Tingting"
FALLBACK_SPEECH_RATE = 190
DEFAULT_EFFECT_VOLUME = 1.0
STATUS_SUCCESS = "success"
STATUS_ATTENTION = "attention"
SPEECH_CONTENT_TITLE_STATUS = "title_status"
SPEECH_CONTENT_STATUS_ONLY = "status_only"
DEFAULT_VOICE_PROFILE = "warm_female"
VOICE_PROFILES = {
    "warm_female": {
        "name": "温和女声 · Sandy",
        "mood": "自然",
        "voice": "Sandy (Chinese (China mainland))",
        "rate": 178,
    },
    "clear_female": {
        "name": "清亮女声 · Flo",
        "mood": "清晰",
        "voice": "Flo (Chinese (China mainland))",
        "rate": 182,
    },
    "calm_male": {
        "name": "沉稳男声 · Reed",
        "mood": "沉稳",
        "voice": "Reed (Chinese (China mainland))",
        "rate": 176,
    },
    "classic": {
        "name": "经典中文 · Tingting",
        "mood": "稳定",
        "voice": FALLBACK_VOICE,
        "rate": FALLBACK_SPEECH_RATE,
    },
}
SPEECH_CONTENT_OPTIONS = (
    (SPEECH_CONTENT_TITLE_STATUS, "任务名 + 状态", "清楚是谁"),
    (SPEECH_CONTENT_STATUS_ONLY, "只播报状态", "最简短"),
)
SOUND_PATHS = {
    STATUS_SUCCESS: BUNDLED_SOUNDS_DIR / "warm-chime.wav",
    STATUS_ATTENTION: BUNDLED_SOUNDS_DIR / "quiet-tap.wav",
}
LEGACY_SOUND_PATHS = {
    STATUS_SUCCESS: Path("/System/Library/Sounds/Hero.aiff"),
    STATUS_ATTENTION: Path("/System/Library/Sounds/Purr.aiff"),
}
CURATED_SOUND_OPTIONS = {
    STATUS_SUCCESS: (
        ("暖木铃 · Warm Chime", "轻快", "warm-chime.wav"),
        ("街机胜利 · Arcade Win", "雀跃", "arcade-win.wav"),
        ("轻轻一弹 · Soft Pop", "俏皮", "soft-pop.wav"),
        ("闪光确认 · Sparkle", "明亮", "sparkle-confirm.wav"),
        ("快速完成 · Quick Done", "利落", "quick-done.wav"),
        ("明亮铃声 · Bright Bell", "清脆", "bright-bell.wav"),
        ("升级啦 · Level Up", "庆祝", "level-up.wav"),
        ("能量上升 · Energy Rise", "有劲", "energy-rise.wav"),
    ),
    STATUS_ATTENTION: (
        ("轻轻一点 · Quiet Tap", "平静", "quiet-tap.wav"),
        ("玻璃轻响 · Glass Ping", "清亮", "glass-ping.wav"),
        ("温柔敲门 · Gentle Knock", "沉稳", "gentle-knock.wav"),
        ("问号绽放 · Question", "提醒", "question-bloom.wav"),
        ("再确认一下 · Double Check", "克制", "double-check.wav"),
        ("好奇一声 · Curious Blip", "轻巧", "curious-blip.wav"),
        ("请检查 · Review Ping", "明确", "review-ping.wav"),
        ("柔和警示 · Soft Alert", "警示", "soft-alert.wav"),
    ),
}
SOUND_DIRECTORIES = (
    Path("/System/Library/Sounds"),
    Path("/Library/Sounds"),
    Path.home() / "Library" / "Sounds",
    IMPORTED_SOUNDS_DIR,
)
SUPPORTED_AUDIO_SUFFIXES = {".aif", ".aiff", ".caf", ".m4a", ".mp3", ".wav"}
DEFAULT_SETTINGS = {
    "schema_version": 4,
    "success_sound": str(SOUND_PATHS[STATUS_SUCCESS]),
    "attention_sound": str(SOUND_PATHS[STATUS_ATTENTION]),
    "effect_volume": DEFAULT_EFFECT_VOLUME,
    "speech_enabled": True,
    "speech_content": SPEECH_CONTENT_TITLE_STATUS,
    "voice_profile": DEFAULT_VOICE_PROFILE,
}
ATTENTION_PATTERNS = (
    ("not_met", re.compile(r"\bnot\s+met\b", re.IGNORECASE)),
    ("partially_met", re.compile(r"\bpartially\s+met\b", re.IGNORECASE)),
    ("missing_evidence", re.compile(r"\bmissing\s+(?:visual\s+)?evidence\b", re.IGNORECASE)),
    ("accept_with_caveats", re.compile(r"\baccept\s+with\s+caveats\b", re.IGNORECASE)),
    ("needs_human", re.compile(r"\bneeds?\s+(?:a\s+)?human\b", re.IGNORECASE)),
    ("structured_failed", re.compile(r"(?im)^\s*(?:#{1,6}\s*)?(?:[-*|]\s*)?(?:status|result|verdict|validation|tests?)\s*[:：-]\s*(?:failed|blocked|unverified|not\s+met|partially\s+met)\b")),
    ("inline_failed_verdict", re.compile(r"(?i)\b(?:status|result|verdict|validation)\s*(?:is\s*)?[:：-]?\s*(?:failed|blocked|unverified|not\s+met|partially\s+met)\b")),
    ("failed_check", re.compile(r"(?i)\b(?:build|tests?|validation|verification)\s+(?:has\s+)?failed\b")),
    ("pending_verification", re.compile(r"(?i)\b(?:pending|requires?|needs?)\s+(?:further\s+)?verification\b")),
    ("could_not_verify", re.compile(r"(?i)\b(?:could\s+not|unable\s+to|not)\s+verif(?:y|ied)\b")),
    ("waiting_for_decision", re.compile(r"(?i)\bwaiting\s+for\s+(?:your|human)\s+(?:input|decision|approval)\b")),
    ("structured_unknown", re.compile(r"(?im)^\s*(?:[-*|]\s*)?unknown(?:\s*/\s*missing\s+evidence)?\b")),
)
ATTENTION_MARKERS = (
    ("未完成", "未完成"),
    ("未通过", "未通过"),
    ("任务失败", "任务失败"),
    ("测试失败", "测试失败"),
    ("构建失败", "构建失败"),
    ("缺少证据", "缺少证据"),
    ("缺少视觉证据", "缺少视觉证据"),
    ("待确认", "待确认"),
    ("待验证", "待验证"),
    ("需要决定", "需要决定"),
    ("需要你决定", "需要你决定"),
    ("需要用户决定", "需要用户决定"),
    ("待用户确认", "待用户确认"),
)


def ensure_runtime_dir() -> None:
    RUNTIME_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        RUNTIME_DIR.chmod(0o700)
    except OSError:
        pass


def ensure_private_directory(path: Path) -> None:
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        path.chmod(0o700)
    except OSError:
        pass


def discover_sounds(directories: tuple[Path, ...] | None = None) -> list[dict[str, str]]:
    """Return playable local sound files from deterministic, injectable roots."""
    roots = directories if directories is not None else SOUND_DIRECTORIES
    discovered: list[dict[str, str]] = []
    seen_paths: set[str] = set()
    for root in roots:
        try:
            candidates = sorted(root.iterdir(), key=lambda item: item.name.casefold())
        except OSError:
            continue
        for candidate in candidates:
            if not candidate.is_file() or candidate.suffix.lower() not in SUPPORTED_AUDIO_SUFFIXES:
                continue
            resolved = str(candidate.resolve())
            if resolved in seen_paths:
                continue
            seen_paths.add(resolved)
            discovered.append(
                {
                    "name": candidate.stem,
                    "path": resolved,
                    "source": str(root),
                }
            )
    return discovered


def normalize_settings(raw: dict[str, Any] | None) -> dict[str, Any]:
    """Validate each field independently so one bad value cannot break alerts."""
    candidate = raw if isinstance(raw, dict) else {}
    settings = dict(DEFAULT_SETTINGS)
    schema_version = candidate.get("schema_version", 1)
    is_legacy = not isinstance(schema_version, int) or schema_version < 2

    for key, classification in (
        ("success_sound", STATUS_SUCCESS),
        ("attention_sound", STATUS_ATTENTION),
    ):
        value = candidate.get(key)
        if isinstance(value, str):
            path = Path(value).expanduser()
            if path.is_file() and path.suffix.lower() in SUPPORTED_AUDIO_SUFFIXES:
                resolved = path.resolve()
                # V0.2 shipped Hero/Purr as defaults. Treat only those exact
                # legacy defaults as an upgrade to the new curated pack;
                # preserve any sound the user explicitly chose or imported.
                if not (
                    is_legacy
                    and resolved == LEGACY_SOUND_PATHS[classification].resolve()
                ):
                    settings[key] = str(resolved)

    effect_volume = candidate.get("effect_volume")
    if (
        isinstance(effect_volume, (int, float))
        and not isinstance(effect_volume, bool)
        and 0.0 <= float(effect_volume) <= 1.0
    ):
        settings["effect_volume"] = round(float(effect_volume), 2)
    speech_enabled = candidate.get("speech_enabled")
    if isinstance(speech_enabled, bool):
        settings["speech_enabled"] = speech_enabled
    speech_content = candidate.get("speech_content")
    if speech_content in {
        SPEECH_CONTENT_TITLE_STATUS,
        SPEECH_CONTENT_STATUS_ONLY,
    }:
        settings["speech_content"] = speech_content
    voice_profile = candidate.get("voice_profile")
    if isinstance(voice_profile, str) and voice_profile in VOICE_PROFILES:
        settings["voice_profile"] = voice_profile
    return settings


def voice_options() -> list[dict[str, Any]]:
    """Expose product-level voice choices without leaking implementation knobs."""
    return [
        {
            "id": profile_id,
            "name": profile["name"],
            "mood": profile["mood"],
            "source": "macOS · 免费本机",
        }
        for profile_id, profile in VOICE_PROFILES.items()
    ]


def speech_content_options() -> list[dict[str, str]]:
    return [
        {"id": option_id, "name": name, "mood": mood}
        for option_id, name, mood in SPEECH_CONTENT_OPTIONS
    ]


def sound_options(
    classification: str,
    selected_path: str | None = None,
) -> list[dict[str, str]]:
    """Return the small curated picker for one status, preserving custom picks."""
    options = [
        {
            "name": name,
            "mood": mood,
            "path": str((BUNDLED_SOUNDS_DIR / filename).resolve()),
            "source": "Kenney CC0",
        }
        for name, mood, filename in CURATED_SOUND_OPTIONS[classification]
        if (BUNDLED_SOUNDS_DIR / filename).is_file()
    ]
    known_paths = {option["path"] for option in options}
    if selected_path and selected_path not in known_paths:
        selected = Path(selected_path)
        if selected.is_file() and selected.suffix.lower() in SUPPORTED_AUDIO_SUFFIXES:
            options.append(
                {
                    "name": f"{selected.stem} · 当前声音",
                    "mood": "自定义",
                    "path": str(selected.resolve()),
                    "source": "Local",
                }
            )
    return options


def load_settings(path: Path | None = None) -> dict[str, Any]:
    settings_path = SETTINGS_PATH if path is None else path
    try:
        raw = json.loads(settings_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        raw = None
    return normalize_settings(raw)


def save_settings(
    settings: dict[str, Any],
    path: Path | None = None,
) -> dict[str, Any]:
    settings_path = SETTINGS_PATH if path is None else path
    normalized = normalize_settings(settings)
    ensure_private_directory(settings_path.parent)
    descriptor, temp_name = tempfile.mkstemp(
        prefix="settings-", suffix=".json", dir=settings_path.parent
    )
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(normalized, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, settings_path)
        settings_path.chmod(0o600)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise
    return normalized


def import_sound(source: Path, destination_dir: Path | None = None) -> Path:
    source = source.expanduser()
    if not source.is_file() or source.suffix.lower() not in SUPPORTED_AUDIO_SUFFIXES:
        raise ValueError("请选择 aif、aiff、caf、m4a、mp3 或 wav 音频文件")
    target_dir = IMPORTED_SOUNDS_DIR if destination_dir is None else destination_dir
    ensure_private_directory(target_dir)
    destination = target_dir / source.name
    descriptor, temp_name = tempfile.mkstemp(
        prefix="sound-", suffix=source.suffix.lower(), dir=target_dir
    )
    os.close(descriptor)
    try:
        shutil.copyfile(source, temp_name)
        os.chmod(temp_name, 0o600)
        os.replace(temp_name, destination)
        destination.chmod(0o600)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise
    return destination.resolve()


def settings_data() -> dict[str, Any]:
    settings = load_settings()
    return {
        "settings": settings,
        "defaults": dict(DEFAULT_SETTINGS),
        "success_sounds": sound_options(
            STATUS_SUCCESS, settings["success_sound"]
        ),
        "attention_sounds": sound_options(
            STATUS_ATTENTION, settings["attention_sound"]
        ),
        "voice_options": voice_options(),
        "speech_content_options": speech_content_options(),
        "settings_path": str(SETTINGS_PATH),
    }


def read_stdin_object() -> dict[str, Any] | None:
    try:
        value = json.load(sys.stdin)
    except (OSError, json.JSONDecodeError, TypeError):
        return None
    return value if isinstance(value, dict) else None


def event_value(payload: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def parse_payload(raw_payload: str) -> dict[str, Any] | None:
    try:
        payload = json.loads(raw_payload)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(payload, dict):
        return None
    event_type = event_value(payload, "type", "event_type", "event-type")
    if event_type != "agent-turn-complete":
        return None
    return payload


def normalize_title(title: str) -> str:
    title = re.sub(r"\s+", " ", title).strip()
    title = title.strip("`#*_ -—–:：")
    if title.lower().startswith("automation:"):
        title = title.split(":", 1)[1].strip()
    if not title:
        return ""
    if len(title) > MAX_TITLE_LENGTH:
        title = title[:MAX_TITLE_LENGTH].rstrip() + "…"
    return title


def classify_outcome(message: str) -> tuple[str, str]:
    """Return a conservative local classification without retaining content."""
    if not isinstance(message, str) or not message.strip():
        return STATUS_ATTENTION, "missing_message"
    candidate = message[-MAX_CLASSIFIER_CHARS:]
    candidate = re.sub(r"[`*_~]", "", candidate)
    for marker, pattern in ATTENTION_PATTERNS:
        if pattern.search(candidate):
            return STATUS_ATTENTION, marker
    for marker, text_marker in ATTENTION_MARKERS:
        if text_marker in candidate:
            return STATUS_ATTENTION, marker
    return STATUS_SUCCESS, "no_attention_marker"


def normalize_spoken_title(title: str) -> str:
    """Turn UI-oriented thread names into short speech-first Chinese text."""
    spoken = normalize_title(title)
    spoken = re.sub(r"[_/|]+", " ", spoken)
    spoken = re.sub(r"\s*[-—–]\s*", "，", spoken)
    spoken = re.sub(
        r"\b[A-Z]{2,6}\b",
        lambda match: " ".join(match.group(0)),
        spoken,
    )
    spoken = re.sub(r"\s+", " ", spoken).strip(" ，。！？:：")
    return spoken or "Codex"


def build_phrase(
    title: str,
    classification: str,
    content_mode: str = SPEECH_CONTENT_TITLE_STATUS,
) -> str:
    """Build a short speech-first sentence with explicit natural pauses."""
    status_phrase = (
        "任务已完成。"
        if classification == STATUS_SUCCESS
        else "任务已结束，但还有事项需要确认。"
    )
    if content_mode == SPEECH_CONTENT_STATUS_ONLY:
        return status_phrase
    return f"{normalize_spoken_title(title)}。{status_phrase}"


def fallback_title(cwd: str) -> str:
    if cwd:
        name = normalize_title(Path(cwd).name)
        ignored_names = {Path.home().name.casefold(), "users", "documents"}
        if name and name.casefold() not in ignored_names:
            return name
    return "Codex"


def resolve_session_index_title(thread_id: str) -> str:
    if not thread_id or not SESSION_INDEX_PATH.is_file():
        return ""
    matched_title = ""
    try:
        with SESSION_INDEX_PATH.open("r", encoding="utf-8") as handle:
            for line in handle:
                if thread_id not in line:
                    continue
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(item, dict) or item.get("id") != thread_id:
                    continue
                title = normalize_title(str(item.get("thread_name") or ""))
                if title:
                    matched_title = title
    except OSError:
        return ""
    return matched_title


def resolve_thread_title(thread_id: str, cwd: str) -> tuple[str, str]:
    index_title = resolve_session_index_title(thread_id)
    if index_title:
        return index_title, "session_index"
    if thread_id:
        for database in STATE_DATABASES:
            if not database.is_file():
                continue
            try:
                uri = f"file:{database}?mode=ro"
                connection = sqlite3.connect(uri, uri=True, timeout=0.15)
                try:
                    connection.execute("PRAGMA query_only = ON")
                    connection.execute("PRAGMA busy_timeout = 150")
                    row = connection.execute(
                        "SELECT title, cwd FROM threads WHERE id = ? LIMIT 1",
                        (thread_id,),
                    ).fetchone()
                finally:
                    connection.close()
                if row:
                    title = normalize_title(str(row[0] or ""))
                    if title:
                        return title, "thread_db"
                    db_cwd = str(row[1] or "")
                    return fallback_title(db_cwd or cwd), "thread_db_cwd"
            except (OSError, sqlite3.Error):
                continue
    return fallback_title(cwd), "payload_cwd"


def load_seen_turns() -> list[str]:
    try:
        data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return []
    turns = data.get("seen_turn_ids") if isinstance(data, dict) else None
    if not isinstance(turns, list):
        return []
    return [item for item in turns if isinstance(item, str) and item]


def save_seen_turns(turn_ids: list[str]) -> None:
    ensure_runtime_dir()
    payload = {
        "schema_version": 1,
        # Keep the complete history so a delayed redelivery cannot replay an old
        # turn twice. The file remains small for normal interactive usage and
        # preserves the user's exact-once expectation across restarts.
        "seen_turn_ids": turn_ids,
        "updated_at": int(time.time()),
    }
    descriptor, temp_name = tempfile.mkstemp(
        prefix="state-", suffix=".json", dir=RUNTIME_DIR
    )
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, STATE_PATH)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def append_event(event: dict[str, Any]) -> None:
    ensure_runtime_dir()
    event = {"ts": int(time.time()), **event}
    try:
        if EVENT_LOG_PATH.exists() and EVENT_LOG_PATH.stat().st_size > 1_000_000:
            rotated = EVENT_LOG_PATH.with_suffix(".jsonl.1")
            os.replace(EVENT_LOG_PATH, rotated)
        descriptor = os.open(
            EVENT_LOG_PATH,
            os.O_WRONLY | os.O_CREAT | os.O_APPEND,
            0o600,
        )
        with os.fdopen(descriptor, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")
    except OSError:
        pass


def play_sound(
    classification: str,
    settings: dict[str, Any] | None = None,
) -> bool:
    if settings is not None:
        runtime_settings = normalize_settings(settings)
    else:
        runtime_settings = load_settings()
    sound_key = (
        "success_sound" if classification == STATUS_SUCCESS else "attention_sound"
    )
    sound_path = Path(runtime_settings[sound_key])
    if not sound_path.is_file():
        return False
    try:
        completed = subprocess.run(
            [
                "/usr/bin/afplay",
                "-v",
                f"{runtime_settings['effect_volume']:.2f}",
                str(sound_path),
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=SOUND_TIMEOUT_SECONDS,
            check=False,
        )
        return completed.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def speech_profile(
    settings: dict[str, Any],
    classification: str,
) -> tuple[str, int]:
    profile = VOICE_PROFILES[settings["voice_profile"]]
    rate = int(profile["rate"])
    # Clean completions can feel a touch brighter; attention should stay calm.
    rate += 3 if classification == STATUS_SUCCESS else -4
    return str(profile["voice"]), rate


def speech_cache_path(phrase: str, voice: str, rate: int) -> Path:
    cache_key = hashlib.sha256(
        json.dumps(
            {"phrase": phrase, "voice": voice, "rate": rate},
            ensure_ascii=False,
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()[:32]
    return RUNTIME_DIR / "speech-cache" / f"{cache_key}.aiff"


def prune_speech_cache(cache_dir: Path, limit: int = MAX_SPEECH_CACHE_FILES) -> None:
    try:
        cached = sorted(
            (path for path in cache_dir.glob("*.aiff") if path.is_file()),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
    except OSError:
        return
    for stale in cached[limit:]:
        try:
            stale.unlink()
        except OSError:
            pass


def render_speech_file(phrase: str, voice: str, rate: int) -> Path | None:
    """Render once and cache locally so repeat notifications start instantly."""
    destination = speech_cache_path(phrase, voice, rate)
    if destination.is_file() and destination.stat().st_size > 0:
        try:
            destination.touch()
        except OSError:
            pass
        return destination
    ensure_private_directory(destination.parent)
    descriptor, temp_name = tempfile.mkstemp(
        prefix="speech-", suffix=".aiff", dir=destination.parent
    )
    os.close(descriptor)
    try:
        completed = subprocess.run(
            [
                "/usr/bin/say",
                "-v",
                voice,
                "-r",
                str(rate),
                "-o",
                temp_name,
                phrase,
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=SPEECH_TIMEOUT_SECONDS,
            check=False,
        )
        if completed.returncode != 0 or Path(temp_name).stat().st_size == 0:
            return None
        os.chmod(temp_name, 0o600)
        os.replace(temp_name, destination)
        prune_speech_cache(destination.parent)
        return destination
    except (OSError, subprocess.SubprocessError):
        return None
    finally:
        try:
            if os.path.exists(temp_name):
                os.unlink(temp_name)
        except OSError:
            pass


def speak(
    phrase: str,
    settings: dict[str, Any] | None = None,
    classification: str = STATUS_SUCCESS,
) -> bool:
    """Play zero-cost enhanced local speech, with a classic voice fallback."""
    runtime_settings = normalize_settings(settings) if settings is not None else load_settings()
    classification = (
        classification
        if classification in {STATUS_SUCCESS, STATUS_ATTENTION}
        else STATUS_ATTENTION
    )
    voice, rate = speech_profile(runtime_settings, classification)
    rendered = render_speech_file(phrase, voice, rate)
    if rendered is not None:
        try:
            completed = subprocess.run(
                ["/usr/bin/afplay", str(rendered)],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=SPEECH_TIMEOUT_SECONDS,
                check=False,
            )
            if completed.returncode == 0:
                return True
        except (OSError, subprocess.SubprocessError):
            pass

    # A removed enhanced voice or cache error must not silence completion alerts.
    try:
        completed = subprocess.run(
            [
                "/usr/bin/say",
                "-v",
                FALLBACK_VOICE,
                "-r",
                str(FALLBACK_SPEECH_RATE),
                phrase,
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=SPEECH_TIMEOUT_SECONDS,
            check=False,
        )
        return completed.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def preview_sound(classification: str, settings: dict[str, Any]) -> bool:
    """Preview one unsaved candidate sound under the production sound lock."""
    ensure_runtime_dir()
    classification = (
        classification
        if classification in {STATUS_SUCCESS, STATUS_ATTENTION}
        else STATUS_ATTENTION
    )
    normalized = normalize_settings(settings)
    lock_descriptor = os.open(LOCK_PATH, os.O_RDWR | os.O_CREAT, 0o600)
    os.fchmod(lock_descriptor, 0o600)
    with os.fdopen(lock_descriptor, "a+", encoding="utf-8") as lock_handle:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
        sound_success = play_sound(classification, settings=normalized)
    append_event(
        {
            "status": "preview_completed" if sound_success else "preview_failed",
            "classification": classification,
            "sound_played": sound_success,
        }
    )
    return sound_success


def preview_speech(title: str, classification: str, settings: dict[str, Any]) -> bool:
    """Preview speech only, keeping sound-effect audition independent."""
    ensure_runtime_dir()
    normalized = normalize_settings(settings)
    if not normalized["speech_enabled"]:
        return False
    classification = (
        classification
        if classification in {STATUS_SUCCESS, STATUS_ATTENTION}
        else STATUS_ATTENTION
    )
    phrase = build_phrase(
        normalize_title(title) or "Codex 测试任务",
        classification,
        normalized["speech_content"],
    )
    lock_descriptor = os.open(LOCK_PATH, os.O_RDWR | os.O_CREAT, 0o600)
    os.fchmod(lock_descriptor, 0o600)
    with os.fdopen(lock_descriptor, "a+", encoding="utf-8") as lock_handle:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
        speech_success = speak(
            phrase,
            settings=normalized,
            classification=classification,
        )
    append_event(
        {
            "status": "speech_preview_completed" if speech_success else "speech_preview_failed",
            "classification": classification,
        }
    )
    return speech_success


def worker(
    turn_id: str,
    thread_id: str,
    title: str,
    title_source: str,
    classification: str,
) -> int:
    ensure_runtime_dir()
    if classification not in {STATUS_SUCCESS, STATUS_ATTENTION}:
        classification = STATUS_ATTENTION
    try:
        lock_descriptor = os.open(LOCK_PATH, os.O_RDWR | os.O_CREAT, 0o600)
        os.fchmod(lock_descriptor, 0o600)
        with os.fdopen(lock_descriptor, "a+", encoding="utf-8") as lock_handle:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
            seen_turns = load_seen_turns()
            if turn_id in seen_turns:
                append_event(
                    {
                        "status": "duplicate_suppressed",
                        "turn_id": turn_id,
                        "thread_id": thread_id,
                        "title": title,
                        "classification": classification,
                    }
                )
                return 0

            # Record before playback. This intentionally provides at-most-once
            # delivery if the worker is interrupted during the notification.
            save_seen_turns([*seen_turns, turn_id])
            runtime_settings = load_settings()
            started = time.monotonic()
            append_event(
                {
                    "status": "notification_started",
                    "turn_id": turn_id,
                    "thread_id": thread_id,
                    "title": title,
                    "title_source": title_source,
                    "classification": classification,
                    "sound": Path(
                        runtime_settings[
                            "success_sound"
                            if classification == STATUS_SUCCESS
                            else "attention_sound"
                        ]
                    ).name,
                    "effect_volume": runtime_settings["effect_volume"],
                    "speech_enabled": runtime_settings["speech_enabled"],
                    "speech_content": runtime_settings["speech_content"],
                    "voice_profile": runtime_settings["voice_profile"],
                }
            )
            sound_success = play_sound(classification, settings=runtime_settings)
            phrase = build_phrase(
                title,
                classification,
                runtime_settings["speech_content"],
            )
            speech_success = (
                speak(
                    phrase,
                    settings=runtime_settings,
                    classification=classification,
                )
                if runtime_settings["speech_enabled"]
                else None
            )
            append_event(
                {
                    "status": "notification_completed"
                    if sound_success and speech_success is not False
                    else "notification_partial_failure",
                    "turn_id": turn_id,
                    "thread_id": thread_id,
                    "title": title,
                    "classification": classification,
                    "sound_played": sound_success,
                    "speech_spoken": speech_success,
                    "duration_ms": round((time.monotonic() - started) * 1000),
                }
            )
    except Exception as error:
        append_event(
            {
                "status": "worker_error",
                "turn_id": turn_id,
                "thread_id": thread_id,
                "error_type": type(error).__name__,
            }
        )
    return 0


def launch_worker(
    turn_id: str,
    thread_id: str,
    title: str,
    title_source: str,
    classification: str,
) -> None:
    command = [
        "/usr/bin/python3",
        str(Path(__file__).resolve()),
        "--worker",
        "--turn-id",
        turn_id,
        "--thread-id",
        thread_id,
        "--title",
        title,
        "--title-source",
        title_source,
        "--status",
        classification,
    ]
    try:
        subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            close_fds=True,
        )
    except OSError as error:
        append_event(
            {
                "status": "launch_failed",
                "turn_id": turn_id,
                "thread_id": thread_id,
                "error_type": type(error).__name__,
            }
        )


def handle_notify(raw_payload: str, dry_run: bool = False) -> int:
    payload = parse_payload(raw_payload)
    if payload is None:
        append_event({"status": "ignored_invalid_or_unsupported_payload"})
        return 0

    thread_id = event_value(payload, "thread-id", "thread_id")
    turn_id = event_value(payload, "turn-id", "turn_id")
    cwd = event_value(payload, "cwd")
    final_message = event_value(
        payload,
        "last-assistant-message",
        "last_assistant_message",
    )
    if not turn_id:
        # Missing event IDs cannot be safely deduplicated. Fail closed instead
        # of risking repeated or misattributed announcements.
        append_event(
            {
                "status": "ignored_missing_turn_id",
                "thread_id": thread_id,
            }
        )
        return 0
    title, title_source = resolve_thread_title(thread_id, cwd)
    classification, classifier_marker = classify_outcome(final_message)
    if dry_run:
        settings = load_settings()
        sound_key = (
            "success_sound"
            if classification == STATUS_SUCCESS
            else "attention_sound"
        )
        result = {
            "turn_id": turn_id,
            "thread_id": thread_id,
            "title": title,
            "title_source": title_source,
            "classification": classification,
            "classifier_marker": classifier_marker,
            "sound": Path(settings[sound_key]).name,
            "effect_volume": settings["effect_volume"],
            "speech_enabled": settings["speech_enabled"],
            "speech_content": settings["speech_content"],
            "voice_profile": settings["voice_profile"],
            "phrase": build_phrase(
                title,
                classification,
                settings["speech_content"],
            ),
        }
        print(json.dumps(result, ensure_ascii=False))
        return 0
    append_event(
        {
            "status": "classified",
            "turn_id": turn_id,
            "thread_id": thread_id,
            "title": title,
            "classification": classification,
            "classifier_marker": classifier_marker,
        }
    )
    launch_worker(turn_id, thread_id, title, title_source, classification)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("payload", nargs="?", help="Codex notify JSON payload")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--test-title", help="Play a manual status-sound test")
    parser.add_argument(
        "--setup",
        action="store_true",
        help="Open the local Codex notification settings window",
    )
    parser.add_argument(
        "--show-settings",
        action="store_true",
        help="Print the effective local notification settings",
    )
    parser.add_argument("--settings-data", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument(
        "--save-settings-json", action="store_true", help=argparse.SUPPRESS
    )
    parser.add_argument(
        "--preview-settings-json", action="store_true", help=argparse.SUPPRESS
    )
    parser.add_argument(
        "--preview-sound-json", action="store_true", help=argparse.SUPPRESS
    )
    parser.add_argument(
        "--preview-speech-json", action="store_true", help=argparse.SUPPRESS
    )
    parser.add_argument("--import-sound", help=argparse.SUPPRESS)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--turn-id", default="", help=argparse.SUPPRESS)
    parser.add_argument("--thread-id", default="", help=argparse.SUPPRESS)
    parser.add_argument("--title", default="", help=argparse.SUPPRESS)
    parser.add_argument("--title-source", default="", help=argparse.SUPPRESS)
    parser.add_argument(
        "--status",
        choices=(STATUS_SUCCESS, STATUS_ATTENTION),
        default=STATUS_ATTENTION,
        help=argparse.SUPPRESS,
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.setup:
        if not SETTINGS_APP_PATH.is_dir():
            print(f"Settings app is missing: {SETTINGS_APP_PATH}")
            return 1
        try:
            running = subprocess.run(
                ["/usr/bin/pgrep", "-x", "CodexNotificationSettings"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=2,
                check=False,
            ).returncode == 0
            open_command = ["/usr/bin/open"]
            if not running:
                open_command.append("-n")
            open_command.append(str(SETTINGS_APP_PATH))
            completed = subprocess.run(
                open_command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=10,
                check=False,
            )
            return completed.returncode
        except (OSError, subprocess.SubprocessError):
            return 1
    if args.show_settings:
        print(json.dumps(load_settings(), ensure_ascii=False, indent=2))
        return 0
    if args.settings_data:
        print(json.dumps(settings_data(), ensure_ascii=False))
        return 0
    if args.save_settings_json:
        candidate = read_stdin_object()
        if candidate is None:
            return 2
        print(json.dumps(save_settings(candidate), ensure_ascii=False))
        return 0
    if args.preview_settings_json or args.preview_sound_json:
        request = read_stdin_object()
        if request is None or not isinstance(request.get("settings"), dict):
            return 2
        classification = str(request.get("status") or STATUS_ATTENTION)
        sound_ok = preview_sound(classification, request["settings"])
        print(json.dumps({"sound": sound_ok}))
        return 0 if sound_ok else 1
    if args.preview_speech_json:
        request = read_stdin_object()
        if request is None or not isinstance(request.get("settings"), dict):
            return 2
        classification = str(request.get("status") or STATUS_SUCCESS)
        title = str(request.get("title") or "Codex 测试任务")
        speech_ok = preview_speech(title, classification, request["settings"])
        print(json.dumps({"speech": speech_ok}))
        return 0 if speech_ok else 1
    if args.import_sound:
        try:
            destination = import_sound(Path(args.import_sound))
        except (OSError, ValueError) as error:
            print(str(error))
            return 2
        print(str(destination))
        return 0
    if args.worker:
        return worker(
            args.turn_id,
            args.thread_id,
            normalize_title(args.title) or "Codex",
            args.title_source or "worker_argument",
            args.status,
        )
    if args.test_title:
        title = normalize_title(args.test_title) or "Codex"
        launch_worker(
            f"manual:{time.time_ns()}",
            "manual-test",
            title,
            "manual_test",
            args.status,
        )
        return 0
    if not args.payload:
        return 0
    return handle_notify(args.payload, dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
