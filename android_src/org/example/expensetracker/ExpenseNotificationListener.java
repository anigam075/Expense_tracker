package org.example.expensetracker;

import android.app.Notification;
import android.os.Bundle;
import android.service.notification.NotificationListenerService;
import android.service.notification.StatusBarNotification;

import org.json.JSONObject;

import java.io.File;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;

public class ExpenseNotificationListener extends NotificationListenerService {
    @Override
    public void onNotificationPosted(StatusBarNotification sbn) {
        try {
            Notification notification = sbn.getNotification();
            if (notification == null) {
                return;
            }

            Bundle extras = notification.extras;
            String title = extras != null ? String.valueOf(extras.getCharSequence(Notification.EXTRA_TITLE, "")) : "";
            String text = extras != null ? String.valueOf(extras.getCharSequence(Notification.EXTRA_TEXT, "")) : "";
            CharSequence bigTextValue = extras != null ? extras.getCharSequence(Notification.EXTRA_BIG_TEXT) : null;
            String bigText = bigTextValue != null ? bigTextValue.toString() : "";

            String combinedText = (title + " " + text + " " + bigText).trim();
            if (combinedText.isEmpty()) {
                return;
            }

            JSONObject payload = new JSONObject();
            payload.put("package_name", sbn.getPackageName());
            payload.put("title", title);
            payload.put("text", text);
            payload.put("big_text", bigText);
            payload.put("posted_at", sbn.getPostTime());

            File appDir = new File(getFilesDir(), "app");
            if (!appDir.exists()) {
                appDir.mkdirs();
            }
            File outFile = new File(appDir, "captured_notifications.jsonl");
            FileOutputStream outputStream = new FileOutputStream(outFile, true);
            outputStream.write((payload.toString() + "\n").getBytes(StandardCharsets.UTF_8));
            outputStream.close();
        } catch (Exception ignored) {
        }
    }
}
