from __future__ import annotations

import json
from pathlib import Path

from kivy.app import App
from kivy.utils import platform


def open_notification_listener_settings() -> bool:
    if platform != "android":
        return False

    from jnius import autoclass

    PythonActivity = autoclass("org.kivy.android.PythonActivity")
    Intent = autoclass("android.content.Intent")
    Settings = autoclass("android.provider.Settings")

    activity = PythonActivity.mActivity
    intent = Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS)
    activity.startActivity(intent)
    return True


def read_captured_notifications() -> tuple[list[dict[str, object]], int]:
    path = _notification_file_path()
    if path is None or not path.exists():
        return [], 0

    app = App.get_running_app()
    repository = getattr(app.root, "repository", None) if app and app.root else None
    offset = int(repository.get_state("notification_file_offset", "0")) if repository else 0

    records: list[dict[str, object]] = []
    with path.open("rb") as handle:
        handle.seek(offset)
        for raw_line in handle:
            try:
                records.append(json.loads(raw_line.decode("utf-8").strip()))
            except json.JSONDecodeError:
                continue
        new_offset = handle.tell()
    return records, new_offset


def _notification_file_path() -> Path | None:
    app = App.get_running_app()
    if app is None:
        return None
    return Path(app.user_data_dir) / "captured_notifications.jsonl"
