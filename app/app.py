from __future__ import annotations

import tempfile
import traceback
from datetime import date
from pathlib import Path

from kivy.app import App
from kivy.lang import Builder
from kivy.properties import ListProperty, ObjectProperty, StringProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label

from app.database import ExpenseRepository
from app.models import ExpenseRecord

KV = """
<ExpenseForm>:
    orientation: "vertical"
    spacing: "12dp"
    padding: "16dp"
    canvas.before:
        Color:
            rgba: 0.96, 0.94, 0.9, 1
        Rectangle:
            pos: self.pos
            size: self.size

    Label:
        text: "Expense Tracker"
        size_hint_y: None
        height: "40dp"
        font_size: "26sp"
        bold: True
        color: 0.14, 0.18, 0.16, 1

    Label:
        text: root.feedback_message
        size_hint_y: None
        height: "24dp"
        color: root.feedback_color

    GridLayout:
        cols: 2
        size_hint_y: None
        height: self.minimum_height
        row_default_height: "46dp"
        row_force_default: True
        spacing: "10dp"

        Label:
            text: "Amount"
            halign: "left"
            text_size: self.size
            color: 0.14, 0.18, 0.16, 1
        TextInput:
            id: amount_input
            multiline: False
            hint_text: "e.g. 245.50"
            input_filter: "float"

        Label:
            text: "Merchant"
            halign: "left"
            text_size: self.size
            color: 0.14, 0.18, 0.16, 1
        TextInput:
            id: merchant_input
            multiline: False
            hint_text: "Where did you spend?"

        Label:
            text: "Payment Method"
            halign: "left"
            text_size: self.size
            color: 0.14, 0.18, 0.16, 1
        Spinner:
            id: payment_method_input
            text: "UPI"
            values: ["UPI", "Card", "Cash", "Net Banking", "Wallet", "Other"]

        Label:
            text: "Date"
            halign: "left"
            text_size: self.size
            color: 0.14, 0.18, 0.16, 1
        TextInput:
            id: date_input
            multiline: False
            hint_text: "YYYY-MM-DD"
            text: root.default_date

        Label:
            text: "Notes"
            halign: "left"
            text_size: self.size
            valign: "top"
            color: 0.14, 0.18, 0.16, 1
        TextInput:
            id: notes_input
            hint_text: "Optional details"

    Button:
        text: "Save Expense"
        size_hint_y: None
        height: "48dp"
        background_normal: ""
        background_color: 0.18, 0.5, 0.32, 1
        on_release: root.save_expense()

    Label:
        text: "Recent Expenses"
        size_hint_y: None
        height: "32dp"
        font_size: "20sp"
        bold: True
        color: 0.14, 0.18, 0.16, 1

    ScrollView:
        do_scroll_x: False

        GridLayout:
            cols: 1
            size_hint_y: None
            height: self.minimum_height
            spacing: "8dp"
            padding: 0, 0, 0, "12dp"

            canvas.before:
                Color:
                    rgba: 1, 1, 1, 0
                Rectangle:
                    pos: self.pos
                    size: self.size

            Label:
                size_hint_y: None
                height: self.texture_size[1] if self.texture_size[1] > 0 else "24dp"
                text_size: self.width, None
                halign: "left"
                valign: "top"
                color: 0.22, 0.25, 0.24, 1
                text: root.recent_expenses_text
"""


class ExpenseForm(BoxLayout):
    repository = ObjectProperty(allownone=False)
    feedback_message = StringProperty("Fill in the details and save the expense.")
    recent_expenses_text = StringProperty("No expenses saved yet.")
    default_date = StringProperty(date.today().isoformat())
    feedback_color = ListProperty([0.13, 0.42, 0.23, 1])

    def on_kv_post(self, _base_widget) -> None:
        self.refresh_recent_expenses()

    def save_expense(self) -> None:
        amount_text = self.ids.amount_input.text.strip()
        merchant = self.ids.merchant_input.text.strip()
        payment_method = self.ids.payment_method_input.text.strip()
        expense_date = self.ids.date_input.text.strip()
        notes = self.ids.notes_input.text.strip()

        if not amount_text or not merchant or not expense_date:
            self._set_feedback("Please enter amount, merchant, and date.", is_error=True)
            return

        try:
            amount = float(amount_text)
        except ValueError:
            self._set_feedback("Please enter a valid amount.", is_error=True)
            return

        if amount <= 0:
            self._set_feedback("Please enter an amount greater than zero.", is_error=True)
            return

        try:
            date.fromisoformat(expense_date)
        except ValueError:
            self._set_feedback("Please use the date format YYYY-MM-DD.", is_error=True)
            return

        expense = ExpenseRecord(
            id=None,
            amount=amount,
            merchant=merchant,
            payment_method=payment_method,
            expense_date=expense_date,
            notes=notes,
        )
        saved_expense = self.repository.add_expense(expense)
        self._set_feedback(
            f"Saved Rs. {saved_expense.amount:.2f} for {saved_expense.merchant}.",
            is_error=False,
        )
        self._clear_inputs()
        self.refresh_recent_expenses()

    def refresh_recent_expenses(self) -> None:
        expenses = self.repository.list_recent_expenses()
        if not expenses:
            self.recent_expenses_text = "No expenses saved yet."
            return

        self.recent_expenses_text = "\n\n".join(
            f"{expense.expense_date}  |  Rs. {expense.amount:.2f}\n"
            f"{expense.merchant} via {expense.payment_method}"
            + (f"\n{expense.notes}" if expense.notes else "")
            for expense in expenses
        )

    def _clear_inputs(self) -> None:
        self.ids.amount_input.text = ""
        self.ids.merchant_input.text = ""
        self.ids.payment_method_input.text = "UPI"
        self.ids.date_input.text = self.default_date
        self.ids.notes_input.text = ""

    def _set_feedback(self, message: str, *, is_error: bool) -> None:
        self.feedback_message = message
        self.feedback_color = [0.78, 0.24, 0.18, 1] if is_error else [0.13, 0.42, 0.23, 1]


class ExpenseTrackerApp(App):
    title = "Expense Tracker"

    def build(self) -> ExpenseForm | Label:
        try:
            Builder.load_string(KV)
            repository = ExpenseRepository(Path(self.user_data_dir) / "expenses.db")
            return ExpenseForm(repository=repository)
        except Exception:
            error_text = traceback.format_exc()
            crash_path = self._write_crash_log(error_text)
            message = (
                "Startup failed.\n\n"
                f"Crash log: {crash_path}\n\n"
                f"{error_text}"
            )
            return Label(text=message, halign="left", valign="top", text_size=(0, 0))

    def _write_crash_log(self, error_text: str) -> str:
        candidates: list[Path] = []
        user_dir = getattr(self, "user_data_dir", "")
        if user_dir:
            candidates.append(Path(user_dir))
        candidates.append(Path(tempfile.gettempdir()))
        candidates.append(Path.cwd())

        for directory in candidates:
            try:
                directory.mkdir(parents=True, exist_ok=True)
                log_path = directory / "expense_tracker_crash.log"
                log_path.write_text(error_text, encoding="utf-8")
                return str(log_path)
            except OSError:
                continue

        return "unable to write crash log"
