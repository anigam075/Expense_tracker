from __future__ import annotations

import calendar
import tempfile
import traceback
from datetime import date
from pathlib import Path

from kivy.app import App
from kivy.core.window import Window
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import ListProperty, NumericProperty, ObjectProperty, StringProperty
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.modalview import ModalView
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import Screen, ScreenManager
from kivy.uix.spinner import Spinner

from app.database import ExpenseRepository
from app.models import ExpenseRecord

KV = """
#:import dp kivy.metrics.dp

<ExpenseRow>:
    action_button: action_button
    size_hint_y: None
    height: "118dp"
    padding: 0, "5dp", 0, "5dp"
    canvas.before:
        Color:
            rgba: 1, 1, 1, 1
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [22, 22, 22, 22]
        Color:
            rgba: 0.88, 0.92, 0.9, 1
        Line:
            rounded_rectangle: [self.x, self.y, self.width, self.height, 22]
            width: 1.1

    BoxLayout:
        padding: "14dp"
        spacing: "14dp"

        BoxLayout:
            orientation: "vertical"
            spacing: "4dp"

            BoxLayout:
                size_hint_y: None
                height: "24dp"
                spacing: "8dp"

                Label:
                    text: root.method_text
                    size_hint_x: None
                    width: "76dp"
                    halign: "center"
                    valign: "middle"
                    text_size: self.size
                    font_size: "13sp"
                    color: 0.11, 0.31, 0.21, 1
                    bold: True
                    canvas.before:
                        Color:
                            rgba: 0.86, 0.94, 0.89, 1
                        RoundedRectangle:
                            pos: self.pos
                            size: self.size
                            radius: [13, 13, 13, 13]

                Label:
                    text: root.date_text
                    halign: "left"
                    valign: "middle"
                    text_size: self.size
                    font_size: "13sp"
                    color: 0.42, 0.47, 0.45, 1

            Label:
                text: root.merchant_text
                size_hint_y: None
                height: "30dp"
                halign: "left"
                valign: "middle"
                text_size: self.width, None
                shorten: True
                shorten_from: "right"
                font_size: "20sp"
                bold: True
                color: 0.13, 0.16, 0.15, 1

            Label:
                text: root.note_text
                size_hint_y: None
                height: "22dp"
                halign: "left"
                valign: "middle"
                text_size: self.width, None
                shorten: True
                shorten_from: "right"
                color: 0.53, 0.57, 0.55, 1
                opacity: 1 if root.note_text else 0

        BoxLayout:
            orientation: "vertical"
            size_hint_x: None
            width: "92dp"
            spacing: "8dp"

            Label:
                text: root.amount_text
                size_hint_y: None
                height: "50dp"
                halign: "right"
                valign: "top"
                text_size: self.width, self.height
                font_size: "19sp"
                bold: True
                color: 0.11, 0.31, 0.21, 1

            Widget:

            Button:
                id: action_button
                text: "..."
                size_hint_y: None
                height: "34dp"
                font_size: "18sp"
                bold: True
                background_normal: ""
                background_down: ""
                background_color: 0.93, 0.95, 0.94, 1
                color: 0.14, 0.18, 0.16, 1
                on_release: root.open_actions(self)

<ExpenseListScreen>:
    name: "list"
    BoxLayout:
        orientation: "vertical"
        canvas.before:
            Color:
                rgba: 0.97, 0.95, 0.91, 1
            Rectangle:
                pos: self.pos
                size: self.size

        BoxLayout:
            orientation: "vertical"
            size_hint_y: None
            height: "258dp"
            padding: "18dp"
            spacing: "14dp"
            canvas.before:
                Color:
                    rgba: 0.14, 0.35, 0.27, 1
                RoundedRectangle:
                    pos: self.pos
                    size: self.size
                    radius: [0, 0, 30, 30]

            Label:
                text: "Expense Atlas"
                size_hint_y: None
                height: "34dp"
                halign: "left"
                valign: "middle"
                text_size: self.width, self.height
                font_size: "31sp"
                bold: True
                color: 1, 1, 1, 1

            Label:
                text: "Track every rupee with a cleaner, calmer daily flow."
                size_hint_y: None
                height: "22dp"
                halign: "left"
                valign: "middle"
                text_size: self.width, self.height
                color: 0.84, 0.93, 0.89, 1

            BoxLayout:
                size_hint_y: None
                height: "116dp"
                spacing: "12dp"

                BoxLayout:
                    orientation: "vertical"
                    padding: "14dp"
                    canvas.before:
                        Color:
                            rgba: 0.98, 0.97, 0.94, 1
                        RoundedRectangle:
                            pos: self.pos
                            size: self.size
                            radius: [24, 24, 24, 24]
                    Label:
                        text: "Total Logged"
                        size_hint_y: None
                        height: "22dp"
                        halign: "left"
                        valign: "middle"
                        text_size: self.width, self.height
                        color: 0.47, 0.52, 0.49, 1
                    Label:
                        text: root.total_amount_text
                        halign: "left"
                        valign: "middle"
                        text_size: self.width, self.height
                        font_size: "28sp"
                        bold: True
                        color: 0.13, 0.16, 0.15, 1

                BoxLayout:
                    orientation: "vertical"
                    size_hint_x: 0.42
                    padding: "14dp"
                    canvas.before:
                        Color:
                            rgba: 0.2, 0.48, 0.37, 1
                        RoundedRectangle:
                            pos: self.pos
                            size: self.size
                            radius: [24, 24, 24, 24]
                    Label:
                        text: "Entries"
                        size_hint_y: None
                        height: "22dp"
                        halign: "left"
                        valign: "middle"
                        text_size: self.width, self.height
                        color: 0.86, 0.95, 0.9, 1
                    Label:
                        text: root.expense_count_text
                        halign: "left"
                        valign: "middle"
                        text_size: self.width, self.height
                        font_size: "32sp"
                        bold: True
                        color: 1, 1, 1, 1

            Label:
                text: root.status_message
                size_hint_y: None
                height: "24dp"
                halign: "left"
                valign: "middle"
                text_size: self.width, self.height
                color: root.status_color

        BoxLayout:
            orientation: "vertical"
            padding: "18dp"
            spacing: "14dp"

            BoxLayout:
                size_hint_y: None
                height: "54dp"
                spacing: "12dp"

                Label:
                    text: "Recent Expenses"
                    halign: "left"
                    valign: "middle"
                    text_size: self.size
                    font_size: "23sp"
                    bold: True
                    color: 0.15, 0.18, 0.16, 1

                Button:
                    text: "+ Add Expense"
                    size_hint_x: None
                    width: "152dp"
                    background_normal: ""
                    background_down: ""
                    background_color: 0.21, 0.56, 0.39, 1
                    color: 1, 1, 1, 1
                    bold: True
                    on_release: root.add_expense()

            ScrollView:
                do_scroll_x: False
                bar_width: "4dp"

                BoxLayout:
                    id: list_container
                    orientation: "vertical"
                    size_hint_y: None
                    height: self.minimum_height
                    spacing: "12dp"
                    padding: 0, 0, 0, "20dp"

<ExpenseEditScreen>:
    name: "edit"
    BoxLayout:
        orientation: "vertical"
        canvas.before:
            Color:
                rgba: 0.97, 0.95, 0.91, 1
            Rectangle:
                pos: self.pos
                size: self.size

        ScrollView:
            do_scroll_x: False
            scroll_type: ['bars', 'content']
            bar_width: "4dp"

            BoxLayout:
                size_hint_y: None
                height: max(self.minimum_height, root.height)
                orientation: "vertical"
                padding: 0, 0, 0, "24dp"

                BoxLayout:
                    orientation: "vertical"
                    size_hint_y: None
                    height: "218dp"
                    padding: "18dp"
                    spacing: "12dp"
                    canvas.before:
                        Color:
                            rgba: 0.14, 0.35, 0.27, 1
                        RoundedRectangle:
                            pos: self.pos
                            size: self.size
                            radius: [0, 0, 30, 30]

                    Button:
                        text: "< Back"
                        size_hint: None, None
                        size: "88dp", "34dp"
                        background_normal: ""
                        background_down: ""
                        background_color: 0.22, 0.48, 0.39, 1
                        color: 1, 1, 1, 1
                        on_release: root.cancel()

                    Label:
                        text: root.screen_title
                        size_hint_y: None
                        height: "38dp"
                        halign: "left"
                        valign: "middle"
                        text_size: self.width, self.height
                        font_size: "30sp"
                        bold: True
                        color: 1, 1, 1, 1

                    Label:
                        text: root.feedback_message
                        size_hint_y: None
                        height: "22dp"
                        halign: "left"
                        valign: "middle"
                        text_size: self.width, self.height
                        color: root.feedback_color

                    Label:
                        text: "Keep things quick, clean, and editable."
                        halign: "left"
                        valign: "middle"
                        text_size: self.width, self.height
                        color: 0.84, 0.93, 0.89, 1

                BoxLayout:
                    orientation: "vertical"
                    size_hint_y: None
                    height: self.minimum_height
                    padding: "18dp"
                    spacing: "14dp"

                    BoxLayout:
                        orientation: "vertical"
                        size_hint_y: None
                        height: self.minimum_height
                        padding: "18dp"
                        spacing: "14dp"
                        canvas.before:
                            Color:
                                rgba: 1, 1, 1, 1
                            RoundedRectangle:
                                pos: self.pos
                                size: self.size
                                radius: [26, 26, 26, 26]
                            Color:
                                rgba: 0.88, 0.92, 0.9, 1
                            Line:
                                rounded_rectangle: [self.x, self.y, self.width, self.height, 26]
                                width: 1.1

                        Label:
                            text: "Expense Details"
                            size_hint_y: None
                            height: "26dp"
                            halign: "left"
                            valign: "middle"
                            text_size: self.width, self.height
                            font_size: "21sp"
                            bold: True
                            color: 0.15, 0.18, 0.16, 1

                        Label:
                            text: "Fill the fields below and save when ready."
                            size_hint_y: None
                            height: "20dp"
                            halign: "left"
                            valign: "middle"
                            text_size: self.width, self.height
                            color: 0.48, 0.53, 0.5, 1

                        Label:
                            text: "Amount"
                            size_hint_y: None
                            height: "20dp"
                            color: 0.31, 0.35, 0.33, 1
                        TextInput:
                            id: amount_input
                            size_hint_y: None
                            height: "52dp"
                            multiline: False
                            hint_text: "e.g. 245.50"
                            input_filter: "float"
                            background_normal: ""
                            background_active: ""
                            background_color: 0.96, 0.97, 0.96, 1
                            foreground_color: 0.14, 0.18, 0.16, 1
                            cursor_color: 0.18, 0.5, 0.32, 1
                            padding: "16dp", "15dp"

                        Label:
                            text: "Merchant"
                            size_hint_y: None
                            height: "20dp"
                            color: 0.31, 0.35, 0.33, 1
                        TextInput:
                            id: merchant_input
                            size_hint_y: None
                            height: "52dp"
                            multiline: False
                            hint_text: "Where did you spend?"
                            background_normal: ""
                            background_active: ""
                            background_color: 0.96, 0.97, 0.96, 1
                            foreground_color: 0.14, 0.18, 0.16, 1
                            cursor_color: 0.18, 0.5, 0.32, 1
                            padding: "16dp", "15dp"

                        Label:
                            text: "Payment Method"
                            size_hint_y: None
                            height: "20dp"
                            color: 0.31, 0.35, 0.33, 1
                        Spinner:
                            id: payment_method_input
                            size_hint_y: None
                            height: "52dp"
                            text: "UPI"
                            values: ["UPI", "Card", "Cash", "Net Banking", "Wallet", "Other"]
                            background_normal: ""
                            background_color: 0.2, 0.22, 0.21, 1
                            color: 1, 1, 1, 1

                        Label:
                            text: "Date"
                            size_hint_y: None
                            height: "20dp"
                            color: 0.31, 0.35, 0.33, 1
                        Button:
                            id: date_button
                            size_hint_y: None
                            height: "52dp"
                            text: root.default_date
                            background_normal: ""
                            background_down: ""
                            background_color: 0.96, 0.97, 0.96, 1
                            color: 0.14, 0.18, 0.16, 1
                            on_release: root.open_date_picker()

                        Label:
                            text: "Notes"
                            size_hint_y: None
                            height: "20dp"
                            color: 0.31, 0.35, 0.33, 1
                        TextInput:
                            id: notes_input
                            size_hint_y: None
                            height: "118dp"
                            hint_text: "Optional details"
                            background_normal: ""
                            background_active: ""
                            background_color: 0.96, 0.97, 0.96, 1
                            foreground_color: 0.14, 0.18, 0.16, 1
                            cursor_color: 0.18, 0.5, 0.32, 1
                            padding: "16dp", "15dp"

                    BoxLayout:
                        size_hint_y: None
                        height: "54dp"
                        padding: "18dp", 0
                        spacing: "12dp"

                        Button:
                            text: "Cancel"
                            background_normal: ""
                            background_down: ""
                            background_color: 0.46, 0.51, 0.49, 1
                            color: 1, 1, 1, 1
                            on_release: root.cancel()

                        Button:
                            text: root.action_button_text
                            background_normal: ""
                            background_down: ""
                            background_color: 0.21, 0.56, 0.39, 1
                            color: 1, 1, 1, 1
                            bold: True
                            on_release: root.save_expense()

<ExpenseRoot>:
"""


class ExpenseRow(BoxLayout):
    expense_id = NumericProperty(0)
    merchant_text = StringProperty("")
    note_text = StringProperty("")
    amount_text = StringProperty("")
    date_text = StringProperty("")
    method_text = StringProperty("")
    list_screen = ObjectProperty(allownone=True)
    action_button = ObjectProperty(allownone=True)
    _touch_start = ObjectProperty(allownone=True)
    _touch_moved = NumericProperty(0)

    def open_actions(self, _anchor: Button) -> None:
        content = BoxLayout(orientation="vertical", spacing=10, padding=16)
        edit_button = Button(
            text="Edit",
            size_hint_y=None,
            height=58,
            background_normal="",
            background_color=(0.96, 0.94, 0.9, 1),
            color=(0.15, 0.18, 0.16, 1),
        )
        delete_button = Button(
            text="Delete",
            size_hint_y=None,
            height=58,
            background_normal="",
            background_color=(0.96, 0.94, 0.9, 1),
            color=(0.68, 0.24, 0.2, 1),
        )
        cancel_button = Button(
            text="Cancel",
            size_hint_y=None,
            height=58,
            background_normal="",
            background_color=(0.4, 0.45, 0.43, 1),
        )

        popup = Popup(
            title="Expense Actions",
            content=content,
            size_hint=(0.75, None),
            height=300,
            auto_dismiss=True,
        )
        edit_button.bind(on_release=lambda _instance: self._trigger_edit(popup))
        delete_button.bind(on_release=lambda _instance: self._trigger_delete(popup))
        cancel_button.bind(on_release=lambda _instance: popup.dismiss())

        content.add_widget(edit_button)
        content.add_widget(delete_button)
        content.add_widget(cancel_button)
        popup.open()

    def _trigger_edit(self, popup: Popup) -> None:
        popup.dismiss()
        if self.list_screen is not None and self.expense_id:
            self.list_screen.edit_expense(self.expense_id)

    def _trigger_delete(self, popup: Popup) -> None:
        popup.dismiss()
        if self.list_screen is not None and self.expense_id:
            self.list_screen.confirm_delete(self.expense_id)

    def on_touch_down(self, touch) -> bool:
        if self.collide_point(*touch.pos):
            if self.action_button is not None and self.action_button.collide_point(*touch.pos):
                return super().on_touch_down(touch)
            self._touch_start = touch.pos
            self._touch_moved = 0
        return super().on_touch_down(touch)

    def on_touch_move(self, touch) -> bool:
        if self._touch_start is not None:
            if abs(touch.pos[0] - self._touch_start[0]) > 10 or abs(touch.pos[1] - self._touch_start[1]) > 10:
                self._touch_moved = 1
        return super().on_touch_move(touch)

    def on_touch_up(self, touch) -> bool:
        if not self.collide_point(*touch.pos):
            self._touch_start = None
            self._touch_moved = 0
            return super().on_touch_up(touch)
        if self.action_button is not None and self.action_button.collide_point(*touch.pos):
            self._touch_start = None
            self._touch_moved = 0
            return super().on_touch_up(touch)
        if self._touch_start is not None and not self._touch_moved:
            self._touch_start = None
            self._touch_moved = 0
            if self.list_screen is not None and self.expense_id:
                self.list_screen.view_expense(self.expense_id)
                return True
        self._touch_start = None
        self._touch_moved = 0
        return super().on_touch_up(touch)


class DatePickerPopup(Popup):
    selected_date = ObjectProperty(allownone=False)
    on_select = ObjectProperty(allownone=False)

    def __init__(self, selected_date: date, on_select, **kwargs) -> None:
        super().__init__(**kwargs)
        self.selected_date = selected_date
        self.on_select = on_select
        self.today = date.today()
        self.current_year = selected_date.year
        self.current_month = selected_date.month
        self.title = "Select Date"
        self.size_hint = (0.96, None)
        self.height = 680
        self.auto_dismiss = True
        self.month_names = list(calendar.month_name)[1:]
        self.year_values = [str(year) for year in range(self.today.year, self.today.year - 30, -1)]
        self._build_content()
        self._refresh_days()

    def _build_content(self) -> None:
        content = BoxLayout(orientation="vertical", spacing=12, padding=16)

        header = BoxLayout(size_hint_y=None, height=60, spacing=10)
        prev_button = Button(
            text="<",
            size_hint_x=0.14,
            background_normal="",
            background_color=(0.4, 0.45, 0.43, 1),
            font_size="18sp",
        )
        next_button = Button(
            text=">",
            size_hint_x=0.14,
            background_normal="",
            background_color=(0.4, 0.45, 0.43, 1),
            font_size="18sp",
        )
        self.month_spinner = Spinner(
            text=calendar.month_name[self.current_month],
            values=self.month_names,
            size_hint_x=0.44,
            background_normal="",
            background_color=(0.92, 0.92, 0.92, 1),
            color=(0.15, 0.18, 0.16, 1),
            font_size="16sp",
        )
        self.year_spinner = Spinner(
            text=str(self.current_year),
            values=self.year_values,
            size_hint_x=0.28,
            background_normal="",
            background_color=(0.92, 0.92, 0.92, 1),
            color=(0.15, 0.18, 0.16, 1),
            font_size="16sp",
        )
        prev_button.bind(on_release=lambda _instance: self._change_month(-1))
        next_button.bind(on_release=lambda _instance: self._change_month(1))
        self.month_spinner.bind(text=self._on_month_selected)
        self.year_spinner.bind(text=self._on_year_selected)
        header.add_widget(prev_button)
        header.add_widget(self.month_spinner)
        header.add_widget(self.year_spinner)
        header.add_widget(next_button)
        content.add_widget(header)

        weekday_row = GridLayout(cols=7, size_hint_y=None, height=34, spacing=6)
        for day_name in ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]:
            weekday_row.add_widget(Label(text=day_name, font_size="13sp", color=(0.3, 0.34, 0.32, 1)))
        content.add_widget(weekday_row)

        self.days_grid = GridLayout(cols=7, spacing=6, size_hint_y=None)
        self.days_grid.bind(minimum_height=self.days_grid.setter("height"))
        content.add_widget(self.days_grid)

        footer = BoxLayout(size_hint_y=None, height=58, spacing=12)
        today_button = Button(
            text="Today",
            background_normal="",
            background_color=(0.18, 0.5, 0.32, 1),
            font_size="16sp",
        )
        close_button = Button(
            text="Close",
            background_normal="",
            background_color=(0.4, 0.45, 0.43, 1),
            font_size="16sp",
        )
        today_button.bind(on_release=lambda _instance: self._select(self.today))
        close_button.bind(on_release=lambda _instance: self.dismiss())
        footer.add_widget(today_button)
        footer.add_widget(close_button)
        content.add_widget(footer)

        self.content = content

    def _refresh_days(self) -> None:
        self.month_spinner.text = calendar.month_name[self.current_month]
        self.year_spinner.text = str(self.current_year)
        self.days_grid.clear_widgets()

        month_matrix = calendar.Calendar(firstweekday=0).monthdatescalendar(
            self.current_year,
            self.current_month,
        )
        for week in month_matrix:
            for day_value in week:
                in_month = day_value.month == self.current_month
                is_future = day_value > self.today
                button = Button(
                    text=str(day_value.day) if in_month else "",
                    size_hint_y=None,
                    height=48,
                    disabled=(not in_month) or is_future,
                    background_normal="",
                    background_color=self._day_color(day_value, in_month, is_future),
                    color=(0.15, 0.18, 0.16, 1),
                    font_size="15sp",
                )
                if in_month and not is_future:
                    button.bind(
                        on_release=lambda _instance, selected=day_value: self._select(selected)
                    )
                self.days_grid.add_widget(button)

    def _change_month(self, direction: int) -> None:
        month = self.current_month + direction
        year = self.current_year
        if month < 1:
            month = 12
            year -= 1
        elif month > 12:
            month = 1
            year += 1

        if date(year, month, 1) > date(self.today.year, self.today.month, 1):
            return

        self.current_year = year
        self.current_month = month
        self._refresh_days()

    def _on_month_selected(self, _spinner: Spinner, month_name: str) -> None:
        month_index = self.month_names.index(month_name) + 1
        if month_index == self.current_month:
            return
        self.current_month = month_index
        if date(self.current_year, self.current_month, 1) > date(self.today.year, self.today.month, 1):
            self.current_year = self.today.year
            self.current_month = self.today.month
        self._refresh_days()

    def _on_year_selected(self, _spinner: Spinner, year_text: str) -> None:
        selected_year = int(year_text)
        if selected_year == self.current_year:
            return
        self.current_year = selected_year
        if date(self.current_year, self.current_month, 1) > date(self.today.year, self.today.month, 1):
            self.current_year = self.today.year
            self.current_month = self.today.month
        self._refresh_days()

    def _select(self, selected: date) -> None:
        self.on_select(selected)
        self.dismiss()

    def _day_color(self, day_value: date, in_month: bool, is_future: bool) -> tuple[float, float, float, float]:
        if not in_month:
            return (0.94, 0.94, 0.94, 1)
        if is_future:
            return (0.88, 0.88, 0.88, 1)
        if day_value == self.selected_date:
            return (0.18, 0.5, 0.32, 1)
        if day_value == self.today:
            return (0.83, 0.92, 0.86, 1)
        return (1, 1, 1, 1)


class ExpenseListScreen(Screen):
    repository = ObjectProperty(allownone=False)
    status_message = StringProperty("Review saved expenses or add a new one.")
    status_color = ListProperty([0.13, 0.42, 0.23, 1])
    total_amount_text = StringProperty("Rs. 0.00")
    expense_count_text = StringProperty("0")
    status_is_error = NumericProperty(0)

    def on_pre_enter(self, *args) -> None:
        self.refresh_expenses()
        return super().on_pre_enter(*args)

    def refresh_expenses(self) -> None:
        container = self.ids.list_container
        container.clear_widgets()
        expenses = self.repository.list_expenses()
        total_amount = sum(expense.amount for expense in expenses)
        self.total_amount_text = f"Rs. {total_amount:,.2f}"
        self.expense_count_text = str(len(expenses))

        if not expenses:
            empty_label = Label(
                text="No expenses yet. Add your first entry to start building your timeline.",
                halign="center",
                valign="middle",
                color=(0.28, 0.32, 0.3, 1),
            )
            empty_label.bind(size=lambda instance, _value: setattr(instance, "text_size", (instance.width - 24, None)))
            container.add_widget(
                BoxLayout(
                    size_hint_y=None,
                    height=180,
                )
            )
            empty_state = container.children[0]
            empty_state.padding = 18
            empty_state.canvas.before.clear()
            with empty_state.canvas.before:
                from kivy.graphics import Color, RoundedRectangle
                Color(1, 1, 1, 1)
                RoundedRectangle(pos=empty_state.pos, size=empty_state.size, radius=[24, 24, 24, 24])
            empty_state.bind(
                pos=lambda instance, _value: self._refresh_empty_card(instance),
                size=lambda instance, _value: self._refresh_empty_card(instance),
            )
            empty_state.add_widget(empty_label)
            return

        for expense in expenses:
            container.add_widget(
                ExpenseRow(
                    expense_id=expense.id or 0,
                    merchant_text=expense.merchant,
                    note_text=expense.notes,
                    amount_text=f"Rs. {expense.amount:.2f}",
                    date_text=expense.expense_date,
                    method_text=expense.payment_method,
                    list_screen=self,
                )
            )

    def add_expense(self) -> None:
        edit_screen = self.manager.get_screen("edit")
        edit_screen.prepare_for_new()
        self.manager.current = "edit"

    def edit_expense(self, expense_id: int | None) -> None:
        if expense_id is None:
            self._set_status("Unable to open this expense.", is_error=True)
            return

        edit_screen = self.manager.get_screen("edit")
        edit_screen.load_expense(expense_id)
        self.manager.current = "edit"

    def view_expense(self, expense_id: int | None) -> None:
        if expense_id is None:
            self._set_status("Unable to open this expense.", is_error=True)
            return

        expense = self.repository.get_expense(expense_id)
        if expense is None:
            self._set_status("Expense not found.", is_error=True)
            self.refresh_expenses()
            return

        self._open_expense_detail_popup(expense)

    def show_saved_status(self, message: str) -> None:
        self._set_status(message, is_error=False)

    def confirm_delete(self, expense_id: int | None) -> None:
        if expense_id is None:
            self._set_status("Unable to delete this expense.", is_error=True)
            return

        expense = self.repository.get_expense(expense_id)
        if expense is None:
            self._set_status("Expense not found.", is_error=True)
            self.refresh_expenses()
            return

        content = BoxLayout(orientation="vertical", spacing=12, padding=16)
        content.add_widget(
            Label(
                text="Are you sure you want to delete this expense?",
                halign="center",
                valign="middle",
                color=(0.15, 0.18, 0.16, 1),
            )
        )
        buttons = BoxLayout(size_hint_y=None, height=48, spacing=10)
        popup = Popup(
            title="Delete Expense",
            content=content,
            size_hint=(0.85, None),
            height=220,
            auto_dismiss=False,
        )
        no_button = Button(
            text="No",
            background_normal="",
            background_color=(0.4, 0.45, 0.43, 1),
        )
        yes_button = Button(
            text="Yes",
            background_normal="",
            background_color=(0.68, 0.24, 0.2, 1),
        )
        no_button.bind(on_release=lambda _instance: popup.dismiss())
        yes_button.bind(on_release=lambda _instance: self._delete_expense(expense, popup))
        buttons.add_widget(no_button)
        buttons.add_widget(yes_button)
        content.add_widget(buttons)
        popup.open()

    def _delete_expense(self, expense: ExpenseRecord, popup: Popup) -> None:
        self.repository.delete_expense(expense.id or 0)
        popup.dismiss()
        self.show_saved_status(f"Deleted Rs. {expense.amount:.2f} for {expense.merchant}.")
        self.refresh_expenses()

    def _set_status(self, message: str, *, is_error: bool) -> None:
        self.status_message = message
        self.status_color = [0.78, 0.24, 0.18, 1] if is_error else [0.13, 0.42, 0.23, 1]
        self.status_is_error = 1 if is_error else 0

    def _refresh_empty_card(self, instance: BoxLayout) -> None:
        from kivy.graphics import Color, RoundedRectangle

        instance.canvas.before.clear()
        with instance.canvas.before:
            Color(1, 1, 1, 1)
            RoundedRectangle(pos=instance.pos, size=instance.size, radius=[24, 24, 24, 24])

    def _open_expense_detail_popup(self, expense: ExpenseRecord) -> None:
        modal = ModalView(
            auto_dismiss=True,
            size_hint=(1, 1),
            background_color=(0.08, 0.1, 0.09, 0.45),
        )

        outer = AnchorLayout(anchor_x="center", anchor_y="center", padding=dp(24))
        card = BoxLayout(
            orientation="vertical",
            size_hint=(None, None),
            size=(dp(320), dp(420)),
            spacing=dp(14),
            padding=dp(18),
        )

        def redraw_popup_card(instance: BoxLayout, _value) -> None:
            from kivy.graphics import Color, RoundedRectangle

            instance.canvas.before.clear()
            with instance.canvas.before:
                Color(0.99, 0.98, 0.96, 1)
                RoundedRectangle(pos=instance.pos, size=instance.size, radius=[24, 24, 24, 24])

        card.bind(pos=redraw_popup_card, size=redraw_popup_card)
        redraw_popup_card(card, None)

        header = BoxLayout(size_hint_y=None, height=42, spacing=12)
        title = Label(
            text="Expense Details",
            halign="left",
            valign="middle",
            color=(0.14, 0.18, 0.16, 1),
            font_size="20sp",
            bold=True,
        )
        title.bind(size=lambda instance, _value: setattr(instance, "text_size", instance.size))
        close_button = Button(
            text="X",
            size_hint=(None, None),
            size=(38, 38),
            background_normal="",
            background_down="",
            background_color=(0.92, 0.94, 0.93, 1),
            color=(0.22, 0.26, 0.24, 1),
        )
        header.add_widget(title)
        header.add_widget(close_button)
        card.add_widget(header)

        field_container = BoxLayout(orientation="vertical", spacing=10)
        fields = [
            ("Amount", f"Rs. {expense.amount:.2f}"),
            ("Merchant", expense.merchant),
            ("Payment Method", expense.payment_method),
            ("Date", expense.expense_date),
            ("Notes", expense.notes or "No additional notes"),
        ]
        for label_text, value_text in fields:
            field_container.add_widget(
                self._build_detail_row(label_text, value_text, multiline=(label_text == "Notes"))
            )
        card.add_widget(field_container)
        outer.add_widget(card)
        modal.add_widget(outer)
        close_button.bind(on_release=lambda _instance: modal.dismiss())
        modal.open()

    def _build_detail_row(self, label_text: str, value_text: str, *, multiline: bool = False) -> BoxLayout:
        row_height = dp(98) if multiline else dp(60)
        row = BoxLayout(
            orientation="horizontal",
            spacing=dp(12),
            size_hint_y=None,
            height=row_height,
            padding=(dp(14), dp(12)),
        )

        def redraw_card(instance: BoxLayout, _value) -> None:
            from kivy.graphics import Color, RoundedRectangle

            instance.canvas.before.clear()
            with instance.canvas.before:
                Color(0.98, 0.98, 0.97, 1)
                RoundedRectangle(pos=instance.pos, size=instance.size, radius=[18, 18, 18, 18])

        row.bind(pos=redraw_card, size=redraw_card)
        redraw_card(row, None)

        label = Label(
            text=label_text,
            size_hint_x=None,
            width=dp(96),
            halign="left",
            valign="top" if multiline else "middle",
            color=(0.45, 0.5, 0.48, 1),
            font_size="12sp",
            bold=True,
        )
        value = Label(
            text=value_text,
            halign="left",
            valign="top" if multiline else "middle",
            color=(0.15, 0.18, 0.16, 1),
            font_size="15sp",
            shorten=not multiline,
            shorten_from="right",
        )
        label.bind(size=lambda instance, _value: setattr(instance, "text_size", instance.size))
        value.bind(
            size=lambda instance, _value: setattr(
                instance,
                "text_size",
                (instance.width, None if multiline else instance.height),
            )
        )
        row.add_widget(label)
        row.add_widget(value)
        return row


class ExpenseEditScreen(Screen):
    repository = ObjectProperty(allownone=False)
    expense_id = ObjectProperty(allownone=True)
    default_date = StringProperty(date.today().isoformat())
    screen_title = StringProperty("Add Expense")
    action_button_text = StringProperty("Save Expense")
    feedback_message = StringProperty("Fill in the details and save the expense.")
    feedback_color = ListProperty([0.13, 0.42, 0.23, 1])

    def prepare_for_new(self) -> None:
        self.expense_id = None
        self.screen_title = "Add Expense"
        self.action_button_text = "Save Expense"
        self._set_feedback("Fill in the details and save the expense.", is_error=False)
        self._fill_form(
            ExpenseRecord(
                id=None,
                amount=0.0,
                merchant="",
                payment_method="UPI",
                expense_date=self.default_date,
                notes="",
            )
        )
        self.ids.amount_input.text = ""

    def load_expense(self, expense_id: int) -> None:
        expense = self.repository.get_expense(expense_id)
        if expense is None:
            self.prepare_for_new()
            self._set_feedback("Expense not found.", is_error=True)
            return

        self.expense_id = expense.id
        self.screen_title = "Edit Expense"
        self.action_button_text = "Update Expense"
        self._set_feedback("Update the details and save the expense.", is_error=False)
        self._fill_form(expense)

    def save_expense(self) -> None:
        amount_text = self.ids.amount_input.text.strip()
        merchant = self.ids.merchant_input.text.strip()
        payment_method = self.ids.payment_method_input.text.strip()
        expense_date = self.ids.date_button.text.strip()
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
            id=self.expense_id,
            amount=amount,
            merchant=merchant,
            payment_method=payment_method,
            expense_date=expense_date,
            notes=notes,
        )

        if self.expense_id is None:
            saved_expense = self.repository.add_expense(expense)
            status_message = f"Saved Rs. {saved_expense.amount:.2f} for {saved_expense.merchant}."
        else:
            saved_expense = self.repository.update_expense(expense)
            status_message = f"Updated Rs. {saved_expense.amount:.2f} for {saved_expense.merchant}."

        list_screen = self.manager.get_screen("list")
        list_screen.show_saved_status(status_message)
        list_screen.refresh_expenses()
        self.manager.current = "list"

    def cancel(self) -> None:
        self.manager.current = "list"

    def open_date_picker(self) -> None:
        selected_date = date.fromisoformat(self.ids.date_button.text)
        popup = DatePickerPopup(
            selected_date=selected_date,
            on_select=self._set_selected_date,
        )
        popup.open()

    def _fill_form(self, expense: ExpenseRecord) -> None:
        self.ids.amount_input.text = f"{expense.amount:.2f}" if expense.amount else ""
        self.ids.merchant_input.text = expense.merchant
        self.ids.payment_method_input.text = expense.payment_method or "UPI"
        self.ids.date_button.text = expense.expense_date or self.default_date
        self.ids.notes_input.text = expense.notes

    def _set_selected_date(self, selected: date) -> None:
        self.ids.date_button.text = selected.isoformat()

    def _set_feedback(self, message: str, *, is_error: bool) -> None:
        self.feedback_message = message
        self.feedback_color = [0.78, 0.24, 0.18, 1] if is_error else [0.13, 0.42, 0.23, 1]


class ExpenseRoot(ScreenManager):
    repository = ObjectProperty(allownone=False)


class ExpenseTrackerApp(App):
    title = "Expense Tracker"

    def build(self) -> ExpenseRoot | Label:
        try:
            Window.softinput_mode = "below_target"
            Builder.load_string(KV)
            repository = ExpenseRepository(Path(self.user_data_dir) / "expenses.db")
            root = ExpenseRoot(repository=repository)
            root.add_widget(ExpenseListScreen(repository=repository))
            root.add_widget(ExpenseEditScreen(repository=repository))
            root.current = "list"
            return root
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
