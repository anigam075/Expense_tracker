from __future__ import annotations

import tempfile
import traceback
from pathlib import Path

from app.app import ExpenseTrackerApp


if __name__ == "__main__":
    try:
        ExpenseTrackerApp().run()
    except Exception:
        error_text = traceback.format_exc()
        for directory in (Path(tempfile.gettempdir()), Path.cwd()):
            try:
                directory.mkdir(parents=True, exist_ok=True)
                (directory / "expense_tracker_fatal.log").write_text(error_text, encoding="utf-8")
                break
            except OSError:
                continue
        raise
