from __future__ import annotations

import calendar
from collections import defaultdict
import re
import tempfile
import traceback
from datetime import datetime
from datetime import date
from pathlib import Path
from threading import Thread
from urllib.parse import unquote

from kivy.app import App
from kivy.clock import Clock, mainthread
from kivy.core.window import Window
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import ListProperty, NumericProperty, ObjectProperty, StringProperty
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.filechooser import FileChooserListView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.modalview import ModalView
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.screenmanager import Screen, ScreenManager
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget
from app.csv_transfer import CsvImportResult, export_transactions_csv, parse_transactions_csv, build_transactions_csv
from app.database import ExpenseRepository
from app.android_bridge import (
    create_csv_document,
    get_csv_display_name,
    get_pdf_display_name,
    materialize_selected_csv,
    materialize_selected_pdf,
    open_csv_picker,
    open_pdf_picker,
    write_csv_text_to_uri,
)
from app.models import ExpenseRecord, StatementReviewRecord
from app.statement_parser import parse_statement_pdf

KV = """
#:import dp kivy.metrics.dp

<BottomTabBar@BoxLayout>:
    active_tab: ""
    size_hint_y: None
    height: "72dp"
    padding: "12dp"
    spacing: "12dp"
    canvas.before:
        Color:
            rgba: 1, 1, 1, 1
        Rectangle:
            pos: self.pos
            size: self.size
        Color:
            rgba: 0.88, 0.92, 0.9, 1
        Line:
            points: self.x, self.top, self.right, self.top
            width: 1

    Button:
        text: "Home"
        background_normal: ""
        background_down: ""
        background_color: (0.21, 0.56, 0.39, 1) if root.active_tab == "home" else (0.93, 0.95, 0.94, 1)
        color: (1, 1, 1, 1) if root.active_tab == "home" else (0.14, 0.18, 0.16, 1)
        bold: True
        on_release: app.root.current = "home"

    Button:
        text: "Transactions"
        background_normal: ""
        background_down: ""
        background_color: (0.21, 0.56, 0.39, 1) if root.active_tab == "transactions" else (0.93, 0.95, 0.94, 1)
        color: (1, 1, 1, 1) if root.active_tab == "transactions" else (0.14, 0.18, 0.16, 1)
        bold: True
        on_release: app.root.current = "transactions"

    Button:
        text: "Import Statements"
        background_normal: ""
        background_down: ""
        background_color: (0.21, 0.56, 0.39, 1) if root.active_tab == "notifications" else (0.93, 0.95, 0.94, 1)
        color: (1, 1, 1, 1) if root.active_tab == "notifications" else (0.14, 0.18, 0.16, 1)
        bold: True
        on_release: app.root.current = "notifications"

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
    name: "home"
    BoxLayout:
        orientation: "vertical"
        padding: "14dp"
        spacing: "14dp"
        canvas.before:
            Color:
                rgba: 0.97, 0.95, 0.91, 1
            Rectangle:
                pos: self.pos
                size: self.size

        BoxLayout:
            orientation: "vertical"
            size_hint_y: None
            height: "260dp"
            padding: "18dp"
            spacing: "14dp"
            canvas.before:
                Color:
                    rgba: 0.14, 0.35, 0.27, 1
                RoundedRectangle:
                    pos: self.pos
                    size: self.size
                    radius: [24, 24, 24, 24]

            Label:
                text: "SpendSutra"
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

            BoxLayout:
                size_hint_y: None
                height: "48dp"
                spacing: "10dp"

                Button:
                    text: "+ Add Expense"
                    background_normal: ""
                    background_down: ""
                    background_color: 0.21, 0.56, 0.39, 1
                    color: 1, 1, 1, 1
                    bold: True
                    on_release: root.add_expense()

                Button:
                    text: "View Visualization"
                    background_normal: ""
                    background_down: ""
                    background_color: 0.84, 0.92, 0.88, 1
                    color: 0.13, 0.24, 0.19, 1
                    bold: True
                    on_release: root.open_visualization()

            Button:
                text: "Data Transfer"
                size_hint_y: None
                height: "46dp"
                background_normal: ""
                background_down: ""
                background_color: 0.93, 0.95, 0.94, 1
                color: 0.14, 0.18, 0.16, 1
                bold: True
                on_release: root.open_data_transfer()

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
            padding: "14dp"
            spacing: "14dp"
            canvas.before:
                Color:
                    rgba: 0.98, 0.97, 0.95, 1
                RoundedRectangle:
                    pos: self.pos
                    size: self.size
                    radius: [24, 24, 24, 24]

            BoxLayout:
                size_hint_y: None
                height: "42dp"

                Label:
                    text: "Spend by Payment Method"
                    halign: "left"
                    valign: "middle"
                    text_size: self.size
                    font_size: "23sp"
                    bold: True
                    color: 0.15, 0.18, 0.16, 1

            BoxLayout:
                spacing: "14dp"

                AnchorLayout:
                    id: pie_chart_anchor
                    size_hint_x: 0.56

                ScrollView:
                    do_scroll_x: False
                    bar_width: "4dp"

                    BoxLayout:
                        id: pie_legend_container
                        orientation: "vertical"
                        size_hint_y: None
                        height: self.minimum_height
                        spacing: "10dp"
                        padding: 0, 0, 0, "20dp"

        BottomTabBar:
            active_tab: "home"

<TransactionsScreen>:
    name: "transactions"
    BoxLayout:
        orientation: "vertical"
        padding: "14dp"
        spacing: "14dp"
        canvas.before:
            Color:
                rgba: 0.97, 0.95, 0.91, 1
            Rectangle:
                pos: self.pos
                size: self.size

        BoxLayout:
            orientation: "vertical"
            size_hint_y: None
            height: "170dp"
            padding: "18dp"
            spacing: "12dp"
            canvas.before:
                Color:
                    rgba: 0.14, 0.35, 0.27, 1
                RoundedRectangle:
                    pos: self.pos
                    size: self.size
                    radius: [24, 24, 24, 24]

            Label:
                text: "Transactions"
                size_hint_y: None
                height: "34dp"
                halign: "left"
                valign: "middle"
                text_size: self.width, self.height
                font_size: "31sp"
                bold: True
                color: 1, 1, 1, 1

            Label:
                text: "Search, filter, sort, and manage every saved transaction."
                size_hint_y: None
                height: "22dp"
                halign: "left"
                valign: "middle"
                text_size: self.width, self.height
                color: 0.84, 0.93, 0.89, 1

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
            padding: "14dp"
            spacing: "14dp"
            canvas.before:
                Color:
                    rgba: 0.98, 0.97, 0.95, 1
                RoundedRectangle:
                    pos: self.pos
                    size: self.size
                    radius: [24, 24, 24, 24]

            TextInput:
                id: search_input
                size_hint_y: None
                height: "48dp"
                multiline: False
                hint_text: "Search merchant or notes"
                background_normal: ""
                background_active: ""
                background_color: 1, 1, 1, 1
                foreground_color: 0.15, 0.18, 0.16, 1
                cursor_color: 0.18, 0.5, 0.32, 1
                padding: "14dp", "14dp"
                on_text: root.refresh_expenses()

            BoxLayout:
                size_hint_y: None
                height: "48dp"
                spacing: "10dp"

                Button:
                    id: start_date_filter_button
                    text: root.start_date_filter_text
                    background_normal: ""
                    background_down: ""
                    background_color: 1, 1, 1, 1
                    color: 0.15, 0.18, 0.16, 1
                    on_release: root.open_start_date_picker()

                Button:
                    id: end_date_filter_button
                    text: root.end_date_filter_text
                    background_normal: ""
                    background_down: ""
                    background_color: 1, 1, 1, 1
                    color: 0.15, 0.18, 0.16, 1
                    on_release: root.open_end_date_picker()

            BoxLayout:
                size_hint_y: None
                height: "48dp"
                spacing: "10dp"

                Spinner:
                    id: payment_filter_input
                    text: "All Methods"
                    values: ["All Methods", "UPI", "Card", "Cash", "Net Banking", "Wallet", "Other", "ACH", "NEFT", "IMPS", "Bank Transfer"]
                    background_normal: ""
                    background_color: 1, 1, 1, 1
                    color: 0.15, 0.18, 0.16, 1
                    on_text: root.refresh_expenses()

                Spinner:
                    id: sort_input
                    text: "Newest"
                    values: ["Newest", "Oldest", "Amount High-Low", "Amount Low-High", "Merchant A-Z"]
                    background_normal: ""
                    background_color: 1, 1, 1, 1
                    color: 0.15, 0.18, 0.16, 1
                    on_text: root.refresh_expenses()

                Button:
                    text: "Clear"
                    size_hint_x: None
                    width: "84dp"
                    background_normal: ""
                    background_down: ""
                    background_color: 0.46, 0.51, 0.49, 1
                    color: 1, 1, 1, 1
                    on_release: root.clear_filters()

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

        BottomTabBar:
            active_tab: "transactions"

<NotificationsScreen>:
    name: "notifications"
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
            padding: "14dp"
            spacing: "14dp"

            BoxLayout:
                orientation: "vertical"
                size_hint_y: None
                height: "220dp"
                padding: "18dp"
                spacing: "10dp"
                canvas.before:
                    Color:
                        rgba: 0.14, 0.35, 0.27, 1
                    RoundedRectangle:
                        pos: self.pos
                        size: self.size
                        radius: [24, 24, 24, 24]

                BoxLayout:
                    size_hint_y: None
                    height: "36dp"
                    spacing: "10dp"

                    Label:
                        text: "Statement Review"
                        halign: "left"
                        valign: "middle"
                        text_size: self.size
                        font_size: "28sp"
                        bold: True
                        color: 1, 1, 1, 1

                    Button:
                        text: "i"
                        size_hint: None, None
                        size: "30dp", "30dp"
                        background_normal: ""
                        background_down: ""
                        background_color: 0.84, 0.92, 0.88, 1
                        color: 0.13, 0.24, 0.19, 1
                        bold: True
                        on_release: root.open_info_tooltip()

                Label:
                    text: root.status_message
                    size_hint_y: None
                    height: "54dp"
                    halign: "left"
                    valign: "top"
                    text_size: self.width, None
                    color: root.status_color

                Label:
                    text: root.selected_file_label
                    size_hint_y: None
                    height: "28dp"
                    halign: "left"
                    valign: "middle"
                    text_size: self.width, self.height
                    color: 0.84, 0.93, 0.89, 1
                    font_size: "14sp"
                    shorten: True
                    shorten_from: "center"

                BoxLayout:
                    size_hint_y: None
                    height: "44dp"
                    spacing: "10dp"

                    Button:
                        text: "Browse PDF"
                        background_normal: ""
                        background_down: ""
                        background_color: 0.93, 0.95, 0.94, 1
                        color: 0.14, 0.18, 0.16, 1
                        on_release: root.open_file_browser()

                    Button:
                        text: "Upload"
                        background_normal: ""
                        background_down: ""
                        background_color: 0.84, 0.92, 0.88, 1
                        color: 0.13, 0.24, 0.19, 1
                        bold: True
                        on_release: root.import_statement()

                BoxLayout:
                    size_hint_y: None
                    height: "44dp"
                    spacing: "10dp"

                    Button:
                        text: "Clear"
                        size_hint_x: None
                        width: "110dp"
                        background_normal: ""
                        background_down: ""
                        background_color: 0.46, 0.51, 0.49, 1
                        color: 1, 1, 1, 1
                        bold: True
                        on_release: root.clear_pending_reviews()

                    Button:
                        text: "Save All Debits"
                        background_normal: ""
                        background_down: ""
                        background_color: 0.21, 0.56, 0.39, 1
                        color: 1, 1, 1, 1
                        bold: True
                        on_release: root.save_all_debits()

            BoxLayout:
                orientation: "vertical"
                padding: "14dp"
                spacing: "12dp"
                canvas.before:
                    Color:
                        rgba: 0.98, 0.97, 0.95, 1
                    RoundedRectangle:
                        pos: self.pos
                        size: self.size
                        radius: [24, 24, 24, 24]

                BoxLayout:
                    size_hint_y: None
                    height: "44dp"
                    spacing: "10dp"

                    Label:
                        text: "Pending Review"
                        halign: "left"
                        valign: "middle"
                        text_size: self.size
                        font_size: "21sp"
                        bold: True
                        color: 0.15, 0.18, 0.16, 1

                    Spinner:
                        id: direction_filter_input
                        size_hint_x: None
                        width: "170dp"
                        text: "All Directions"
                        values: ["All Directions", "Debit Only", "Credit Only"]
                        background_normal: ""
                        background_color: 1, 1, 1, 1
                        color: 0.15, 0.18, 0.16, 1
                        on_text: root.refresh_reviews()

                ScrollView:
                    do_scroll_x: False
                    bar_width: "4dp"

                    BoxLayout:
                        id: review_container
                        orientation: "vertical"
                        size_hint_y: None
                        height: self.minimum_height
                        spacing: "12dp"
                        padding: 0, 0, 0, "20dp"

        BottomTabBar:
            active_tab: "notifications"

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

<VisualizationScreen>:
    name: "visualization"
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
            height: "184dp"
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
                on_release: root.go_back()

            Label:
                text: "Spend Visualization"
                size_hint_y: None
                height: "38dp"
                halign: "left"
                valign: "middle"
                text_size: self.width, self.height
                font_size: "30sp"
                bold: True
                color: 1, 1, 1, 1

            Label:
                text: "Review monthly and yearly spend trends with a full-size chart."
                size_hint_y: None
                height: "40dp"
                halign: "left"
                valign: "top"
                text_size: self.width, None
                color: 0.84, 0.93, 0.89, 1

        BoxLayout:
            orientation: "vertical"
            padding: "18dp"
            spacing: "14dp"

            BoxLayout:
                size_hint_y: None
                height: "48dp"
                spacing: "10dp"

                Button:
                    id: monthly_button
                    text: "Monthly"
                    background_normal: ""
                    background_down: ""
                    background_color: 0.21, 0.56, 0.39, 1
                    color: 1, 1, 1, 1
                    bold: True
                    on_release: root.set_mode("monthly")

                Button:
                    id: yearly_button
                    text: "Yearly"
                    background_normal: ""
                    background_down: ""
                    background_color: 0.9, 0.93, 0.91, 1
                    color: 0.14, 0.18, 0.16, 1
                    bold: True
                    on_release: root.set_mode("yearly")

            BoxLayout:
                id: selector_row
                size_hint_y: None
                height: "46dp"
                spacing: "10dp"

                Label:
                    text: "Year"
                    size_hint_x: None
                    width: "52dp"
                    halign: "left"
                    valign: "middle"
                    text_size: self.size
                    color: 0.24, 0.28, 0.26, 1

                Spinner:
                    id: year_spinner
                    text: root.selected_year_text
                    values: root.year_values
                    background_normal: ""
                    background_color: 0.95, 0.96, 0.95, 1
                    color: 0.14, 0.18, 0.16, 1
                    on_text: root.on_year_selected(self.text)

            Label:
                id: chart_caption
                text: root.chart_caption
                size_hint_y: None
                height: "26dp"
                halign: "left"
                valign: "middle"
                text_size: self.width, self.height
                font_size: "18sp"
                bold: True
                color: 0.15, 0.18, 0.16, 1

            BoxLayout:
                orientation: "vertical"
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

                ScrollView:
                    do_scroll_x: True
                    do_scroll_y: False
                    bar_width: "4dp"

                    BoxLayout:
                        id: chart_anchor
                        orientation: "vertical"
                        size_hint_x: None
                        size_hint_y: None
                        width: max(self.minimum_width, self.parent.width if self.parent else 0)
                        height: max(self.minimum_height, dp(360))
                        padding: "16dp"

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


class ReviewPopupContent(BoxLayout):
    selectable_input = ObjectProperty(allownone=True)

    def on_touch_down(self, touch):
        if (
            self.selectable_input is not None
            and self.selectable_input.selection_text
            and not self.selectable_input.collide_point(*touch.pos)
        ):
            self.selectable_input.cancel_selection()
            self.selectable_input.focus = False
        return super().on_touch_down(touch)


class CircularProgressRing(Widget):
    progress = NumericProperty(0)

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.bind(pos=self._redraw, size=self._redraw, progress=self._redraw)

    def _redraw(self, *_args) -> None:
        from kivy.graphics import Color, Line

        self.canvas.before.clear()
        with self.canvas.before:
            center_x = self.center_x
            center_y = self.center_y
            radius = min(self.width, self.height) / 2 - dp(6)
            Color(0.82, 0.86, 0.84, 1)
            Line(circle=(center_x, center_y, radius, 0, 360), width=dp(6))
            Color(0.21, 0.56, 0.39, 1)
            Line(circle=(center_x, center_y, radius, 90, 90 + (360 * (self.progress / 100.0))), width=dp(6))


class PaymentMethodPieChart(Widget):
    segments = ListProperty([])

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.bind(pos=self._redraw, size=self._redraw, segments=self._redraw)

    def _redraw(self, *_args) -> None:
        from kivy.graphics import Color, Ellipse

        self.canvas.before.clear()
        with self.canvas.before:
            if not self.segments:
                Color(0.9, 0.92, 0.91, 1)
                Ellipse(pos=self.pos, size=self.size)
                return

            angle_start = 0.0
            for _label, ratio, color in self.segments:
                if ratio <= 0:
                    continue
                Color(*color)
                Ellipse(
                    pos=self.pos,
                    size=self.size,
                    angle_start=angle_start,
                    angle_end=angle_start + (ratio * 360.0),
                )
                angle_start += ratio * 360.0


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
    status_message = StringProperty("Track totals, move quickly, and review the payment split.")
    status_color = ListProperty([0.84, 0.93, 0.89, 1])
    total_amount_text = StringProperty("Rs. 0.00")
    expense_count_text = StringProperty("0")

    def on_pre_enter(self, *args) -> None:
        self.refresh_dashboard()
        return super().on_pre_enter(*args)

    def refresh_dashboard(self) -> None:
        expenses = self.repository.list_expenses(limit=None)
        total_amount = sum(expense.amount for expense in expenses)
        self.total_amount_text = f"Rs. {total_amount:,.2f}"
        self.expense_count_text = str(len(expenses))
        self._refresh_pie_chart(expenses)

    def _refresh_pie_chart(self, expenses: list[ExpenseRecord]) -> None:
        chart_anchor = self.ids.pie_chart_anchor
        legend_container = self.ids.pie_legend_container
        chart_anchor.clear_widgets()
        legend_container.clear_widgets()

        if not expenses:
            empty_label = Label(
                text="Add expenses to see the payment split.",
                halign="center",
                valign="middle",
                color=(0.32, 0.36, 0.34, 1),
            )
            empty_label.bind(size=lambda instance, _value: setattr(instance, "text_size", instance.size))
            chart_anchor.add_widget(empty_label)
            return

        totals: defaultdict[str, float] = defaultdict(float)
        for expense in expenses:
            totals[expense.payment_method or "Other"] += expense.amount

        palette = [
            (0.14, 0.35, 0.27, 1),
            (0.1, 0.77, 0.79, 1),
            (0.64, 0.28, 0.67, 1),
            (0.92, 0.61, 0.22, 1),
            (0.39, 0.54, 0.93, 1),
            (0.88, 0.36, 0.29, 1),
        ]
        total_spend = sum(totals.values()) or 1.0
        segments = []
        for index, (method, amount) in enumerate(sorted(totals.items(), key=lambda item: item[1], reverse=True)):
            color = palette[index % len(palette)]
            segments.append((method, amount / total_spend, color))
            legend_container.add_widget(self._build_pie_legend_row(method, amount, color, total_spend))

        chart_anchor.add_widget(
            PaymentMethodPieChart(
                size_hint=(None, None),
                size=(dp(220), dp(220)),
                segments=segments,
            )
        )

    def _build_pie_legend_row(
        self,
        method: str,
        amount: float,
        color: tuple[float, float, float, float],
        total_spend: float,
    ) -> BoxLayout:
        row = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(10))
        swatch_anchor = AnchorLayout(size_hint_x=None, width=dp(20))
        swatch = Widget(size_hint=(None, None), size=(dp(16), dp(16)))

        def redraw_swatch(instance: Widget, _value) -> None:
            from kivy.graphics import Color, RoundedRectangle

            instance.canvas.before.clear()
            with instance.canvas.before:
                Color(*color)
                RoundedRectangle(pos=instance.pos, size=instance.size, radius=[5, 5, 5, 5])

        swatch.bind(pos=redraw_swatch, size=redraw_swatch)
        redraw_swatch(swatch, None)
        swatch_anchor.add_widget(swatch)
        row.add_widget(swatch_anchor)

        label = Label(
            text=method,
            halign="left",
            valign="middle",
            color=(0.15, 0.18, 0.16, 1),
            font_size="14sp",
            bold=True,
        )
        label.bind(size=lambda instance, _value: setattr(instance, "text_size", instance.size))
        row.add_widget(label)

        value = Label(
            text=f"Rs. {amount:,.0f}  ({(amount / total_spend) * 100:.0f}%)",
            size_hint_x=None,
            width=dp(132),
            halign="right",
            valign="middle",
            color=(0.42, 0.47, 0.45, 1),
            font_size="13sp",
        )
        value.bind(size=lambda instance, _value: setattr(instance, "text_size", instance.size))
        row.add_widget(value)
        return row

    def add_expense(self) -> None:
        edit_screen = self.manager.get_screen("edit")
        edit_screen.prepare_for_new()
        self.manager.current = "edit"

    def show_saved_status(self, message: str) -> None:
        self._set_status(message, is_error=False)

    def _set_status(self, message: str, *, is_error: bool) -> None:
        self.status_message = message
        self.status_color = [0.98, 0.82, 0.78, 1] if is_error else [0.84, 0.93, 0.89, 1]

    def open_visualization(self) -> None:
        visualization_screen = self.manager.get_screen("visualization")
        visualization_screen.prepare_visualization()
        self.manager.current = "visualization"

    def open_data_transfer(self) -> None:
        content = BoxLayout(orientation="vertical", spacing=dp(14), padding=dp(16))

        title = Label(
            text="Data Transfer",
            size_hint_y=None,
            height=dp(28),
            halign="left",
            valign="middle",
            font_size="22sp",
            bold=True,
            color=(0.14, 0.18, 0.16, 1),
        )
        title.bind(size=lambda instance, _value: setattr(instance, "text_size", instance.size))
        subtitle = Label(
            text="Export confirmed transactions to CSV or import them back from a CSV backup.",
            size_hint_y=None,
            height=dp(44),
            halign="left",
            valign="top",
            color=(0.42, 0.47, 0.45, 1),
        )
        subtitle.bind(size=lambda instance, _value: setattr(instance, "text_size", (instance.width, None)))

        actions = BoxLayout(size_hint_y=None, height=dp(52), spacing=dp(12))
        export_button = Button(
            text="Export CSV",
            background_normal="",
            background_down="",
            background_color=(0.21, 0.56, 0.39, 1),
            color=(1, 1, 1, 1),
            bold=True,
        )
        import_button = Button(
            text="Import CSV",
            background_normal="",
            background_down="",
            background_color=(0.84, 0.92, 0.88, 1),
            color=(0.13, 0.24, 0.19, 1),
            bold=True,
        )
        actions.add_widget(export_button)
        actions.add_widget(import_button)

        status_label = Label(
            text="Choose an action to back up or restore saved transactions.",
            size_hint_y=None,
            height=dp(56),
            halign="left",
            valign="top",
            color=(0.42, 0.47, 0.45, 1),
        )
        status_label.bind(size=lambda instance, _value: setattr(instance, "text_size", (instance.width, None)))

        close_button = Button(
            text="Close",
            size_hint_y=None,
            height=dp(46),
            background_normal="",
            background_down="",
            background_color=(0.46, 0.51, 0.49, 1),
            color=(1, 1, 1, 1),
        )

        content.add_widget(title)
        content.add_widget(subtitle)
        content.add_widget(actions)
        content.add_widget(status_label)
        content.add_widget(close_button)

        popup = Popup(
            title="",
            content=content,
            size_hint=(0.9, 0.4),
            auto_dismiss=False,
            separator_height=0,
        )

        self._transfer_popup = popup
        self._transfer_status_label = status_label

        export_button.bind(on_release=lambda _instance: self._start_csv_export())
        import_button.bind(on_release=lambda _instance: self._start_csv_import())
        close_button.bind(on_release=lambda _instance: popup.dismiss())
        popup.bind(on_dismiss=lambda _instance: self._clear_transfer_popup_state())
        popup.open()

    def _clear_transfer_popup_state(self) -> None:
        self._transfer_popup = None
        self._transfer_status_label = None

    def _set_transfer_status(self, message: str, *, is_error: bool = False) -> None:
        label = getattr(self, "_transfer_status_label", None)
        if label is None:
            return
        label.text = message
        label.color = (0.78, 0.24, 0.18, 1) if is_error else (0.42, 0.47, 0.45, 1)

    def _start_csv_export(self) -> None:
        expenses = self.repository.list_expenses(limit=None)
        if not expenses:
            self._set_transfer_status("No saved transactions are available to export.", is_error=True)
            return

        file_name = f"expenses_export_{datetime.now().strftime('%Y-%m-%d_%H%M%S')}.csv"
        csv_text = build_transactions_csv(expenses)

        if create_csv_document(self._handle_csv_export_destination, file_name):
            self._pending_csv_export_text = csv_text
            self._set_transfer_status("Choose where to save the CSV export.", is_error=False)
            return

        fallback_dir = Path.cwd() / "exports"
        output_path = fallback_dir / file_name
        export_transactions_csv(expenses, output_path)
        self._set_transfer_status(f"Exported {len(expenses)} transaction(s) to {output_path.name}.", is_error=False)
        self.show_saved_status(f"Exported CSV backup: {output_path.name}")

    def _handle_csv_export_destination(self, selection: list[str] | tuple[str, ...]) -> None:
        Clock.schedule_once(lambda _dt: self._apply_csv_export_destination(selection), 0)

    @mainthread
    def _apply_csv_export_destination(self, selection: list[str] | tuple[str, ...]) -> None:
        csv_text = getattr(self, "_pending_csv_export_text", "")
        if not selection or not csv_text:
            self._set_transfer_status("CSV export was cancelled.", is_error=True)
            self._pending_csv_export_text = ""
            return

        target = str(selection[0])
        success = write_csv_text_to_uri(target, csv_text)
        self._pending_csv_export_text = ""
        if not success:
            self._set_transfer_status("Could not write the CSV file to the chosen location.", is_error=True)
            return

        display_name = get_csv_display_name(target) or self._friendly_csv_name(target, fallback="transactions.csv")
        self._set_transfer_status(f"Exported saved transactions to {display_name}.", is_error=False)
        self.show_saved_status(f"Exported CSV backup: {display_name}")

    def _start_csv_import(self) -> None:
        try:
            if open_csv_picker(self._handle_csv_import_selection):
                self._set_transfer_status("File manager opened. Choose a CSV backup there.", is_error=False)
                return
        except Exception:
            pass
        self._open_embedded_csv_browser()

    def _open_embedded_csv_browser(self) -> None:
        chooser = FileChooserListView(
            path=str(self._default_csv_dir()),
            filters=["*.csv"],
            multiselect=False,
        )

        actions = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(10))
        cancel_button = Button(
            text="Cancel",
            background_normal="",
            background_down="",
            background_color=(0.46, 0.51, 0.49, 1),
            color=(1, 1, 1, 1),
        )
        select_button = Button(
            text="Use CSV",
            background_normal="",
            background_down="",
            background_color=(0.21, 0.56, 0.39, 1),
            color=(1, 1, 1, 1),
        )
        actions.add_widget(cancel_button)
        actions.add_widget(select_button)

        content = BoxLayout(orientation="vertical", spacing=dp(12), padding=dp(14))
        content.add_widget(chooser)
        content.add_widget(actions)

        popup = Popup(
            title="Choose CSV Backup",
            content=content,
            size_hint=(0.96, 0.92),
            auto_dismiss=False,
        )
        cancel_button.bind(on_release=lambda _instance: popup.dismiss())
        select_button.bind(on_release=lambda _instance: self._select_csv_import_path(chooser, popup))
        popup.open()

    def _select_csv_import_path(self, chooser: FileChooserListView, popup: Popup) -> None:
        selection = chooser.selection
        if not selection:
            self._set_transfer_status("Choose a CSV file first.", is_error=True)
            return
        popup.dismiss()
        self._apply_csv_import_selection(selection)

    def _handle_csv_import_selection(self, selection: list[str] | tuple[str, ...]) -> None:
        Clock.schedule_once(lambda _dt: self._apply_csv_import_selection(selection), 0)

    @mainthread
    def _apply_csv_import_selection(self, selection: list[str] | tuple[str, ...]) -> None:
        if not selection:
            self._set_transfer_status("CSV import was cancelled.", is_error=True)
            return

        raw_path = str(selection[0]).strip()
        display_name = get_csv_display_name(raw_path) or self._friendly_csv_name(raw_path)

        try:
            materialized_path = materialize_selected_csv(raw_path)
            csv_path = materialized_path if materialized_path is not None else Path(raw_path).expanduser()
            if not csv_path.exists() or csv_path.suffix.lower() != ".csv":
                self._set_transfer_status("Please choose a valid CSV file.", is_error=True)
                return
            result = parse_transactions_csv(csv_path, self.repository.list_expenses(limit=None))
        except Exception as exc:
            self._set_transfer_status(f"Unable to read CSV: {type(exc).__name__}: {exc}", is_error=True)
            return

        self._set_transfer_status(f"Loaded CSV backup {display_name}. Review the import summary.", is_error=False)
        self._open_csv_import_preview(result, display_name)

    def _open_csv_import_preview(self, result: CsvImportResult, display_name: str) -> None:
        content = BoxLayout(orientation="vertical", spacing=dp(12), padding=dp(16))

        title = Label(
            text="Import CSV Preview",
            size_hint_y=None,
            height=dp(28),
            halign="left",
            valign="middle",
            font_size="20sp",
            bold=True,
            color=(0.14, 0.18, 0.16, 1),
        )
        title.bind(size=lambda instance, _value: setattr(instance, "text_size", instance.size))
        summary = Label(
            text=(
                f"{display_name}\n\n"
                f"Rows found: {result.total_rows}\n"
                f"Ready to import: {len(result.importable_rows)}\n"
                f"Invalid rows skipped: {len(result.invalid_rows)}"
            ),
            size_hint_y=None,
            height=dp(128),
            halign="left",
            valign="top",
            color=(0.32, 0.36, 0.34, 1),
        )
        summary.bind(size=lambda instance, _value: setattr(instance, "text_size", (instance.width, None)))
        content.add_widget(title)
        content.add_widget(summary)

        if result.missing_headers:
            error_label = Label(
                text="Missing headers: " + ", ".join(result.missing_headers),
                size_hint_y=None,
                height=dp(44),
                halign="left",
                valign="top",
                color=(0.78, 0.24, 0.18, 1),
            )
            error_label.bind(size=lambda instance, _value: setattr(instance, "text_size", (instance.width, None)))
            content.add_widget(error_label)
        elif result.invalid_rows:
            preview_text = "\n".join(
                f"Row {issue.row_number}: {issue.message}" for issue in result.invalid_rows[:3]
            )
            invalid_label = Label(
                text=preview_text,
                size_hint_y=None,
                height=dp(70),
                halign="left",
                valign="top",
                color=(0.68, 0.24, 0.2, 1),
            )
            invalid_label.bind(size=lambda instance, _value: setattr(instance, "text_size", (instance.width, None)))
            content.add_widget(invalid_label)

        buttons = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(10))
        cancel_button = Button(
            text="Cancel",
            background_normal="",
            background_down="",
            background_color=(0.46, 0.51, 0.49, 1),
            color=(1, 1, 1, 1),
        )
        import_button = Button(
            text="Import Valid Rows",
            disabled=bool(result.missing_headers or not result.importable_rows),
            background_normal="",
            background_down="",
            background_color=(0.21, 0.56, 0.39, 1) if result.importable_rows and not result.missing_headers else (0.7, 0.72, 0.71, 1),
            color=(1, 1, 1, 1),
        )
        buttons.add_widget(cancel_button)
        buttons.add_widget(import_button)
        content.add_widget(buttons)

        popup = Popup(title="", content=content, size_hint=(0.9, 0.5), auto_dismiss=False, separator_height=0)
        cancel_button.bind(on_release=lambda _instance: popup.dismiss())
        import_button.bind(on_release=lambda _instance: self._commit_csv_import(result, popup))
        popup.open()

    def _commit_csv_import(self, result: CsvImportResult, popup: Popup) -> None:
        imported = 0
        for expense in result.importable_rows:
            self.repository.add_expense(expense)
            imported += 1

        popup.dismiss()
        self.refresh_dashboard()
        transactions_screen = self.manager.get_screen("transactions")
        transactions_screen.refresh_expenses()
        self.show_saved_status(f"Imported {imported} transaction(s) from CSV.")
        self._set_transfer_status(
            f"Imported {imported} row(s). Skipped {len(result.invalid_rows)} invalid rows.",
            is_error=False,
        )

    def _default_csv_dir(self) -> Path:
        candidates = [
            Path.cwd() / "exports",
            Path.cwd() / "statements",
            Path.home() / "Downloads",
            Path("/storage/emulated/0/Download"),
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return Path.cwd()

    def _friendly_csv_name(self, raw_path: str, fallback: str = "") -> str:
        display_name = get_csv_display_name(raw_path)
        if display_name:
            return display_name

        decoded = unquote(str(raw_path).strip())
        matches = re.findall(r"([^/\\?#]+\.csv)\b", decoded, flags=re.IGNORECASE)
        if matches:
            return matches[-1]

        document_match = re.search(r"(?:document:|document%3A)([^/?#]+)$", str(raw_path), flags=re.IGNORECASE)
        if document_match:
            return f"{document_match.group(1)}.csv"

        if fallback:
            return fallback
        return "transactions.csv"

    def _refresh_empty_card(self, instance: BoxLayout) -> None:
        from kivy.graphics import Color, RoundedRectangle

        instance.canvas.before.clear()
        with instance.canvas.before:
            Color(1, 1, 1, 1)
            RoundedRectangle(pos=instance.pos, size=instance.size, radius=[24, 24, 24, 24])

class TransactionsScreen(Screen):
    repository = ObjectProperty(allownone=False)
    status_message = StringProperty("Review saved transactions and keep the ledger clean.")
    status_color = ListProperty([0.84, 0.93, 0.89, 1])
    start_date_filter = StringProperty("")
    end_date_filter = StringProperty("")
    start_date_filter_text = StringProperty("Start Date")
    end_date_filter_text = StringProperty("End Date")

    def on_pre_enter(self, *args) -> None:
        self.refresh_expenses()
        return super().on_pre_enter(*args)

    def refresh_expenses(self) -> None:
        container = self.ids.list_container
        container.clear_widgets()
        expenses = self._get_visible_expenses()

        if not expenses:
            empty_label = Label(
                text="No matching transactions yet.",
                halign="center",
                valign="middle",
                color=(0.28, 0.32, 0.3, 1),
            )
            empty_label.bind(size=lambda instance, _value: setattr(instance, "text_size", (instance.width - 24, None)))
            container.add_widget(BoxLayout(size_hint_y=None, height=180))
            empty_state = container.children[0]
            empty_state.padding = 18
            empty_state.bind(
                pos=lambda instance, _value: self._refresh_empty_card(instance),
                size=lambda instance, _value: self._refresh_empty_card(instance),
            )
            self._refresh_empty_card(empty_state)
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

    def clear_filters(self) -> None:
        self.start_date_filter = ""
        self.end_date_filter = ""
        self.start_date_filter_text = "Start Date"
        self.end_date_filter_text = "End Date"
        self.ids.search_input.text = ""
        self.ids.payment_filter_input.text = "All Methods"
        self.ids.sort_input.text = "Newest"
        self.refresh_expenses()

    def open_start_date_picker(self) -> None:
        popup = DatePickerPopup(
            selected_date=self._selected_filter_date(self.start_date_filter),
            on_select=self._set_start_date_filter,
        )
        popup.open()

    def open_end_date_picker(self) -> None:
        popup = DatePickerPopup(
            selected_date=self._selected_filter_date(self.end_date_filter),
            on_select=self._set_end_date_filter,
        )
        popup.open()

    def _set_start_date_filter(self, selected: date) -> None:
        self.start_date_filter = selected.isoformat()
        self.start_date_filter_text = self.start_date_filter
        if self.end_date_filter and self.start_date_filter > self.end_date_filter:
            self.end_date_filter = ""
            self.end_date_filter_text = "End Date"
            self._set_status("Start date updated. Choose an end date to complete the range.", is_error=False)
        self.refresh_expenses()

    def _set_end_date_filter(self, selected: date) -> None:
        self.end_date_filter = selected.isoformat()
        self.end_date_filter_text = self.end_date_filter
        if self.start_date_filter and self.end_date_filter < self.start_date_filter:
            self.start_date_filter = ""
            self.start_date_filter_text = "Start Date"
            self._set_status("End date updated. Choose a start date to complete the range.", is_error=False)
        self.refresh_expenses()

    def _selected_filter_date(self, raw_value: str) -> date:
        try:
            return date.fromisoformat(raw_value) if raw_value else date.today()
        except ValueError:
            return date.today()

    def edit_expense(self, expense_id: int | None) -> None:
        if expense_id is None:
            self._set_status("Unable to open this transaction.", is_error=True)
            return

        edit_screen = self.manager.get_screen("edit")
        edit_screen.load_expense(expense_id)
        self.manager.current = "edit"

    def view_expense(self, expense_id: int | None) -> None:
        if expense_id is None:
            self._set_status("Unable to open this transaction.", is_error=True)
            return

        expense = self.repository.get_expense(expense_id)
        if expense is None:
            self._set_status("Transaction not found.", is_error=True)
            self.refresh_expenses()
            return

        self._open_expense_detail_popup(expense)

    def show_saved_status(self, message: str) -> None:
        self._set_status(message, is_error=False)

    def confirm_delete(self, expense_id: int | None) -> None:
        if expense_id is None:
            self._set_status("Unable to delete this transaction.", is_error=True)
            return

        expense = self.repository.get_expense(expense_id)
        if expense is None:
            self._set_status("Transaction not found.", is_error=True)
            self.refresh_expenses()
            return

        content = BoxLayout(orientation="vertical", spacing=12, padding=16)
        content.add_widget(Label(text="Are you sure you want to delete this transaction?", halign="center", valign="middle", color=(0.15, 0.18, 0.16, 1)))
        buttons = BoxLayout(size_hint_y=None, height=58, spacing=10)
        popup = Popup(title="Delete Transaction", content=content, size_hint=(0.85, None), height=238, auto_dismiss=False)
        no_button = Button(text="No", background_normal="", background_color=(0.4, 0.45, 0.43, 1), size_hint_y=None, height=58)
        yes_button = Button(text="Yes", background_normal="", background_color=(0.68, 0.24, 0.2, 1), size_hint_y=None, height=58)
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
        home_screen = self.manager.get_screen("home")
        home_screen.refresh_dashboard()

    def _set_status(self, message: str, *, is_error: bool) -> None:
        self.status_message = message
        self.status_color = [0.98, 0.82, 0.78, 1] if is_error else [0.84, 0.93, 0.89, 1]

    def _get_visible_expenses(self) -> list[ExpenseRecord]:
        expenses = self.repository.list_expenses(limit=None)
        search_text = self.ids.search_input.text.strip().lower() if "search_input" in self.ids else ""
        payment_method = self.ids.payment_filter_input.text if "payment_filter_input" in self.ids else "All Methods"
        sort_option = self.ids.sort_input.text if "sort_input" in self.ids else "Newest"

        if search_text:
            expenses = [
                expense
                for expense in expenses
                if search_text in expense.merchant.lower() or search_text in expense.notes.lower()
            ]

        if payment_method != "All Methods":
            expenses = [expense for expense in expenses if expense.payment_method == payment_method]

        if self.start_date_filter:
            expenses = [expense for expense in expenses if expense.expense_date >= self.start_date_filter]

        if self.end_date_filter:
            expenses = [expense for expense in expenses if expense.expense_date <= self.end_date_filter]

        if sort_option == "Oldest":
            expenses.sort(key=lambda expense: (expense.expense_date, expense.id or 0))
        elif sort_option == "Amount High-Low":
            expenses.sort(key=lambda expense: (-expense.amount, expense.expense_date), reverse=False)
        elif sort_option == "Amount Low-High":
            expenses.sort(key=lambda expense: (expense.amount, expense.expense_date))
        elif sort_option == "Merchant A-Z":
            expenses.sort(key=lambda expense: (expense.merchant.lower(), expense.expense_date), reverse=False)
        else:
            expenses.sort(key=lambda expense: (expense.expense_date, expense.id or 0), reverse=True)

        return expenses

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


class NotificationsScreen(Screen):
    repository = ObjectProperty(allownone=False)
    status_message = StringProperty("Choose a statement PDF to begin.")
    status_color = ListProperty([0.84, 0.93, 0.89, 1])
    selected_statement_path = StringProperty("")
    selected_file_label = StringProperty("No PDF selected yet.")
    selected_source_name = StringProperty("")

    def on_pre_enter(self, *args) -> None:
        self.refresh_reviews()
        return super().on_pre_enter(*args)

    def open_file_browser(self) -> None:
        try:
            if open_pdf_picker(self._handle_native_selection):
                self._set_status("File manager opened. Choose a PDF statement there.", is_error=False)
                return
        except Exception:
            pass
        self._open_embedded_file_browser()

    def _open_embedded_file_browser(self) -> None:
        chooser = FileChooserListView(
            path=str(self._default_statement_dir()),
            filters=["*.pdf"],
            multiselect=False,
        )

        actions = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(10))
        cancel_button = Button(
            text="Cancel",
            background_normal="",
            background_down="",
            background_color=(0.46, 0.51, 0.49, 1),
            color=(1, 1, 1, 1),
        )
        select_button = Button(
            text="Use PDF",
            background_normal="",
            background_down="",
            background_color=(0.21, 0.56, 0.39, 1),
            color=(1, 1, 1, 1),
        )
        actions.add_widget(cancel_button)
        actions.add_widget(select_button)

        content = BoxLayout(orientation="vertical", spacing=dp(12), padding=dp(14))
        content.add_widget(chooser)
        content.add_widget(actions)

        popup = Popup(
            title="Choose Statement PDF",
            content=content,
            size_hint=(0.96, 0.92),
            auto_dismiss=False,
        )
        cancel_button.bind(on_release=lambda _instance: popup.dismiss())
        select_button.bind(on_release=lambda _instance: self._select_statement_path(chooser, popup))
        popup.open()

    def _handle_native_selection(self, selection: list[str] | tuple[str, ...]) -> None:
        Clock.schedule_once(lambda _dt: self._apply_native_selection(selection), 0)

    @mainthread
    def _apply_native_selection(self, selection: list[str] | tuple[str, ...]) -> None:
        if not selection:
            return
        selected_path = str(selection[0])
        display_name = self._friendly_pdf_name(selected_path)
        self.selected_statement_path = selected_path
        self.selected_source_name = display_name
        self._set_status(f"Selected {display_name}. Tap Upload when ready.", is_error=False)
        self.selected_file_label = display_name

    def import_statement(self) -> None:
        raw_path = self.selected_statement_path.strip()
        if not raw_path:
            self._set_status("Choose a statement PDF first.", is_error=True)
            return

        if getattr(self, "_statement_import_in_progress", False):
            self._set_status("Statement import is already in progress.", is_error=True)
            return

        self._statement_import_in_progress = True
        self._show_statement_loader()
        source_name = self.selected_source_name or self._friendly_pdf_name(raw_path, fallback="statement.pdf")
        Thread(
            target=self._run_statement_import,
            args=(raw_path, source_name),
            daemon=True,
        ).start()

    def _run_statement_import(self, raw_path: str, source_name: str) -> None:
        try:
            materialized_path = materialize_selected_pdf(raw_path)
            if materialized_path is None:
                path = Path(raw_path).expanduser()
            else:
                path = materialized_path

            if not path.exists() or path.suffix.lower() != ".pdf":
                raise ValueError("Please choose a valid PDF file.")

            result = parse_statement_pdf(path, progress_callback=self._statement_progress_callback)
        except Exception as exc:
            app = App.get_running_app()
            log_path = ""
            if app is not None and hasattr(app, "_write_crash_log"):
                log_path = app._write_crash_log(traceback.format_exc())
            message = f"Unable to import statement: {type(exc).__name__}: {exc}"
            if log_path:
                message = f"{message} | Log: {log_path}"
            Clock.schedule_once(lambda _dt: self._finish_statement_import_error(message), 0)
            return

        Clock.schedule_once(
            lambda _dt: self._finish_statement_import_success(result, source_name),
            0,
        )

    def _statement_progress_callback(self, message: str, percent: int) -> None:
        Clock.schedule_once(lambda _dt: self._update_statement_loader(message, percent), 0)

    @mainthread
    def _finish_statement_import_success(self, result, source_name: str) -> None:
        imported = 0
        for txn in result.transactions:
            self.repository.add_statement_review(
                StatementReviewRecord(
                    id=None,
                    bank_name=result.bank_name,
                    account_last4=result.account_last4,
                    source_file=source_name,
                    amount=txn.amount,
                    direction=txn.direction,
                    merchant=txn.merchant,
                    payment_method=txn.payment_method,
                    expense_date=txn.txn_date,
                    reference_no=txn.reference_no,
                    raw_row=txn.raw_row,
                )
            )
            imported += 1

        warning_suffix = f" {len(result.warnings)} row(s) need manual attention." if result.warnings else ""
        self._set_status(
            f"Imported {imported} row(s) from {result.bank_name} statement.{warning_suffix}",
            is_error=False,
        )
        self.selected_statement_path = ""
        self.selected_source_name = ""
        self.selected_file_label = "No PDF selected yet."
        self.refresh_reviews()
        self._hide_statement_loader()
        self._statement_import_in_progress = False

    @mainthread
    def _finish_statement_import_error(self, message: str) -> None:
        self._hide_statement_loader()
        self._statement_import_in_progress = False
        self._set_status(message, is_error=True)

    def _show_statement_loader(self) -> None:
        if getattr(self, "_statement_loader_modal", None) is not None:
            return

        modal = ModalView(
            auto_dismiss=False,
            size_hint=(1, 1),
            background_color=(0.05, 0.07, 0.06, 0.58),
        )
        outer = AnchorLayout(anchor_x="center", anchor_y="center")
        card = BoxLayout(
            orientation="vertical",
            size_hint=(None, None),
            size=(dp(250), dp(240)),
            spacing=dp(12),
            padding=dp(18),
        )

        def redraw_card(instance: BoxLayout, _value) -> None:
            from kivy.graphics import Color, RoundedRectangle

            instance.canvas.before.clear()
            with instance.canvas.before:
                Color(0.99, 0.98, 0.96, 1)
                RoundedRectangle(pos=instance.pos, size=instance.size, radius=[20, 20, 20, 20])

        card.bind(pos=redraw_card, size=redraw_card)
        redraw_card(card, None)

        title = Label(
            text="Parsing Statement",
            size_hint_y=None,
            height=dp(28),
            halign="center",
            valign="middle",
            font_size="20sp",
            bold=True,
            color=(0.14, 0.18, 0.16, 1),
        )
        title.bind(size=lambda instance, _value: setattr(instance, "text_size", instance.size))

        ring = CircularProgressRing(size_hint=(None, None), size=(dp(110), dp(110)))
        ring.progress = 0
        percent_label = Label(
            text="0%",
            size_hint_y=None,
            height=dp(24),
            halign="center",
            valign="middle",
            font_size="18sp",
            bold=True,
            color=(0.13, 0.24, 0.19, 1),
        )
        percent_label.bind(size=lambda instance, _value: setattr(instance, "text_size", instance.size))

        progress_box = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(146), spacing=dp(12))
        ring_anchor = AnchorLayout(anchor_x="center", anchor_y="center")
        ring_anchor.add_widget(ring)
        progress_box.add_widget(ring_anchor)
        progress_box.add_widget(percent_label)

        status_label = Label(
            text="Preparing statement parser...",
            size_hint_y=None,
            height=dp(32),
            halign="center",
            valign="middle",
            color=(0.42, 0.47, 0.45, 1),
        )
        status_label.bind(size=lambda instance, _value: setattr(instance, "text_size", (instance.width, None)))

        card.add_widget(title)
        card.add_widget(progress_box)
        card.add_widget(status_label)
        outer.add_widget(card)
        modal.add_widget(outer)

        self._statement_loader_modal = modal
        self._statement_loader_ring = ring
        self._statement_loader_percent_label = percent_label
        self._statement_loader_status_label = status_label
        modal.open()

    @mainthread
    def _update_statement_loader(self, message: str, percent: int) -> None:
        ring = getattr(self, "_statement_loader_ring", None)
        percent_label = getattr(self, "_statement_loader_percent_label", None)
        status_label = getattr(self, "_statement_loader_status_label", None)
        if ring is None or percent_label is None or status_label is None:
            return

        ring.progress = percent
        percent_label.text = f"{percent}%"
        status_label.text = message

    @mainthread
    def _hide_statement_loader(self) -> None:
        modal = getattr(self, "_statement_loader_modal", None)
        if modal is not None:
            modal.dismiss()
        self._statement_loader_modal = None
        self._statement_loader_ring = None
        self._statement_loader_percent_label = None
        self._statement_loader_status_label = None

    def save_all_debits(self) -> None:
        saved = 0
        for review in self.repository.list_statement_reviews(status="pending"):
            if review.direction != "debit":
                continue
            self.repository.confirm_statement_review(review)
            saved += 1

        if not saved:
            self._set_status("No debit transactions are ready to save.", is_error=True)
            return

        self._set_status(f"Saved {saved} debit transaction(s) from statements.", is_error=False)
        self.refresh_reviews()
        home_screen = self.manager.get_screen("home")
        transactions_screen = self.manager.get_screen("transactions")
        home_screen.show_saved_status(f"Saved {saved} statement transaction(s) to the main list.")
        home_screen.refresh_dashboard()
        transactions_screen.refresh_expenses()

    def clear_pending_reviews(self) -> None:
        cleared = self.repository.clear_statement_reviews(status="pending")
        if not cleared:
            self._set_status("No pending statement rows are available to clear.", is_error=True)
            return

        self._set_status(f"Cleared {cleared} pending statement row(s).", is_error=False)
        self.refresh_reviews()

    def refresh_reviews(self) -> None:
        container = self.ids.review_container
        container.clear_widgets()
        reviews = self._filtered_reviews()

        if not reviews:
            empty = Label(
                text="No pending statement rows yet.",
                size_hint_y=None,
                height=dp(54),
                halign="center",
                valign="middle",
                color=(0.32, 0.36, 0.34, 1),
            )
            empty.bind(size=lambda instance, _value: setattr(instance, "text_size", instance.size))
            container.add_widget(empty)
            return

        for review in reviews:
            container.add_widget(self._build_review_card(review))

    def _build_review_card(self, review: StatementReviewRecord) -> BoxLayout:
        card = BoxLayout(size_hint_y=None, orientation="vertical", padding=(0, 0, 0, dp(6)))
        surface = BoxLayout(
            orientation="vertical",
            spacing=dp(8),
            padding=dp(14),
            size_hint_y=None,
        )
        surface.bind(minimum_height=lambda instance, value: setattr(instance, "height", value))
        card.bind(minimum_height=lambda instance, value: setattr(instance, "height", value))

        def redraw_card(instance: BoxLayout, _value) -> None:
            from kivy.graphics import Color, RoundedRectangle

            instance.canvas.before.clear()
            with instance.canvas.before:
                Color(1, 1, 1, 1)
                RoundedRectangle(pos=instance.pos, size=instance.size, radius=[22, 22, 22, 22])

        surface.bind(pos=redraw_card, size=redraw_card)
        redraw_card(surface, None)

        header = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(8))
        source = Label(
            text=f"{review.bank_name} x{review.account_last4}",
            halign="left",
            valign="middle",
            color=(0.11, 0.31, 0.21, 1),
            bold=True,
            font_size="15sp",
        )
        direction = Label(
            text=review.direction.title(),
            size_hint_x=None,
            width=dp(92),
            halign="center",
            valign="middle",
            color=(0.68, 0.24, 0.2, 1) if review.direction != "debit" else (0.11, 0.31, 0.21, 1),
            bold=True,
            font_size="14sp",
        )
        amount = Label(
            text=f"Rs. {review.amount:.2f}",
            size_hint_x=None,
            width=dp(124),
            halign="right",
            valign="middle",
            color=(0.11, 0.31, 0.21, 1),
            bold=True,
            font_size="15sp",
        )
        source.bind(size=lambda instance, _value: setattr(instance, "text_size", (instance.width, instance.height)))
        direction.bind(size=lambda instance, _value: setattr(instance, "text_size", instance.size))
        amount.bind(size=lambda instance, _value: setattr(instance, "text_size", instance.size))
        header.add_widget(source)
        header.add_widget(direction)
        header.add_widget(amount)
        surface.add_widget(header)

        merchant = Label(
            text=review.merchant,
            size_hint_y=None,
            height=dp(38),
            halign="left",
            valign="middle",
            font_size="19sp",
            bold=True,
            color=(0.15, 0.18, 0.16, 1),
        )
        merchant.bind(size=lambda instance, _value: setattr(instance, "text_size", instance.size))
        surface.add_widget(merchant)

        meta = Label(
            text=f"{review.payment_method}  |  {review.expense_date}  |  {review.source_file}",
            size_hint_y=None,
            height=dp(24),
            halign="left",
            valign="middle",
            color=(0.47, 0.52, 0.49, 1),
            font_size="14sp",
            shorten=True,
            shorten_from="right",
        )
        meta.bind(size=lambda instance, _value: setattr(instance, "text_size", instance.size))
        surface.add_widget(meta)

        raw_row = Label(
            text=review.raw_row,
            size_hint_y=None,
            height=dp(42),
            halign="left",
            valign="top",
            color=(0.47, 0.52, 0.49, 1),
            shorten=True,
            shorten_from="right",
            font_size="14sp",
        )
        raw_row.bind(size=lambda instance, _value: setattr(instance, "text_size", (instance.width, instance.height)))
        surface.add_widget(raw_row)

        actions = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(10))
        review_button = Button(
            text="Review",
            background_normal="",
            background_down="",
            background_color=(0.84, 0.92, 0.88, 1),
            color=(0.13, 0.24, 0.19, 1),
            font_size="16sp",
        )
        save_button = Button(
            text="Save" if review.direction == "debit" else "Debit Only",
            disabled=review.direction != "debit",
            background_normal="",
            background_down="",
            background_color=(0.21, 0.56, 0.39, 1) if review.direction == "debit" else (0.7, 0.72, 0.71, 1),
            color=(1, 1, 1, 1),
            font_size="16sp",
        )
        reject_button = Button(
            text="Reject",
            background_normal="",
            background_down="",
            background_color=(0.68, 0.24, 0.2, 1),
            color=(1, 1, 1, 1),
            font_size="16sp",
        )
        review_button.bind(on_release=lambda _instance: self.open_review_popup(review.id or 0))
        save_button.bind(on_release=lambda _instance: self.save_review(review.id or 0))
        reject_button.bind(on_release=lambda _instance: self.reject_review(review.id or 0))
        actions.add_widget(review_button)
        actions.add_widget(save_button)
        actions.add_widget(reject_button)
        surface.add_widget(actions)
        card.add_widget(surface)
        return card

    def open_review_popup(self, review_id: int) -> None:
        review = self.repository.get_statement_review(review_id)
        if review is None:
            self._set_status("Statement review not found.", is_error=True)
            self.refresh_reviews()
            return

        content = ReviewPopupContent(orientation="vertical", spacing=dp(10), padding=dp(16))
        def redraw_content(instance: BoxLayout, _value) -> None:
            from kivy.graphics import Color, RoundedRectangle

            instance.canvas.before.clear()
            with instance.canvas.before:
                Color(0.97, 0.95, 0.91, 1)
                RoundedRectangle(pos=instance.pos, size=instance.size, radius=[18, 18, 18, 18])

        content.bind(pos=redraw_content, size=redraw_content)
        redraw_content(content, None)
        fields: dict[str, object] = {}

        amount_label = Label(text="Amount", size_hint_y=None, height=dp(22), halign="left", valign="middle", color=(0.17, 0.20, 0.18, 1), bold=True)
        amount_label.bind(size=lambda instance, _value: setattr(instance, "text_size", instance.size))
        amount_input = TextInput(text=f"{review.amount:.2f}", size_hint_y=None, height=dp(46), multiline=False)
        fields["amount"] = amount_input
        content.add_widget(amount_label)
        content.add_widget(amount_input)

        direction_label = Label(text="Transaction Direction", size_hint_y=None, height=dp(22), halign="left", valign="middle", color=(0.17, 0.20, 0.18, 1), bold=True)
        direction_label.bind(size=lambda instance, _value: setattr(instance, "text_size", instance.size))
        direction_spinner = Spinner(
            text=review.direction.title(),
            values=["Debit", "Credit", "Unknown"],
            size_hint_y=None,
            height=dp(46),
            background_normal="",
            background_color=(1, 1, 1, 1),
            color=(0.15, 0.18, 0.16, 1),
        )
        fields["direction"] = direction_spinner
        content.add_widget(direction_label)
        content.add_widget(direction_spinner)

        merchant_label = Label(text="Merchant", size_hint_y=None, height=dp(22), halign="left", valign="middle", color=(0.17, 0.20, 0.18, 1), bold=True)
        merchant_label.bind(size=lambda instance, _value: setattr(instance, "text_size", instance.size))
        merchant_input = TextInput(text=review.merchant, size_hint_y=None, height=dp(46), multiline=False)
        fields["merchant"] = merchant_input
        content.add_widget(merchant_label)
        content.add_widget(merchant_input)

        payment_label = Label(text="Payment Method", size_hint_y=None, height=dp(22), halign="left", valign="middle", color=(0.17, 0.20, 0.18, 1), bold=True)
        payment_label.bind(size=lambda instance, _value: setattr(instance, "text_size", instance.size))
        payment_spinner = Spinner(
            text=review.payment_method,
            values=["UPI", "Card", "Cash", "NEFT", "IMPS", "ACH", "Bank Transfer", "Other"],
            size_hint_y=None,
            height=dp(46),
            background_normal="",
            background_color=(1, 1, 1, 1),
            color=(0.15, 0.18, 0.16, 1),
        )
        fields["payment_method"] = payment_spinner
        content.add_widget(payment_label)
        content.add_widget(payment_spinner)

        date_label = Label(text="Date", size_hint_y=None, height=dp(22), halign="left", valign="middle", color=(0.17, 0.20, 0.18, 1), bold=True)
        date_label.bind(size=lambda instance, _value: setattr(instance, "text_size", instance.size))
        date_input = TextInput(text=review.expense_date, size_hint_y=None, height=dp(46), multiline=False)
        fields["expense_date"] = date_input
        content.add_widget(date_label)
        content.add_widget(date_input)

        raw_label = Label(text="Raw Row", size_hint_y=None, height=dp(22), halign="left", valign="middle", color=(0.17, 0.20, 0.18, 1), bold=True)
        raw_label.bind(size=lambda instance, _value: setattr(instance, "text_size", instance.size))
        raw_box = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(128), spacing=dp(8), padding=(dp(10), dp(10), dp(10), dp(10)))

        def redraw_raw_box(instance: BoxLayout, _value) -> None:
            from kivy.graphics import Color, RoundedRectangle

            instance.canvas.before.clear()
            with instance.canvas.before:
                Color(1, 1, 1, 1)
                RoundedRectangle(pos=instance.pos, size=instance.size, radius=[12, 12, 12, 12])

        raw_box.bind(pos=redraw_raw_box, size=redraw_raw_box)
        redraw_raw_box(raw_box, None)

        raw_input = TextInput(
            text=review.raw_row,
            readonly=True,
            multiline=True,
            size_hint_y=None,
            height=dp(108),
            background_normal="",
            background_active="",
            background_color=(1, 1, 1, 1),
            foreground_color=(0.18, 0.22, 0.2, 1),
            cursor_color=(0.18, 0.22, 0.2, 1),
        )
        fields["raw_row"] = raw_input
        raw_input.bind(focus=lambda instance, value: not value and instance.cancel_selection())
        raw_box.add_widget(raw_input)
        content.add_widget(raw_label)
        content.add_widget(raw_box)
        content.selectable_input = raw_input

        buttons = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(10))
        cancel_button = Button(text="Cancel", background_normal="", background_down="", background_color=(0.46, 0.51, 0.49, 1), color=(1, 1, 1, 1))
        save_button = Button(text="Save Changes", background_normal="", background_down="", background_color=(0.21, 0.56, 0.39, 1), color=(1, 1, 1, 1))
        buttons.add_widget(cancel_button)
        buttons.add_widget(save_button)
        content.add_widget(buttons)

        popup = Popup(title="Review Statement Row", content=content, size_hint=(0.94, 0.9), auto_dismiss=False, separator_color=(0.21, 0.56, 0.39, 1))
        cancel_button.bind(on_release=lambda _instance: popup.dismiss())
        save_button.bind(on_release=lambda _instance: self._save_review_changes(review, fields, popup))
        popup.open()

    def _save_review_changes(self, review: StatementReviewRecord, fields: dict[str, object], popup: Popup) -> None:
        amount_text = str(fields["amount"].text).strip()
        merchant = " ".join(str(fields["merchant"].text).strip().split())
        payment_method = str(fields["payment_method"].text).strip()
        expense_date = str(fields["expense_date"].text).strip()
        direction = str(fields["direction"].text).strip().lower()

        if not amount_text or not merchant or not payment_method or not expense_date:
            self._set_status("Amount, merchant, payment method, and date are required.", is_error=True)
            return

        try:
            amount = float(amount_text)
        except ValueError:
            self._set_status("Please enter a valid amount for this statement row.", is_error=True)
            return

        try:
            date.fromisoformat(expense_date)
        except ValueError:
            self._set_status("Statement date must use YYYY-MM-DD.", is_error=True)
            return

        self.repository.update_statement_review(
            StatementReviewRecord(
                id=review.id,
                bank_name=review.bank_name,
                account_last4=review.account_last4,
                source_file=review.source_file,
                amount=amount,
                direction=direction,
                merchant=merchant,
                payment_method=payment_method,
                expense_date=expense_date,
                reference_no=review.reference_no,
                raw_row=review.raw_row,
                status=review.status,
            )
        )
        popup.dismiss()
        self._set_status("Statement row updated. Save only debit transactions when ready.", is_error=False)
        self.refresh_reviews()

    def save_review(self, review_id: int) -> None:
        review = self.repository.get_statement_review(review_id)
        if review is None:
            self._set_status("Statement review not found.", is_error=True)
            self.refresh_reviews()
            return
        if review.direction != "debit":
            self._set_status("Only debit transactions can be added to the main expense list.", is_error=True)
            return

        saved_expense = self.repository.confirm_statement_review(review)
        self._set_status(f"Saved Rs. {saved_expense.amount:.2f} from statements.", is_error=False)
        self.refresh_reviews()
        home_screen = self.manager.get_screen("home")
        transactions_screen = self.manager.get_screen("transactions")
        home_screen.show_saved_status(f"Saved Rs. {saved_expense.amount:.2f} for {saved_expense.merchant}.")
        home_screen.refresh_dashboard()
        transactions_screen.refresh_expenses()

    def reject_review(self, review_id: int) -> None:
        self.repository.reject_statement_review(review_id)
        self._set_status("Statement row removed from the review queue.", is_error=False)
        self.refresh_reviews()

    def _filtered_reviews(self) -> list[StatementReviewRecord]:
        reviews = self.repository.list_statement_reviews(status="pending")
        filter_value = self.ids.direction_filter_input.text
        if filter_value == "Debit Only":
            return [review for review in reviews if review.direction == "debit"]
        if filter_value == "Credit Only":
            return [review for review in reviews if review.direction == "credit"]
        return reviews

    def _select_statement_path(self, chooser: FileChooserListView, popup: Popup) -> None:
        selection = chooser.selection
        if not selection:
            self._set_status("Choose a PDF file first.", is_error=True)
            return
        selected_path = selection[0]
        display_name = self._friendly_pdf_name(selected_path)
        self.selected_statement_path = selected_path
        self.selected_source_name = display_name
        self.selected_file_label = display_name
        popup.dismiss()
        self._set_status(f"Selected {display_name}. Tap Upload when ready.", is_error=False)

    def _default_statement_dir(self) -> Path:
        candidates = [
            Path.cwd() / "statements",
            Path.home() / "Downloads",
            Path("/storage/emulated/0/Download"),
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return Path.cwd()

    def _set_status(self, message: str, *, is_error: bool) -> None:
        self.status_message = message
        self.status_color = [0.98, 0.82, 0.78, 1] if is_error else [0.84, 0.93, 0.89, 1]

    def open_info_tooltip(self) -> None:
        outer = BoxLayout(orientation="vertical", spacing=dp(12), padding=dp(14))

        header = BoxLayout(size_hint_y=None, height=dp(34), spacing=dp(10))
        title = Label(
            text="How It Works",
            halign="left",
            valign="middle",
            color=(0.14, 0.18, 0.16, 1),
            font_size="18sp",
            bold=True,
        )
        title.bind(size=lambda instance, _value: setattr(instance, "text_size", instance.size))
        close_button = Button(
            text="X",
            size_hint=(None, None),
            size=(dp(32), dp(32)),
            background_normal="",
            background_down="",
            background_color=(0.92, 0.94, 0.93, 1),
            color=(0.22, 0.26, 0.24, 1),
        )
        header.add_widget(title)
        header.add_widget(close_button)
        outer.add_widget(header)

        body = Label(
            text=(
                "Choose a bank statement PDF, upload it, review the parsed rows, "
                "and save only debit transactions to the main expense list."
            ),
            halign="left",
            valign="top",
            color=(0.18, 0.22, 0.2, 1),
            font_size="15sp",
        )
        body.bind(size=lambda instance, _value: setattr(instance, "text_size", (instance.width, None)))
        outer.add_widget(body)

        popup = Popup(
            title="",
            content=outer,
            size_hint=(0.82, 0.34),
            auto_dismiss=False,
            separator_height=0,
        )
        close_button.bind(on_release=lambda _instance: popup.dismiss())
        popup.open()

    def _friendly_pdf_name(self, raw_path: str, fallback: str = "") -> str:
        display_name = get_pdf_display_name(raw_path)
        if display_name:
            return display_name

        decoded = unquote(str(raw_path).strip())
        matches = re.findall(r'([^/\\?#]+\.pdf)\b', decoded, flags=re.IGNORECASE)
        if matches:
            return matches[-1]

        document_match = re.search(r'(?:document:|document%3A)([^/?#]+)$', str(raw_path), flags=re.IGNORECASE)
        if document_match:
            return f"{document_match.group(1)}.pdf"

        if fallback:
            return fallback

        return "selected_statement.pdf"



class VisualizationScreen(Screen):
    repository = ObjectProperty(allownone=False)
    chart_mode = StringProperty("monthly")
    selected_year_text = StringProperty("")
    chart_caption = StringProperty("Monthly spend")
    year_values = ListProperty([])

    def prepare_visualization(self) -> None:
        expenses = self.repository.list_expenses(limit=None)
        years = sorted({expense.expense_date[:4] for expense in expenses}, reverse=True)
        self.year_values = years or [str(date.today().year)]
        if self.selected_year_text not in self.year_values:
            self.selected_year_text = self.year_values[0]
        self.chart_mode = "monthly"
        self._sync_controls()
        self.refresh_chart()

    def on_pre_enter(self, *args) -> None:
        self._sync_controls()
        if self.repository.list_expenses(limit=None):
            self.refresh_chart()
        return super().on_pre_enter(*args)

    def set_mode(self, mode: str) -> None:
        if mode not in {"monthly", "yearly"}:
            return
        self.chart_mode = mode
        self._sync_controls()
        self.refresh_chart()

    def on_year_selected(self, year_text: str) -> None:
        self.selected_year_text = year_text
        if self.chart_mode == "monthly":
            self.refresh_chart()

    def go_back(self) -> None:
        self.manager.current = "home"

    def refresh_chart(self) -> None:
        chart_anchor = self.ids.chart_anchor
        chart_anchor.clear_widgets()
        expenses = self.repository.list_expenses(limit=None)
        if not expenses:
            placeholder = Label(
                text="Add expenses to see visualization.",
                halign="center",
                valign="middle",
                color=(0.32, 0.36, 0.34, 1),
            )
            placeholder.bind(size=lambda instance, _value: setattr(instance, "text_size", instance.size))
            chart_anchor.add_widget(placeholder)
            return

        labels, values, caption = self._build_chart_series(expenses, self.chart_mode, self.selected_year_text)
        self.chart_caption = caption
        chart_anchor.add_widget(self._build_visual_chart(labels, values))

    def _sync_controls(self) -> None:
        self.ids.monthly_button.background_color = (0.21, 0.56, 0.39, 1) if self.chart_mode == "monthly" else (0.9, 0.93, 0.91, 1)
        self.ids.monthly_button.color = (1, 1, 1, 1) if self.chart_mode == "monthly" else (0.14, 0.18, 0.16, 1)
        self.ids.yearly_button.background_color = (0.21, 0.56, 0.39, 1) if self.chart_mode == "yearly" else (0.9, 0.93, 0.91, 1)
        self.ids.yearly_button.color = (1, 1, 1, 1) if self.chart_mode == "yearly" else (0.14, 0.18, 0.16, 1)
        self.ids.selector_row.height = dp(46) if self.chart_mode == "monthly" else 0
        self.ids.selector_row.opacity = 1 if self.chart_mode == "monthly" else 0
        self.ids.year_spinner.text = self.selected_year_text
        self.ids.year_spinner.values = self.year_values

    def _build_chart_series(
        self,
        expenses: list[ExpenseRecord],
        mode: str,
        selected_year: str,
    ) -> tuple[list[str], list[float], str]:
        if mode == "yearly":
            totals: defaultdict[str, float] = defaultdict(float)
            for expense in expenses:
                totals[expense.expense_date[:4]] += expense.amount
            years = sorted(totals.keys())
            return years, [totals[year] for year in years], "Yearly spend overview"

        totals = {month: 0.0 for month in range(1, 13)}
        for expense in expenses:
            if expense.expense_date.startswith(selected_year):
                totals[int(expense.expense_date[5:7])] += expense.amount
        labels = list(calendar.month_abbr)[1:]
        values = [totals[month] for month in range(1, 13)]
        return labels, values, f"Monthly spend for {selected_year}"

    def _build_visual_chart(self, labels: list[str], values: list[float]) -> BoxLayout:
        chart = BoxLayout(
            orientation="vertical",
            spacing=dp(8),
            size_hint=(None, None),
            size=(max(dp(640), len(labels) * dp(54)), dp(360)),
        )

        body = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(310), spacing=dp(8))
        y_axis = BoxLayout(orientation="vertical", size_hint_x=None, width=dp(56))

        max_value = max(values) if values else 1.0
        if max_value <= 0:
            max_value = 1.0
        tick_values = [max_value * ratio for ratio in (1, 0.75, 0.5, 0.25, 0)]
        for tick in tick_values:
            tick_label = Label(
                text=f"{int(round(tick))}",
                halign="right",
                valign="middle",
                color=(0.43, 0.47, 0.45, 1),
                font_size="12sp",
            )
            tick_label.bind(size=lambda instance, _value: setattr(instance, "text_size", instance.size))
            y_axis.add_widget(tick_label)
        body.add_widget(y_axis)

        plot = BoxLayout(orientation="vertical")

        def redraw_plot(instance: BoxLayout, _value) -> None:
            from kivy.graphics import Color, Line

            instance.canvas.before.clear()
            with instance.canvas.before:
                Color(0.64, 0.28, 0.67, 1)
                Line(points=[instance.x, instance.y, instance.x, instance.top], width=1.5)
                Line(points=[instance.x, instance.y, instance.right, instance.y], width=1.5)

        plot.bind(pos=redraw_plot, size=redraw_plot)
        redraw_plot(plot, None)

        bars_anchor = AnchorLayout(anchor_x="center", anchor_y="bottom")
        bars_row = BoxLayout(
            orientation="horizontal",
            size_hint=(None, None),
            size=(max(dp(560), len(labels) * dp(46)), dp(250)),
            spacing=dp(8),
            padding=(dp(6), 0, dp(6), 0),
        )
        for label_text, amount in zip(labels, values):
            bars_row.add_widget(self._build_bar_column(label_text, amount, max_value))
        bars_anchor.add_widget(bars_row)
        plot.add_widget(bars_anchor)
        body.add_widget(plot)
        chart.add_widget(body)

        return chart

    def _build_bar_column(self, label_text: str, amount: float, max_value: float) -> BoxLayout:
        column = BoxLayout(orientation="vertical", spacing=dp(8), size_hint_x=None, width=dp(38))

        value_label = Label(
            text=f"{int(round(amount))}" if amount else "0",
            size_hint_y=None,
            height=dp(18),
            halign="center",
            valign="middle",
            color=(0.33, 0.37, 0.35, 1),
            font_size="10sp",
        )
        value_label.bind(size=lambda instance, _value: setattr(instance, "text_size", instance.size))
        column.add_widget(value_label)

        bar_area = AnchorLayout(anchor_x="center", anchor_y="bottom", size_hint_y=None, height=dp(190))
        bar_height = dp(12) if amount <= 0 else max(dp(18), dp(170) * (amount / max_value))
        bar = Widget(size_hint=(None, None), size=(dp(22), bar_height))

        def redraw_bar(instance: Widget, _value) -> None:
            from kivy.graphics import Color, RoundedRectangle

            instance.canvas.before.clear()
            with instance.canvas.before:
                Color(0.1, 0.77, 0.79, 1)
                RoundedRectangle(pos=instance.pos, size=instance.size, radius=[6, 6, 0, 0])

        bar.bind(pos=redraw_bar, size=redraw_bar)
        redraw_bar(bar, None)
        bar_area.add_widget(bar)
        column.add_widget(bar_area)

        label = Label(
            text=label_text,
            size_hint_y=None,
            height=dp(20),
            halign="center",
            valign="middle",
            color=(0.43, 0.18, 0.48, 1),
            font_size="11sp",
        )
        label.bind(size=lambda instance, _value: setattr(instance, "text_size", instance.size))
        column.add_widget(label)
        return column


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
        merchant = " ".join(self.ids.merchant_input.text.strip().split())
        payment_method = self.ids.payment_method_input.text.strip()
        expense_date = self.ids.date_button.text.strip()
        notes = " ".join(self.ids.notes_input.text.strip().split())

        if not amount_text or not merchant or not payment_method or not expense_date:
            self._set_feedback("Please enter amount, merchant, payment method, and date.", is_error=True)
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

        home_screen = self.manager.get_screen("home")
        transactions_screen = self.manager.get_screen("transactions")
        home_screen.show_saved_status(status_message)
        home_screen.refresh_dashboard()
        transactions_screen.show_saved_status(status_message)
        transactions_screen.refresh_expenses()
        self.manager.current = "transactions"

    def cancel(self) -> None:
        self.manager.current = "transactions"

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
    title = "SpendSutra"

    def build(self) -> ExpenseRoot | Label:
        try:
            Window.softinput_mode = "below_target"
            Builder.load_string(KV)
            repository = self._create_repository()
            root = ExpenseRoot(repository=repository)
            root.add_widget(ExpenseListScreen(repository=repository))
            root.add_widget(TransactionsScreen(repository=repository))
            root.add_widget(NotificationsScreen(repository=repository))
            root.add_widget(ExpenseEditScreen(repository=repository))
            root.add_widget(VisualizationScreen(repository=repository))
            root.current = "home"
            return root
        except Exception:
            error_text = traceback.format_exc()
            crash_path = self._write_crash_log(error_text)
            message = (
                "Startup failed.\n\n"
                f"Crash log: {crash_path}\n\n"
                f"{error_text}"
            )
            label = Label(text=message, halign="left", valign="top")
            label.bind(size=lambda instance, _value: setattr(instance, "text_size", instance.size))
            return label

    def _create_repository(self) -> ExpenseRepository:
        candidates = [
            Path(self.user_data_dir) / "expenses.db",
            Path.cwd() / "data" / "expenses.db",
            Path(tempfile.gettempdir()) / "expense_tracker" / "expenses.db",
        ]

        last_error: Exception | None = None
        for db_path in candidates:
            try:
                db_path.parent.mkdir(parents=True, exist_ok=True)
                return ExpenseRepository(db_path)
            except Exception as exc:
                last_error = exc
                continue

        if last_error is not None:
            raise last_error
        raise RuntimeError("Unable to initialize database.")

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
