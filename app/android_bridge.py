from __future__ import annotations

import json
import time
from pathlib import Path

from kivy.app import App
from kivy.utils import platform

_PDF_PICKER_REQUEST_CODE = 48261
_pdf_picker_callback = None
_pdf_picker_bound = False
_pdf_picker_flags = 0


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


def open_pdf_picker(on_selection) -> bool:
    if platform != "android":
        return False

    from android import activity
    from jnius import autoclass, cast

    global _pdf_picker_callback, _pdf_picker_bound
    _pdf_picker_callback = on_selection

    if not _pdf_picker_bound:
        activity.bind(on_activity_result=_on_pdf_picker_result)
        _pdf_picker_bound = True

    PythonActivity = autoclass("org.kivy.android.PythonActivity")
    Intent = autoclass("android.content.Intent")
    String = autoclass("java.lang.String")

    chooser_intent = Intent(Intent.ACTION_OPEN_DOCUMENT)
    chooser_intent.setType("application/pdf")
    chooser_intent.addCategory(Intent.CATEGORY_OPENABLE)
    chooser_intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
    chooser_intent.addFlags(Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION)

    activity_instance = PythonActivity.mActivity
    activity_instance.startActivityForResult(
        Intent.createChooser(
            chooser_intent,
            cast("java.lang.CharSequence", String("Choose Statement PDF")),
        ),
        _PDF_PICKER_REQUEST_CODE,
    )
    return True


def materialize_selected_pdf(selection: str) -> Path | None:
    if not selection:
        return None

    raw = str(selection).strip()
    if not raw:
        return None

    direct_path = Path(raw)
    if direct_path.exists():
        return direct_path

    if platform != "android" or not raw.startswith("content://"):
        return None

    from jnius import autoclass, JavaException

    PythonActivity = autoclass("org.kivy.android.PythonActivity")
    Uri = autoclass("android.net.Uri")
    Intent = autoclass("android.content.Intent")

    activity = PythonActivity.mActivity
    resolver = activity.getContentResolver()
    uri = Uri.parse(raw)
    try:
        permission_flags = _pdf_picker_flags & Intent.FLAG_GRANT_READ_URI_PERMISSION
        if permission_flags:
            resolver.takePersistableUriPermission(uri, permission_flags)
    except JavaException:
        pass

    try:
        input_stream = resolver.openInputStream(uri)
    except JavaException as exc:
        raise RuntimeError(f"Could not open selected PDF URI: {exc}") from None
    if input_stream is None:
        raise RuntimeError("Could not open selected PDF URI.")

    app = App.get_running_app()
    if app is None:
        return None

    imports_dir = Path(app.user_data_dir) / "imports"
    imports_dir.mkdir(parents=True, exist_ok=True)
    destination = imports_dir / f"statement_{int(time.time() * 1000)}.pdf"

    try:
        with destination.open("wb") as output_stream:
            while True:
                value = input_stream.read()
                if value == -1:
                    break
                output_stream.write(bytes((value,)))
    finally:
        try:
            input_stream.close()
        except Exception:
            pass

    return destination


def get_pdf_display_name(selection: str) -> str | None:
    raw = str(selection).strip()
    if not raw:
        return None

    direct_path = Path(raw)
    if direct_path.exists():
        return direct_path.name

    if platform != "android" or not raw.startswith("content://"):
        return None

    from jnius import autoclass, JavaException

    PythonActivity = autoclass("org.kivy.android.PythonActivity")
    Uri = autoclass("android.net.Uri")
    OpenableColumns = autoclass("android.provider.OpenableColumns")

    activity = PythonActivity.mActivity
    resolver = activity.getContentResolver()
    uri = Uri.parse(raw)

    cursor = None
    try:
        cursor = resolver.query(uri, None, None, None, None)
        if cursor is None or not cursor.moveToFirst():
            return None
        column_index = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME)
        if column_index < 0:
            return None
        display_name = cursor.getString(column_index)
        return str(display_name) if display_name else None
    except JavaException:
        return None
    finally:
        if cursor is not None:
            try:
                cursor.close()
            except Exception:
                pass


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


def _on_pdf_picker_result(request_code, result_code, intent) -> None:
    if request_code != _PDF_PICKER_REQUEST_CODE:
        return

    global _pdf_picker_flags
    callback = _pdf_picker_callback
    if callback is None:
        return

    try:
        if intent is None:
            callback([])
            return

        uri = intent.getData()
        if uri is None:
            callback([])
            return

        _pdf_picker_flags = intent.getFlags()
        callback([str(uri.toString())])
    except Exception:
        callback([])
