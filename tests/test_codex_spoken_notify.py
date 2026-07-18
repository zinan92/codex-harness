#!/usr/bin/env python3

from __future__ import annotations

import importlib.util
import json
import multiprocessing
from pathlib import Path
import stat
import tempfile
import time
import unittest
from unittest import mock


MODULE_PATH = Path(__file__).parents[1] / "src" / "codex_spoken_notify.py"
SPEC = importlib.util.spec_from_file_location("codex_spoken_notify", MODULE_PATH)
assert SPEC and SPEC.loader
notifier = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(notifier)


def actual_worker_interval(runtime_path: str, output_path: str, label: str) -> None:
    runtime = Path(runtime_path)
    notifier.RUNTIME_DIR = runtime
    notifier.STATE_PATH = runtime / "state.json"
    notifier.LOCK_PATH = runtime / "sound.lock"
    notifier.EVENT_LOG_PATH = runtime / "events.jsonl"

    def record_sound(_classification: str, settings=None) -> bool:
        del settings
        start = time.time()
        time.sleep(0.12)
        end = time.time()
        with Path(output_path).open("a", encoding="utf-8") as output:
            output.write(
                json.dumps(
                    {"label": label, "kind": "sound", "start": start, "end": end}
                )
                + "\n"
            )
        return True

    notifier.play_sound = record_sound
    notifier.speak = lambda _phrase, settings=None, classification="success": True
    notifier.worker(
        f"turn-{label}",
        f"thread-{label}",
        label,
        "test",
        notifier.STATUS_SUCCESS,
    )


class SpokenNotifyTests(unittest.TestCase):
    def test_discover_sounds_uses_injectable_directories(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "Ping.aiff").write_bytes(b"audio")
            (root / "Custom.wav").write_bytes(b"audio")
            (root / "ignore.txt").write_text("not audio", encoding="utf-8")
            sounds = notifier.discover_sounds((root, Path("/missing")))
        self.assertEqual([item["name"] for item in sounds], ["Custom", "Ping"])
        self.assertTrue(all(item["source"] == str(root) for item in sounds))

    def test_curated_status_pickers_are_expanded_distinct_and_playable(self) -> None:
        success = notifier.sound_options(notifier.STATUS_SUCCESS)
        attention = notifier.sound_options(notifier.STATUS_ATTENTION)
        self.assertEqual(len(success), 8)
        self.assertEqual(len(attention), 8)
        self.assertTrue(all(Path(item["path"]).is_file() for item in success + attention))
        self.assertFalse({item["path"] for item in success} & {item["path"] for item in attention})
        self.assertTrue(all(item["source"] == "Kenney CC0" for item in success + attention))

    def test_settings_validate_each_field_and_fall_back_independently(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            valid_sound = Path(temp_dir) / "valid.wav"
            valid_sound.write_bytes(b"audio")
            settings = notifier.normalize_settings(
                {
                    "success_sound": str(valid_sound),
                    "attention_sound": "/missing/sound.wav",
                    "effect_volume": 0.35,
                }
            )
        self.assertEqual(settings["success_sound"], str(valid_sound.resolve()))
        self.assertEqual(
            settings["attention_sound"],
            str(notifier.SOUND_PATHS[notifier.STATUS_ATTENTION]),
        )
        self.assertEqual(settings["schema_version"], 4)
        self.assertNotIn("voice", settings)
        self.assertNotIn("speech_rate", settings)
        self.assertEqual(settings["effect_volume"], 0.35)
        self.assertTrue(settings["speech_enabled"])
        self.assertEqual(settings["speech_content"], "title_status")
        self.assertEqual(settings["voice_profile"], "warm_female")

    def test_speech_setting_is_boolean_and_defaults_on(self) -> None:
        self.assertFalse(notifier.normalize_settings({"speech_enabled": False})["speech_enabled"])
        self.assertTrue(notifier.normalize_settings({"speech_enabled": "no"})["speech_enabled"])
        self.assertTrue(notifier.normalize_settings({})["speech_enabled"])

    def test_speech_content_and_voice_profile_validate_independently(self) -> None:
        settings = notifier.normalize_settings(
            {"speech_content": "status_only", "voice_profile": "calm_male"}
        )
        self.assertEqual(settings["speech_content"], "status_only")
        self.assertEqual(settings["voice_profile"], "calm_male")
        invalid = notifier.normalize_settings(
            {"speech_content": "essay", "voice_profile": "network_voice"}
        )
        self.assertEqual(invalid["speech_content"], "title_status")
        self.assertEqual(invalid["voice_profile"], "warm_female")

    def test_product_voice_options_are_free_local_profiles(self) -> None:
        options = notifier.voice_options()
        self.assertEqual(
            [option["id"] for option in options],
            ["warm_female", "clear_female", "calm_male", "classic"],
        )
        self.assertTrue(all(option["source"] == "macOS · 免费本机" for option in options))
        self.assertTrue(all("voice" not in option for option in options))

    def test_v02_default_sounds_migrate_to_curated_pack(self) -> None:
        settings = notifier.normalize_settings(
            {
                "schema_version": 1,
                "success_sound": str(notifier.LEGACY_SOUND_PATHS[notifier.STATUS_SUCCESS]),
                "attention_sound": str(notifier.LEGACY_SOUND_PATHS[notifier.STATUS_ATTENTION]),
                "voice": "Tingting",
                "speech_rate": 200,
                "effect_volume": 0.7,
            }
        )
        self.assertEqual(settings["success_sound"], str(notifier.SOUND_PATHS[notifier.STATUS_SUCCESS]))
        self.assertEqual(settings["attention_sound"], str(notifier.SOUND_PATHS[notifier.STATUS_ATTENTION]))
        self.assertNotIn("voice", settings)
        self.assertEqual(settings["voice_profile"], "warm_female")
        self.assertEqual(settings["effect_volume"], 0.7)

    def test_save_and_load_settings_are_atomic_and_owner_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "private" / "settings.json"
            saved = notifier.save_settings(
                {
                    **notifier.DEFAULT_SETTINGS,
                    "effect_volume": 0.6,
                },
                path=path,
            )
            loaded = notifier.load_settings(path=path)
            self.assertEqual(saved, loaded)
            self.assertEqual(loaded["effect_volume"], 0.6)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE(path.parent.stat().st_mode), 0o700)

    def test_missing_corrupt_and_deleted_sound_settings_fall_back(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            missing_path = root / "missing.json"
            self.assertEqual(
                notifier.load_settings(path=missing_path),
                notifier.DEFAULT_SETTINGS,
            )

            corrupt_path = root / "corrupt.json"
            corrupt_path.write_text("{not-json", encoding="utf-8")
            self.assertEqual(
                notifier.load_settings(path=corrupt_path),
                notifier.DEFAULT_SETTINGS,
            )

            selected_sound = root / "selected.wav"
            selected_sound.write_bytes(b"audio")
            settings_path = root / "settings.json"
            notifier.save_settings(
                {
                    **notifier.DEFAULT_SETTINGS,
                    "success_sound": str(selected_sound),
                },
                path=settings_path,
            )
            selected_sound.unlink()
            loaded = notifier.load_settings(path=settings_path)
            self.assertEqual(
                loaded["success_sound"],
                str(notifier.SOUND_PATHS[notifier.STATUS_SUCCESS]),
            )

    def test_import_sound_copies_owner_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "custom.wav"
            source.write_bytes(b"custom-audio")
            destination = notifier.import_sound(source, root / "sounds")
            self.assertEqual(destination.read_bytes(), b"custom-audio")
            self.assertEqual(stat.S_IMODE(destination.stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE(destination.parent.stat().st_mode), 0o700)

    def test_parse_complete_payload(self) -> None:
        payload = notifier.parse_payload(
            json.dumps(
                {
                    "type": "agent-turn-complete",
                    "thread-id": "thread-1",
                    "turn-id": "turn-1",
                }
            )
        )
        self.assertIsNotNone(payload)
        self.assertEqual(payload["thread-id"], "thread-1")

    def test_parse_rejects_invalid_and_other_events(self) -> None:
        self.assertIsNone(notifier.parse_payload("not-json"))
        self.assertIsNone(notifier.parse_payload('{"type":"approval-needed"}'))

    def test_missing_turn_id_is_ignored(self) -> None:
        payload = json.dumps(
            {
                "type": "agent-turn-complete",
                "thread-id": "thread-1",
                "cwd": "/tmp/trading",
            }
        )
        with (
            mock.patch.object(notifier, "append_event") as append_event,
            mock.patch.object(notifier, "launch_worker") as launch_worker,
        ):
            self.assertEqual(notifier.handle_notify(payload), 0)
        launch_worker.assert_not_called()
        append_event.assert_called_once_with(
            {"status": "ignored_missing_turn_id", "thread_id": "thread-1"}
        )

    def test_title_normalization(self) -> None:
        self.assertEqual(
            notifier.normalize_title("  Automation: 交易系统   检查  "),
            "交易系统 检查",
        )
        long_title = "很长的任务标题" * 10
        self.assertLessEqual(len(notifier.normalize_title(long_title)), 37)

    def test_speech_first_phrase_has_natural_pauses_and_content_modes(self) -> None:
        self.assertEqual(
            notifier.build_phrase("Token POS", notifier.STATUS_SUCCESS),
            "Token P O S。任务已完成。",
        )
        self.assertEqual(
            notifier.build_phrase(
                "交易系统",
                notifier.STATUS_ATTENTION,
                notifier.SPEECH_CONTENT_TITLE_STATUS,
            ),
            "交易系统。任务已结束，但还有事项需要确认。",
        )
        self.assertEqual(
            notifier.build_phrase(
                "交易系统",
                notifier.STATUS_SUCCESS,
                notifier.SPEECH_CONTENT_STATUS_ONLY,
            ),
            "任务已完成。",
        )

    def test_classifier_success_and_attention(self) -> None:
        success_examples = (
            "任务已完成，8/8 tests passed。",
            "The previously failed test is fixed; no failures remain.",
            "风险已消除，全部验证通过。",
        )
        for message in success_examples:
            with self.subTest(message=message):
                self.assertEqual(
                    notifier.classify_outcome(message),
                    (notifier.STATUS_SUCCESS, "no_attention_marker"),
                )

        attention_examples = {
            "Validation: failed": "structured_failed",
            "## Verdict: Failed": "structured_failed",
            "The final verdict is: failed": "inline_failed_verdict",
            "Build failed during verification": "failed_check",
            "This remains pending verification": "pending_verification",
            "I could not verify the deployment": "could_not_verify",
            "Waiting for your decision": "waiting_for_decision",
            "Partially Met": "partially_met",
            "Missing visual evidence": "missing_evidence",
            "还有一项待确认": "待确认",
            "测试失败，需要处理": "测试失败",
        }
        for message, marker in attention_examples.items():
            with self.subTest(message=message):
                self.assertEqual(
                    notifier.classify_outcome(message),
                    (notifier.STATUS_ATTENTION, marker),
                )

    def test_classifier_missing_message_is_attention(self) -> None:
        self.assertEqual(
            notifier.classify_outcome(""),
            (notifier.STATUS_ATTENTION, "missing_message"),
        )

    def test_database_fallback_never_speaks_raw_user_prompt_title(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database = Path(temp_dir) / "state.sqlite"
            connection = notifier.sqlite3.connect(database)
            connection.execute("CREATE TABLE threads (id TEXT PRIMARY KEY, title TEXT, cwd TEXT)")
            connection.execute(
                "INSERT INTO threads VALUES (?, ?, ?)",
                ("thread-1", "交易系统任务", "/tmp/trading"),
            )
            connection.commit()
            connection.close()
            with mock.patch.object(notifier, "STATE_DATABASES", (database,)):
                title, source = notifier.resolve_thread_title("thread-1", "/tmp/fallback")
            self.assertEqual(title, "trading")
            self.assertEqual(source, "thread_db_cwd")

    def test_session_index_title_has_priority_and_uses_latest_name(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            index_path = Path(temp_dir) / "session_index.jsonl"
            index_path.write_text(
                "\n".join(
                    (
                        json.dumps(
                            {"id": "thread-1", "thread_name": "旧名称"},
                            ensure_ascii=False,
                        ),
                        "invalid-json",
                        json.dumps(
                            {"id": "thread-1", "thread_name": "修复 Codex 完成通知"},
                            ensure_ascii=False,
                        ),
                    )
                ),
                encoding="utf-8",
            )
            with (
                mock.patch.object(notifier, "SESSION_INDEX_PATH", index_path),
                mock.patch.object(notifier, "STATE_DATABASES", (Path("/missing"),)),
            ):
                title, source = notifier.resolve_thread_title(
                    "thread-1", "/tmp/fallback"
                )
            self.assertEqual(title, "修复 Codex 完成通知")
            self.assertEqual(source, "session_index")

    def test_internal_thread_detection_covers_spawn_edge_and_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database = Path(temp_dir) / "state.sqlite"
            connection = notifier.sqlite3.connect(database)
            connection.execute(
                "CREATE TABLE threads ("
                "id TEXT PRIMARY KEY, thread_source TEXT, source TEXT)"
            )
            connection.execute(
                "CREATE TABLE thread_spawn_edges ("
                "parent_thread_id TEXT, child_thread_id TEXT PRIMARY KEY, status TEXT)"
            )
            connection.executemany(
                "INSERT INTO threads VALUES (?, ?, ?)",
                (
                    ("root", "user", "vscode"),
                    ("source-child", "subagent", "vscode"),
                    (
                        "json-child",
                        "",
                        json.dumps({"subagent": {"thread_spawn": {}}}),
                    ),
                    ("edge-child", "", "vscode"),
                ),
            )
            connection.execute(
                "INSERT INTO thread_spawn_edges VALUES (?, ?, ?)",
                ("root", "edge-child", "open"),
            )
            connection.commit()
            connection.close()
            with mock.patch.object(notifier, "STATE_DATABASES", (database,)):
                self.assertFalse(notifier.is_internal_thread("root"))
                self.assertTrue(notifier.is_internal_thread("source-child"))
                self.assertTrue(notifier.is_internal_thread("json-child"))
                self.assertTrue(notifier.is_internal_thread("edge-child"))

    def test_internal_thread_completion_is_silent(self) -> None:
        payload = json.dumps(
            {
                "type": "agent-turn-complete",
                "thread-id": "subagent-thread",
                "turn-id": "subagent-turn",
                "last-assistant-message": "任务已完成。",
            }
        )
        with (
            mock.patch.object(notifier, "is_internal_thread", return_value=True),
            mock.patch.object(notifier, "resolve_thread_title") as resolve_title,
            mock.patch.object(notifier, "append_event") as append_event,
            mock.patch.object(notifier, "launch_worker") as launch_worker,
        ):
            self.assertEqual(notifier.handle_notify(payload), 0)
        resolve_title.assert_not_called()
        launch_worker.assert_not_called()
        append_event.assert_called_once_with(
            {
                "status": "ignored_internal_thread",
                "turn_id": "subagent-turn",
                "thread_id": "subagent-thread",
            }
        )

    def test_missing_thread_falls_back_to_cwd(self) -> None:
        with mock.patch.object(notifier, "STATE_DATABASES", (Path("/missing"),)):
            title, source = notifier.resolve_thread_title("missing", "/tmp/ecommerce")
        self.assertEqual(title, "ecommerce")
        self.assertEqual(source, "payload_cwd")

    def test_duplicate_is_suppressed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = Path(temp_dir)
            with (
                mock.patch.object(notifier, "RUNTIME_DIR", runtime),
                mock.patch.object(notifier, "STATE_PATH", runtime / "state.json"),
                mock.patch.object(notifier, "LOCK_PATH", runtime / "sound.lock"),
                mock.patch.object(notifier, "EVENT_LOG_PATH", runtime / "events.jsonl"),
                mock.patch.object(notifier, "play_sound", return_value=True) as sound,
                mock.patch.object(notifier, "speak", return_value=True),
            ):
                notifier.worker(
                    "turn-1",
                    "thread-1",
                    "交易系统",
                    "test",
                    notifier.STATUS_SUCCESS,
                )
                notifier.worker(
                    "turn-1",
                    "thread-1",
                    "交易系统",
                    "test",
                    notifier.STATUS_SUCCESS,
                )
            self.assertEqual(sound.call_count, 1)
            self.assertEqual(sound.call_args.args[0], notifier.STATUS_SUCCESS)

    def test_worker_can_play_only_the_classified_sound_when_speech_is_off(self) -> None:
        calls = []
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = Path(temp_dir)
            with (
                mock.patch.object(notifier, "RUNTIME_DIR", runtime),
                mock.patch.object(notifier, "STATE_PATH", runtime / "state.json"),
                mock.patch.object(notifier, "LOCK_PATH", runtime / "sound.lock"),
                mock.patch.object(notifier, "EVENT_LOG_PATH", runtime / "events.jsonl"),
                mock.patch.object(
                    notifier,
                    "play_sound",
                    side_effect=lambda status, settings=None: calls.append(
                        ("sound", status, settings)
                    )
                    or True,
                ),
                mock.patch.object(
                    notifier,
                    "load_settings",
                    return_value={**notifier.DEFAULT_SETTINGS, "speech_enabled": False},
                ),
                mock.patch.object(notifier, "speak") as speak,
            ):
                notifier.worker(
                    "turn-order",
                    "thread-order",
                    "内容系统",
                    "test",
                    notifier.STATUS_ATTENTION,
                )
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0:2], ("sound", notifier.STATUS_ATTENTION))
        speak.assert_not_called()

    def test_sound_failure_is_logged_without_retry_and_speech_still_runs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = Path(temp_dir)
            with (
                mock.patch.object(notifier, "RUNTIME_DIR", runtime),
                mock.patch.object(notifier, "STATE_PATH", runtime / "state.json"),
                mock.patch.object(notifier, "LOCK_PATH", runtime / "sound.lock"),
                mock.patch.object(notifier, "EVENT_LOG_PATH", runtime / "events.jsonl"),
                mock.patch.object(
                    notifier, "load_settings", return_value=notifier.DEFAULT_SETTINGS
                ),
                mock.patch.object(notifier, "play_sound", return_value=False),
                mock.patch.object(notifier, "speak", return_value=True) as speak,
            ):
                notifier.worker(
                    "turn-sound-failure",
                    "thread-sound-failure",
                    "交易系统",
                    "test",
                    notifier.STATUS_SUCCESS,
                )
            completed = json.loads(
                (runtime / "events.jsonl").read_text(encoding="utf-8").splitlines()[-1]
            )
            self.assertEqual(completed["status"], "notification_partial_failure")
            self.assertFalse(completed["sound_played"])
            self.assertTrue(completed["speech_spoken"])
            speak.assert_called_once_with(
                "交易系统。任务已完成。",
                settings=notifier.DEFAULT_SETTINGS,
                classification=notifier.STATUS_SUCCESS,
            )

    def test_worker_loads_settings_once_and_logs_only_safe_profile(self) -> None:
        runtime_settings = {
            **notifier.DEFAULT_SETTINGS,
            "effect_volume": 0.4,
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = Path(temp_dir)
            with (
                mock.patch.object(notifier, "RUNTIME_DIR", runtime),
                mock.patch.object(notifier, "STATE_PATH", runtime / "state.json"),
                mock.patch.object(notifier, "LOCK_PATH", runtime / "sound.lock"),
                mock.patch.object(notifier, "EVENT_LOG_PATH", runtime / "events.jsonl"),
                mock.patch.object(
                    notifier, "load_settings", return_value=runtime_settings
                ) as load_settings,
                mock.patch.object(notifier, "play_sound", return_value=True),
                mock.patch.object(notifier, "speak", return_value=True),
            ):
                notifier.worker(
                    "turn-profile",
                    "thread-profile",
                    "交易系统",
                    "test",
                    notifier.STATUS_SUCCESS,
                )
            events = [
                json.loads(line)
                for line in (runtime / "events.jsonl").read_text(
                    encoding="utf-8"
                ).splitlines()
            ]
        load_settings.assert_called_once_with()
        started = next(event for event in events if event["status"] == "notification_started")
        self.assertEqual(started["sound"], "warm-chime.wav")
        self.assertEqual(started["effect_volume"], 0.4)
        self.assertNotIn("phrase", started)
        self.assertNotIn("voice", started)
        self.assertEqual(started["voice_profile"], "warm_female")
        self.assertEqual(started["speech_content"], "title_status")

    def test_worker_speaks_task_name_after_status_sound(self) -> None:
        calls = []
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = Path(temp_dir)
            with (
                mock.patch.object(notifier, "RUNTIME_DIR", runtime),
                mock.patch.object(notifier, "STATE_PATH", runtime / "state.json"),
                mock.patch.object(notifier, "LOCK_PATH", runtime / "sound.lock"),
                mock.patch.object(notifier, "EVENT_LOG_PATH", runtime / "events.jsonl"),
                mock.patch.object(
                    notifier, "load_settings", return_value=notifier.DEFAULT_SETTINGS
                ),
                mock.patch.object(
                    notifier,
                    "play_sound",
                    side_effect=lambda status, settings=None: calls.append(("sound", status)) or True,
                ),
                mock.patch.object(
                    notifier,
                    "speak",
                    side_effect=lambda phrase, settings=None, classification="success": calls.append(
                        ("speech", phrase, settings, classification)
                    )
                    or True,
                ),
            ):
                notifier.worker(
                    "turn-spoken",
                    "thread-spoken",
                    "电商系统",
                    "test",
                    notifier.STATUS_SUCCESS,
                )
        self.assertEqual(
            calls,
            [
                ("sound", notifier.STATUS_SUCCESS),
                (
                    "speech",
                    "电商系统。任务已完成。",
                    notifier.DEFAULT_SETTINGS,
                    notifier.STATUS_SUCCESS,
                ),
            ],
        )

    def test_sound_timeout_is_non_fatal(self) -> None:
        with mock.patch.object(
            notifier.subprocess,
            "run",
            side_effect=notifier.subprocess.TimeoutExpired("afplay", 10),
        ):
            self.assertFalse(notifier.play_sound(notifier.STATUS_SUCCESS))

    def test_speech_profile_changes_tempo_by_status(self) -> None:
        settings = {**notifier.DEFAULT_SETTINGS, "voice_profile": "calm_male"}
        success_voice, success_rate = notifier.speech_profile(
            settings, notifier.STATUS_SUCCESS
        )
        attention_voice, attention_rate = notifier.speech_profile(
            settings, notifier.STATUS_ATTENTION
        )
        self.assertEqual(success_voice, "Reed (Chinese (China mainland))")
        self.assertEqual(success_voice, attention_voice)
        self.assertGreater(success_rate, attention_rate)

    def test_speech_render_is_cached_owner_only_and_reused(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = Path(temp_dir)

            def fake_run(command, **_kwargs):
                output = Path(command[command.index("-o") + 1])
                output.write_bytes(b"FORMfake-aiff")
                return mock.Mock(returncode=0)

            with (
                mock.patch.object(notifier, "RUNTIME_DIR", runtime),
                mock.patch.object(notifier.subprocess, "run", side_effect=fake_run) as run,
            ):
                first = notifier.render_speech_file(
                    "交易系统。任务已完成。", "Sandy", 181
                )
                second = notifier.render_speech_file(
                    "交易系统。任务已完成。", "Sandy", 181
                )

            self.assertEqual(first, second)
            self.assertIsNotNone(first)
            self.assertEqual(run.call_count, 1)
            self.assertEqual(stat.S_IMODE(first.stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE(first.parent.stat().st_mode), 0o700)

    def test_speak_plays_cached_file_then_falls_back_if_render_fails(self) -> None:
        completed = mock.Mock(returncode=0)
        with tempfile.TemporaryDirectory() as temp_dir:
            rendered = Path(temp_dir) / "speech.aiff"
            rendered.write_bytes(b"audio")
            with (
                mock.patch.object(notifier, "render_speech_file", return_value=rendered),
                mock.patch.object(notifier.subprocess, "run", return_value=completed) as run,
            ):
                self.assertTrue(
                    notifier.speak(
                        "任务已完成。",
                        settings=notifier.DEFAULT_SETTINGS,
                        classification=notifier.STATUS_SUCCESS,
                    )
                )
            self.assertEqual(run.call_args.args[0], ["/usr/bin/afplay", str(rendered)])

        with (
            mock.patch.object(notifier, "render_speech_file", return_value=None),
            mock.patch.object(notifier.subprocess, "run", return_value=completed) as run,
        ):
            self.assertTrue(
                notifier.speak(
                    "任务已完成。",
                    settings=notifier.DEFAULT_SETTINGS,
                    classification=notifier.STATUS_SUCCESS,
                )
            )
        self.assertEqual(
            run.call_args.args[0],
            [
                "/usr/bin/say",
                "-v",
                notifier.FALLBACK_VOICE,
                "-r",
                str(notifier.FALLBACK_SPEECH_RATE),
                "任务已完成。",
            ],
        )

    def test_saved_settings_control_runtime_commands(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            success_sound = root / "celebrate.wav"
            attention_sound = root / "calm.wav"
            success_sound.write_bytes(b"audio")
            attention_sound.write_bytes(b"audio")
            settings_path = root / "settings.json"
            notifier.save_settings(
                {
                    "success_sound": str(success_sound),
                    "attention_sound": str(attention_sound),
                    "effect_volume": 0.45,
                },
                path=settings_path,
            )
            completed = mock.Mock(returncode=0)
            with (
                mock.patch.object(notifier, "SETTINGS_PATH", settings_path),
                mock.patch.object(notifier.subprocess, "run", return_value=completed) as run,
            ):
                self.assertTrue(notifier.play_sound(notifier.STATUS_SUCCESS))
        self.assertEqual(
            run.call_args_list[0].args[0],
            ["/usr/bin/afplay", "-v", "0.45", str(success_sound.resolve())],
        )
        self.assertEqual(len(run.call_args_list), 1)

    def test_preview_uses_only_the_unsaved_candidate_sound(self) -> None:
        candidate = {
            **notifier.DEFAULT_SETTINGS,
            "effect_volume": 0.55,
        }
        calls = []
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = Path(temp_dir)
            with (
                mock.patch.object(notifier, "RUNTIME_DIR", runtime),
                mock.patch.object(notifier, "LOCK_PATH", runtime / "sound.lock"),
                mock.patch.object(notifier, "EVENT_LOG_PATH", runtime / "events.jsonl"),
                mock.patch.object(
                    notifier, "normalize_settings", return_value=candidate
                ),
                mock.patch.object(
                    notifier,
                    "play_sound",
                    side_effect=lambda status, settings=None: calls.append(
                        ("sound", status, settings)
                    )
                    or True,
                ),
            ):
                result = notifier.preview_sound(notifier.STATUS_ATTENTION, candidate)
        self.assertTrue(result)
        self.assertEqual(calls, [("sound", notifier.STATUS_ATTENTION, candidate)])

    def test_speech_preview_is_separate_from_sound_preview(self) -> None:
        candidate = {**notifier.DEFAULT_SETTINGS, "speech_enabled": True}
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = Path(temp_dir)
            with (
                mock.patch.object(notifier, "RUNTIME_DIR", runtime),
                mock.patch.object(notifier, "LOCK_PATH", runtime / "sound.lock"),
                mock.patch.object(notifier, "EVENT_LOG_PATH", runtime / "events.jsonl"),
                mock.patch.object(notifier, "play_sound") as play_sound,
                mock.patch.object(notifier, "speak", return_value=True) as speak,
            ):
                result = notifier.preview_speech(
                    "交易系统", notifier.STATUS_ATTENTION, candidate
                )
        self.assertTrue(result)
        play_sound.assert_not_called()
        speak.assert_called_once_with(
            "交易系统。任务已结束，但还有事项需要确认。",
            settings=candidate,
            classification=notifier.STATUS_ATTENTION,
        )

    def test_process_lock_serializes_workers(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = str(Path(temp_dir) / "intervals.jsonl")
            processes = [
                multiprocessing.Process(
                    target=actual_worker_interval,
                    args=(temp_dir, output_path, label),
                )
                for label in ("one", "two")
            ]
            for process in processes:
                process.start()
            for process in processes:
                process.join(timeout=3)
                self.assertEqual(process.exitcode, 0)
            records = [
                json.loads(line)
                for line in Path(output_path).read_text(encoding="utf-8").splitlines()
            ]
            self.assertEqual(len(records), 2)
            intervals = [record for record in records if record["kind"] == "sound"]
            intervals.sort(key=lambda item: item["start"])
            self.assertGreaterEqual(intervals[1]["start"], intervals[0]["end"])
            state = json.loads(
                (Path(temp_dir) / "state.json").read_text(encoding="utf-8")
            )
            self.assertCountEqual(state["seen_turn_ids"], ["turn-one", "turn-two"])

    def test_handle_notify_passes_only_classification_to_worker(self) -> None:
        payload = json.dumps(
            {
                "type": "agent-turn-complete",
                "thread-id": "thread-1",
                "turn-id": "turn-1",
                "cwd": "/tmp/trading",
                "last-assistant-message": "Missing evidence: screenshot",
            }
        )
        with (
            mock.patch.object(
                notifier,
                "resolve_thread_title",
                return_value=("交易系统", "test_db"),
            ),
            mock.patch.object(notifier, "append_event") as append_event,
            mock.patch.object(notifier, "launch_worker") as launch_worker,
        ):
            self.assertEqual(notifier.handle_notify(payload), 0)
        launch_worker.assert_called_once_with(
            "turn-1",
            "thread-1",
            "交易系统",
            "test_db",
            notifier.STATUS_ATTENTION,
        )
        classification_event = append_event.call_args.args[0]
        self.assertEqual(classification_event["classifier_marker"], "missing_evidence")
        self.assertNotIn("last-assistant-message", classification_event)


if __name__ == "__main__":
    unittest.main()
