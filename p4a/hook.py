from pathlib import Path
import xml.etree.ElementTree as ET


ANDROID_NS = "http://schemas.android.com/apk/res/android"
ET.register_namespace("android", ANDROID_NS)

SERVICE_NAME = "org.example.expensetracker.ExpenseNotificationListener"
SERVICE_LABEL = "Expense Tracker Notifications"
SERVICE_PERMISSION = (
    "android.permission.BIND_NOTIFICATION_LISTENER_SERVICE"
)
LISTENER_ACTION = "android.service.notification.NotificationListenerService"


def _android_attr(name: str) -> str:
    return f"{{{ANDROID_NS}}}{name}"


def _ensure_notification_listener(manifest_path: Path) -> None:
    tree = ET.parse(manifest_path)
    root = tree.getroot()
    application = root.find("application")
    if application is None:
        raise RuntimeError("AndroidManifest.xml is missing <application>")

    existing = application.findall("service")
    for service in existing:
        if service.get(_android_attr("name")) == SERVICE_NAME:
            return

    service = ET.Element("service")
    service.set(_android_attr("name"), SERVICE_NAME)
    service.set(_android_attr("label"), SERVICE_LABEL)
    service.set(_android_attr("permission"), SERVICE_PERMISSION)
    service.set(_android_attr("exported"), "false")

    intent_filter = ET.SubElement(service, "intent-filter")
    action = ET.SubElement(intent_filter, "action")
    action.set(_android_attr("name"), LISTENER_ACTION)

    application.append(service)
    tree.write(manifest_path, encoding="utf-8", xml_declaration=True)


def after_apk_build(toolchain) -> None:
    manifest_path = (
        Path(toolchain._dist.dist_dir) / "src" / "main" / "AndroidManifest.xml"
    )
    if not manifest_path.exists():
        raise FileNotFoundError(
            f"Generated AndroidManifest.xml not found: {manifest_path}"
        )

    _ensure_notification_listener(manifest_path)
