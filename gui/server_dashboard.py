import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from collections import deque
from datetime import datetime
import queue
import math
import sqlite3
import csv
from tkinter import filedialog
from pathlib import Path

from server.proxy_server import ProxyServerController
from database.request_store import get_recent_requests, initialize_database

# Advanced Proxy System - Proxify-inspired dashboard
# Install: pip install customtkinter matplotlib

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

BG = "#080F1C"
PANEL = "#101A2B"
PANEL_2 = "#0C1524"
BORDER = "#223149"
TEXT = "#E7EEF8"
MUTED = "#8494AA"
BLUE = "#3988FF"
CYAN = "#20C8D8"
GREEN = "#29D391"
PURPLE = "#9A79FF"
ORANGE = "#F6B94A"
RED = "#F36B78"


class ProxyDashboard:
    def __init__(self, root):
        self.root = root
        self.root.title("Proxify | Advanced Proxy System")
        self.root.geometry("1280x820")
        self.root.minsize(1050, 680)
        self.root.configure(fg_color=BG)

        self.events = queue.Queue()
        self.server_running = False

        # These values are placeholders until connected to the real server backend.
        self.metrics = {
            "clients": 0,
            "requests": 0,
            "latency": 0,
            "success": 0,
            "bytes_in": 0,
            "bytes_out": 0,
            "threads": 0,
            "cache_hits": 0,
        }

        self.traffic_in = deque([0.0] * 30, maxlen=30)
        self.traffic_out = deque([0.0] * 30, maxlen=30)
        self.session_rows = {}
        self.request_rows = []
        self._last_traffic_sample = datetime.now()
        self._last_bytes_in = 0
        self._last_bytes_out = 0
        self.max_workers = 20
        self._performance_bars = {}
        self._max_events_per_cycle = 75
        self._max_log_lines = 250
        self._max_history_rows = 100

        initialize_database()
        self._build_shell()
        self._build_dashboard()
        self._load_request_history()
        self._navigate("Dashboard")

        # Real TCP server controller; callbacks enqueue UI updates safely.
        self.server_controller = ProxyServerController(
            on_log=self.log,
            on_status=self.set_server_status,
            on_metrics=self.update_metrics,
            on_session_add=self.add_session,
            on_session_remove=self.remove_session,
            on_request=self.add_request,
            max_workers=20,
        )

        self._refresh_clock()
        self.root.after(100, self._process_events)
        self.root.after(1000, self._sample_traffic)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---------- Shell / navigation ----------

    def _build_shell(self):
        # Sidebar inspired by the supplied NexusHost reference.
        self.sidebar = ctk.CTkFrame(
            self.root, width=158, corner_radius=0, fg_color="#090D16"
        )
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        self.brand = ctk.CTkLabel(
            self.sidebar, text="◈  PROXIFY", text_color=CYAN,
            font=("Arial", 17, "bold")
        )
        self.brand.pack(anchor="w", padx=17, pady=(22, 5))
        ctk.CTkLabel(
            self.sidebar, text="ADVANCED PROXY SYSTEM", text_color=MUTED,
            font=("Arial", 8, "bold")
        ).pack(anchor="w", padx=19, pady=(0, 22))

        groups = [
            ("OVERVIEW", [("▦", "Dashboard")]),
            ("PROXY", [("◎", "Proxies"), ("⌁", "Analytics"), ("▤", "Sessions")]),
            ("SYSTEM", [("⚙", "Settings"), ("◷", "Billing")]),
        ]
        self.nav_buttons = {}
        for group_name, items in groups:
            ctk.CTkLabel(
                self.sidebar, text=group_name, text_color="#65758D",
                font=("Arial", 8, "bold")
            ).pack(anchor="w", padx=18, pady=(8, 5))
            for glyph, name in items:
                b = ctk.CTkButton(
                    self.sidebar, text=f"{glyph}   {name}", width=136, height=34,
                    corner_radius=7, anchor="w",
                    fg_color="#17243A" if name == "Dashboard" else "transparent",
                    hover_color="#1A2B45", text_color=TEXT,
                    font=("Arial", 10), command=lambda n=name: self._navigate(n)
                )
                b.pack(padx=10, pady=2)
                self.nav_buttons[name] = b

        self.main = ctk.CTkFrame(self.root, fg_color=BG, corner_radius=0)
        self.main.pack(side="left", fill="both", expand=True)

        self.topbar = ctk.CTkFrame(
            self.main, height=54, fg_color="#0B101B", corner_radius=0
        )
        self.topbar.pack(fill="x")
        self.topbar.pack_propagate(False)

        self.top_links = {}
        ctk.CTkLabel(
            self.topbar, text="Proxy Server Monitoring", text_color=TEXT,
            font=("Arial", 12, "bold")
        ).pack(side="left", padx=20)
        self.search = ctk.CTkEntry(
            self.topbar, width=190, height=30,
            placeholder_text="⌕  Search services...",
            fg_color="#111D2F", border_color=BORDER, text_color=TEXT
        )
        self.search.pack(side="right", padx=(8, 18), pady=10)
        self.clock_label = ctk.CTkLabel(
            self.topbar, text="", text_color=MUTED, font=("Arial", 9)
        )
        self.clock_label.pack(side="right", padx=8)
        self.profile_label = ctk.CTkLabel(
            self.topbar, text="●  ADMIN", text_color=TEXT,
            font=("Arial", 9, "bold")
        )
        self.profile_label.pack(side="right", padx=12)

        self.page = ctk.CTkScrollableFrame(
            self.main, fg_color=BG, corner_radius=0,
            scrollbar_button_color="#263852"
        )
        self.page.pack(fill="both", expand=True, padx=14, pady=(20, 16))

    def _navigate(self, name):
        for key, button in self.nav_buttons.items():
            button.configure(fg_color=BLUE if key == name else "transparent")
        for key, button in self.top_links.items():
            button.configure(text_color=BLUE if key == name else MUTED)

        if name == "Dashboard":
            return
        if name == "Analytics":
            self._open_analytics_window()
        elif name == "Proxies":
            self._open_proxies_window()
        elif name == "Sessions":
            self._open_sessions_window()
        elif name == "Settings":
            self._open_settings_window()
        elif name == "Billing":
            self._open_usage_window()

    def _section_window(self, key, title, geometry="950x650"):
        windows = getattr(self, "_section_windows", {})
        self._section_windows = windows
        existing = windows.get(key)
        if existing is not None:
            try:
                if existing.winfo_exists():
                    existing.lift()
                    return None
            except Exception:
                pass

        win = ctk.CTkToplevel(self.root)
        windows[key] = win
        win.title(f"Proxify | {title}")
        win.geometry(geometry)
        win.minsize(760, 520)
        win.configure(fg_color=BG)
        win.transient(self.root)
        header = ctk.CTkFrame(win, fg_color="transparent")
        header.pack(fill="x", padx=22, pady=(18, 10))
        ctk.CTkLabel(
            header, text=title, text_color=TEXT,
            font=("Arial", 23, "bold")
        ).pack(anchor="w")
        return win

    def _open_proxies_window(self):
        win = self._section_window("proxies", "Proxy Management", "900x620")
        if win is None:
            return
        card = ctk.CTkFrame(win, fg_color=PANEL, border_color=BORDER, border_width=1)
        card.pack(fill="x", padx=22, pady=10)
        self.proxy_page_status = ctk.CTkLabel(
            card, text="● ONLINE" if self.server_running else "● OFFLINE",
            text_color=GREEN if self.server_running else RED,
            font=("Arial", 18, "bold")
        )
        self.proxy_page_status.pack(anchor="w", padx=18, pady=(18, 6))
        ctk.CTkLabel(
            card, text="TCP Proxy Endpoint: 127.0.0.1:9000",
            text_color=TEXT, font=("Arial", 14)
        ).pack(anchor="w", padx=18, pady=5)
        ctk.CTkLabel(
            card, text="Protocol: TCP client connection with HTTP/HTTPS webpage fetching",
            text_color=MUTED, font=("Arial", 11)
        ).pack(anchor="w", padx=18, pady=(0, 16))

        buttons = ctk.CTkFrame(win, fg_color="transparent")
        buttons.pack(fill="x", padx=22, pady=8)
        ctk.CTkButton(
            buttons, text="Start Proxy Server", fg_color=GREEN,
            text_color="#06140F", command=self._start_clicked
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            buttons, text="Stop Proxy Server", fg_color="#572A38",
            command=self._stop_clicked
        ).pack(side="left", padx=8)
        ctk.CTkButton(
            buttons, text="Refresh Status", fg_color="#26364D",
            command=self._refresh_proxy_page
        ).pack(side="left", padx=8)

        info = ctk.CTkFrame(win, fg_color=PANEL, border_color=BORDER, border_width=1)
        info.pack(fill="both", expand=True, padx=22, pady=10)
        ctk.CTkLabel(info, text="Proxy Configuration", text_color=TEXT,
                     font=("Arial", 14, "bold")).pack(anchor="w", padx=16, pady=14)
        for label, value in [
            ("Listening address", "127.0.0.1"),
            ("Listening port", "9000"),
            ("Worker pool capacity", str(self.max_workers)),
            ("Allowed destination schemes", "HTTP / HTTPS"),
            ("Maximum HTML response", "5 MB"),
            ("Connection timeout", "12 seconds for webpage fetch"),
        ]:
            row = ctk.CTkFrame(info, fg_color="transparent")
            row.pack(fill="x", padx=16, pady=5)
            ctk.CTkLabel(row, text=label, text_color=MUTED).pack(side="left")
            ctk.CTkLabel(row, text=value, text_color=TEXT).pack(side="right")

    def _refresh_proxy_page(self):
        label = getattr(self, "proxy_page_status", None)
        if label is not None and label.winfo_exists():
            label.configure(
                text="● ONLINE" if self.server_running else "● OFFLINE",
                text_color=GREEN if self.server_running else RED
            )

    def _open_sessions_window(self):
        win = self._section_window("sessions", "Client Sessions", "1000x650")
        if win is None:
            return
        summary = ctk.CTkFrame(win, fg_color=PANEL, border_color=BORDER, border_width=1)
        summary.pack(fill="x", padx=22, pady=8)
        self.sessions_page_count = ctk.CTkLabel(
            summary, text=f"Active connections: {len(self.session_rows)}",
            text_color=TEXT, font=("Arial", 15, "bold")
        )
        self.sessions_page_count.pack(anchor="w", padx=15, pady=12)

        frame = ctk.CTkFrame(win, fg_color=PANEL, border_color=BORDER, border_width=1)
        frame.pack(fill="both", expand=True, padx=22, pady=10)
        cols = ("ip", "country", "protocol", "city", "bandwidth", "status")
        self.sessions_page_table = ttk.Treeview(
            frame, columns=cols, show="headings", style="Proxy.Treeview"
        )
        labels = ("IP Address", "Country", "Protocol", "City", "Bandwidth", "Status")
        widths = (150, 120, 120, 150, 120, 120)
        for col, label, width in zip(cols, labels, widths):
            self.sessions_page_table.heading(col, text=label)
            self.sessions_page_table.column(col, width=width, anchor="w")
        self.sessions_page_table.pack(fill="both", expand=True, padx=10, pady=10)
        ctk.CTkButton(
            win, text="Refresh Sessions", command=self._refresh_sessions_page
        ).pack(anchor="e", padx=22, pady=(0, 15))
        self._refresh_sessions_page()

    def _refresh_sessions_page(self):
        table = getattr(self, "sessions_page_table", None)
        if table is None or not table.winfo_exists():
            return
        for item in table.get_children():
            table.delete(item)
        if hasattr(self, "sessions") and self.sessions.winfo_exists():
            for values in self.sessions.get_children():
                table.insert("", "end", values=self.sessions.item(values, "values"))
        if hasattr(self, "sessions_page_count"):
            self.sessions_page_count.configure(
                text=f"Active connections: {len(table.get_children())}"
            )

    def _open_settings_window(self):
        win = self._section_window("settings", "System Settings", "850x620")
        if win is None:
            return
        panel = ctk.CTkFrame(win, fg_color=PANEL, border_color=BORDER, border_width=1)
        panel.pack(fill="x", padx=22, pady=10)
        settings = [
            ("Server host", "127.0.0.1"),
            ("Server port", "9000"),
            ("Maximum worker threads", str(self.max_workers)),
            ("Maximum request frame", "64 KB"),
            ("Maximum response frame", "8 MB"),
            ("Maximum downloaded HTML", "5 MB"),
            ("Fetch timeout", "12 seconds"),
            ("Database", "SQLite — database/proxy_history.db"),
        ]
        for label, value in settings:
            row = ctk.CTkFrame(panel, fg_color="transparent")
            row.pack(fill="x", padx=16, pady=9)
            ctk.CTkLabel(row, text=label, text_color=MUTED).pack(side="left")
            ctk.CTkLabel(row, text=value, text_color=TEXT).pack(side="right")
        note = ctk.CTkLabel(
            win,
            text="These values describe the current implementation. Edit the server configuration in server/proxy_server.py to change them.",
            text_color=MUTED, wraplength=780, justify="left"
        )
        note.pack(anchor="w", padx=25, pady=10)

    def _open_usage_window(self):
        win = self._section_window("billing", "Usage & Data Transfer", "850x560")
        if win is None:
            return
        rows = self._analytics_rows()
        total = len(rows)
        succeeded = sum(int(row["success"]) for row in rows)
        failed = total - succeeded
        bytes_total = sum(int(row["bytes_downloaded"]) for row in rows)
        avg = sum(float(row["latency_ms"]) for row in rows) / total if total else 0

        panel = ctk.CTkFrame(win, fg_color=PANEL, border_color=BORDER, border_width=1)
        panel.pack(fill="x", padx=22, pady=10)
        for label, value in [
            ("Recorded requests", str(total)),
            ("Successful requests", str(succeeded)),
            ("Failed requests", str(failed)),
            ("Total downloaded data", self._format_bytes(bytes_total)),
            ("Average response time", f"{avg:.0f} ms"),
        ]:
            row = ctk.CTkFrame(panel, fg_color="transparent")
            row.pack(fill="x", padx=16, pady=10)
            ctk.CTkLabel(row, text=label, text_color=MUTED).pack(side="left")
            ctk.CTkLabel(row, text=value, text_color=TEXT,
                         font=("Arial", 12, "bold")).pack(side="right")
        ctk.CTkLabel(
            win, text="This project does not process payments. This page reports recorded usage only.",
            text_color=MUTED, wraplength=760
        ).pack(anchor="w", padx=24, pady=10)

    def _analytics_rows(self, start_date="", end_date=""):
        db_path = Path(__file__).resolve().parents[1] / "database" / "proxy_history.db"
        if not db_path.exists():
            return []
        query = """
            SELECT id, created_at, client_ip, url, status, latency_ms,
                   success, bytes_downloaded
            FROM request_history
            WHERE 1=1
        """
        params = []
        if start_date.strip():
            query += " AND date(created_at) >= date(?)"
            params.append(start_date.strip())
        if end_date.strip():
            query += " AND date(created_at) <= date(?)"
            params.append(end_date.strip())
        query += " ORDER BY id DESC"
        with sqlite3.connect(db_path, timeout=10) as conn:
            conn.row_factory = sqlite3.Row
            return [dict(row) for row in conn.execute(query, params).fetchall()]

    def _open_analytics_window(self):
        if getattr(self, "_analytics_window", None) is not None:
            try:
                if self._analytics_window.winfo_exists():
                    self._analytics_window.lift()
                    self._refresh_analytics()
                    return
            except Exception:
                pass

        win = ctk.CTkToplevel(self.root)
        self._analytics_window = win
        win.title("Proxify | Analytics")
        win.geometry("1180x760")
        win.minsize(900, 600)
        win.configure(fg_color=BG)

        header = ctk.CTkFrame(win, fg_color="transparent")
        header.pack(fill="x", padx=22, pady=(18, 8))
        ctk.CTkLabel(
            header, text="Request Analytics",
            text_color=TEXT, font=("Arial", 23, "bold")
        ).pack(anchor="w")
        ctk.CTkLabel(
            header, text="Live summary and historical records from your SQLite database",
            text_color=MUTED, font=("Arial", 11)
        ).pack(anchor="w", pady=(3, 0))

        filters = ctk.CTkFrame(win, fg_color=PANEL, corner_color=BORDER)
        filters.pack(fill="x", padx=22, pady=8)
        self.analytics_start = ctk.CTkEntry(
            filters, width=150, placeholder_text="Start YYYY-MM-DD"
        )
        self.analytics_start.pack(side="left", padx=10, pady=10)
        self.analytics_end = ctk.CTkEntry(
            filters, width=150, placeholder_text="End YYYY-MM-DD"
        )
        self.analytics_end.pack(side="left", padx=5, pady=10)
        ctk.CTkButton(
            filters, text="Apply Filter", width=110,
            command=self._refresh_analytics
        ).pack(side="left", padx=8, pady=10)
        ctk.CTkButton(
            filters, text="Clear", width=75, fg_color="#26364D",
            command=self._clear_analytics_filter
        ).pack(side="left", padx=4, pady=10)
        ctk.CTkButton(
            filters, text="Export CSV", width=110,
            fg_color=GREEN, text_color="#07131F",
            command=self._export_analytics_csv
        ).pack(side="right", padx=10, pady=10)

        cards = ctk.CTkFrame(win, fg_color="transparent")
        cards.pack(fill="x", padx=18, pady=5)
        self.analytics_kpis = {}
        for key, label in [
            ("total", "Total Requests"), ("success", "Successful"),
            ("failed", "Failed"), ("avg", "Avg. Latency"),
            ("bytes", "Downloaded")
        ]:
            card = ctk.CTkFrame(cards, fg_color=PANEL, border_color=BORDER, border_width=1)
            card.pack(side="left", fill="both", expand=True, padx=4)
            ctk.CTkLabel(card, text=label, text_color=MUTED, font=("Arial", 10)).pack(
                anchor="w", padx=12, pady=(10, 2)
            )
            value = ctk.CTkLabel(card, text="0", text_color=TEXT, font=("Arial", 20, "bold"))
            value.pack(anchor="w", padx=12, pady=(0, 10))
            self.analytics_kpis[key] = value

        table_panel = ctk.CTkFrame(win, fg_color=PANEL, border_color=BORDER, border_width=1)
        table_panel.pack(fill="both", expand=True, padx=22, pady=(8, 18))
        ctk.CTkLabel(
            table_panel, text="Request History", text_color=TEXT,
            font=("Arial", 14, "bold")
        ).pack(anchor="w", padx=12, pady=10)

        table_frame = ctk.CTkFrame(table_panel, fg_color="transparent")
        table_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        columns = ("time", "client", "url", "status", "latency", "bytes")
        self.analytics_table = ttk.Treeview(
            table_frame, columns=columns, show="headings", style="Proxy.Treeview"
        )
        headings = {
            "time": "Date / Time", "client": "Client IP", "url": "Requested URL",
            "status": "Status", "latency": "Latency", "bytes": "Downloaded"
        }
        widths = {"time": 145, "client": 105, "url": 440, "status": 90, "latency": 90, "bytes": 100}
        for col in columns:
            self.analytics_table.heading(col, text=headings[col])
            self.analytics_table.column(col, width=widths[col], anchor="w")
        yscroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.analytics_table.yview)
        self.analytics_table.configure(yscrollcommand=yscroll.set)
        self.analytics_table.pack(side="left", fill="both", expand=True)
        yscroll.pack(side="right", fill="y")

        self._refresh_analytics()

    def _clear_analytics_filter(self):
        self.analytics_start.delete(0, "end")
        self.analytics_end.delete(0, "end")
        self._refresh_analytics()

    def _refresh_analytics(self):
        if not hasattr(self, "analytics_table"):
            return
        start = self.analytics_start.get().strip()
        end = self.analytics_end.get().strip()
        try:
            rows = self._analytics_rows(start, end)
        except Exception as exc:
            messagebox.showerror("Analytics error", str(exc))
            return

        for item in self.analytics_table.get_children():
            self.analytics_table.delete(item)

        total = len(rows)
        successes = sum(int(row["success"]) for row in rows)
        failed = total - successes
        avg_latency = (sum(float(row["latency_ms"]) for row in rows) / total) if total else 0
        total_bytes = sum(int(row["bytes_downloaded"]) for row in rows)

        self.analytics_kpis["total"].configure(text=str(total))
        self.analytics_kpis["success"].configure(text=str(successes))
        self.analytics_kpis["failed"].configure(text=str(failed))
        self.analytics_kpis["avg"].configure(text=f"{avg_latency:.0f} ms")
        self.analytics_kpis["bytes"].configure(text=self._format_bytes(total_bytes))

        for row in rows[:1000]:
            self.analytics_table.insert("", "end", values=(
                row["created_at"], row["client_ip"], row["url"], row["status"],
                f"{float(row['latency_ms']):.0f} ms",
                self._format_bytes(int(row["bytes_downloaded"]))
            ))
        self._analytics_export_rows = rows

    def _export_analytics_csv(self):
        rows = getattr(self, "_analytics_export_rows", [])
        if not rows:
            messagebox.showinfo("Export CSV", "There are no records to export.")
            return
        path = filedialog.asksaveasfilename(
            parent=self._analytics_window,
            title="Save analytics report",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")]
        )
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8-sig") as file:
            writer = csv.DictWriter(file, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        messagebox.showinfo("Export complete", f"Exported {len(rows)} records to:\n{path}")

    def _refresh_clock(self):
        self.clock_label.configure(text=datetime.now().strftime("%d %b %Y  |  %H:%M:%S"))
        self.root.after(1000, self._refresh_clock)

    # ---------- Dashboard layout ----------

    def _build_dashboard(self):
        # Page heading and live server controls.
        hero = ctk.CTkFrame(self.page, fg_color="transparent")
        hero.pack(fill="x", pady=(2, 12))
        left = ctk.CTkFrame(hero, fg_color="transparent")
        left.pack(side="left")
        ctk.CTkLabel(
            left, text="Dashboard", text_color=TEXT,
            font=("Arial", 24, "bold")
        ).pack(anchor="w")
        ctk.CTkLabel(
            left, text="Live overview of your multi-threaded proxy server",
            text_color=MUTED, font=("Arial", 10)
        ).pack(anchor="w", pady=(3, 0))

        controls = ctk.CTkFrame(hero, fg_color="transparent")
        controls.pack(side="right", pady=5)
        self.server_badge = ctk.CTkLabel(
            controls, text="● OFFLINE", text_color=RED,
            font=("Arial", 10, "bold")
        )
        self.server_badge.pack(side="left", padx=10)
        self.start_btn = ctk.CTkButton(
            controls, text="▶ Start Server", width=112, height=32,
            fg_color=GREEN, hover_color="#1DAE78", text_color="#06140F",
            font=("Arial", 10, "bold"), command=self._start_clicked
        )
        self.start_btn.pack(side="left", padx=4)
        self.stop_btn = ctk.CTkButton(
            controls, text="■ Stop", width=72, height=32,
            fg_color="#572A38", hover_color="#79384A", text_color="#FFE7EB",
            state="disabled", command=self._stop_clicked
        )
        self.stop_btn.pack(side="left", padx=4)

        # Real project KPIs; no fabricated CPU, RAM, or geographic measurements.
        self.kpi_values = {}
        kpi_specs = [
            ("ACTIVE CLIENTS", "clients", "0", CYAN, "Current connections"),
            ("TOTAL REQUESTS", "requests", "0", PURPLE, "Recorded requests"),
            ("AVG. LATENCY", "latency", "—", ORANGE, "Response time"),
            ("SUCCESS RATE", "success", "—", GREEN, "Successful fetches"),
            ("DATA TRANSFERRED", "data", "0 B", BLUE, "Inbound + outbound"),
        ]
        kpi_row = ctk.CTkFrame(self.page, fg_color="transparent")
        kpi_row.pack(fill="x", pady=(0, 12))
        for i, (title, key, value, accent, subtitle) in enumerate(kpi_specs):
            card = ctk.CTkFrame(
                kpi_row, fg_color="#101722", corner_radius=10,
                border_width=1, border_color=accent
            )
            card.grid(row=0, column=i, padx=2, sticky="nsew")
            kpi_row.grid_columnconfigure(i, weight=1, uniform="kpis")
            ctk.CTkLabel(
                card, text=title, text_color=MUTED,
                font=("Arial", 8, "bold")
            ).pack(anchor="w", padx=11, pady=(12, 2))
            value_label = ctk.CTkLabel(
                card, text=value, text_color=TEXT,
                font=("Arial", 21, "bold")
            )
            value_label.pack(anchor="w", padx=11)
            self.kpi_values[key] = value_label
            ctk.CTkLabel(
                card, text=subtitle, text_color=accent,
                font=("Arial", 8)
            ).pack(anchor="w", padx=11, pady=(2, 11))

        # Main monitoring row: live traffic and request outcome distribution.
        middle = ctk.CTkFrame(self.page, fg_color="transparent")
        middle.pack(fill="x", pady=4)
        middle.grid_columnconfigure(0, weight=7, uniform="mainrow")
        middle.grid_columnconfigure(1, weight=4, uniform="mainrow")
        traffic_panel = self._panel(middle)
        traffic_panel.grid(row=0, column=0, padx=(0, 6), sticky="nsew")
        self._panel_heading(traffic_panel, "Proxy Traffic Overview", "LIVE IN / OUT")
        self._build_traffic_chart(traffic_panel)

# Initialize inbound and outbound traffic breakdown.
        self._build_location_bars(traffic_panel)
        distribution_panel = self._panel(middle)
        distribution_panel.grid(row=0, column=1, padx=(6, 0), sticky="nsew")
        self._panel_heading(distribution_panel, "Request Distribution", "SQLITE RECORDS")
        self.distribution_canvas = tk.Canvas(
            distribution_panel, height=190, bg=PANEL,
            highlightthickness=0, bd=0
        )
        self.distribution_canvas.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.distribution_canvas.bind(
            "<Configure>", lambda event: self._refresh_distribution()
        )

        # Service cards reflect actual project components and configured capacity.
        ctk.CTkLabel(
            self.page, text="Runtime & Services", text_color=TEXT,
            font=("Arial", 15, "bold")
        ).pack(anchor="w", padx=4, pady=(14, 7))
        services = ctk.CTkFrame(self.page, fg_color="transparent")
        services.pack(fill="x", pady=(0, 8))
        service_specs = [
            ("TCP SOCKET", "127.0.0.1:9000", "Client-server communication", CYAN),
            ("WORKER POOL", f"{self.max_workers} workers", "ThreadPoolExecutor", PURPLE),
            ("WEB FETCHER", "HTTP / HTTPS", "Public HTML pages", GREEN),
            ("SQLITE STORE", "Persistent", "Request history database", ORANGE),
        ]
        self.service_status_labels = {}
        for i, (name, value, detail, accent) in enumerate(service_specs):
            card = ctk.CTkFrame(
                services, fg_color="#101722", corner_radius=10,
                border_width=1, border_color="#29364A"
            )
            card.grid(row=0, column=i, padx=2, sticky="nsew")
            services.grid_columnconfigure(i, weight=1, uniform="services")
            ctk.CTkLabel(
                card, text=f"●  {name}", text_color=accent,
                font=("Arial", 9, "bold")
            ).pack(anchor="w", padx=11, pady=(12, 5))
            val = ctk.CTkLabel(
                card, text=value, text_color=TEXT,
                font=("Arial", 15, "bold")
            )
            val.pack(anchor="w", padx=11)
            self.service_status_labels[name] = val
            ctk.CTkLabel(
                card, text=detail, text_color=MUTED,
                font=("Arial", 8)
            ).pack(anchor="w", padx=11, pady=(3, 12))

        # Existing live sessions and performance panels are retained.
        bottom = ctk.CTkFrame(self.page, fg_color="transparent")
        bottom.pack(fill="both", expand=True, pady=5)
        bottom.grid_columnconfigure(0, weight=5)
        bottom.grid_columnconfigure(1, weight=3)
        sessions_panel = self._panel(bottom)
        sessions_panel.grid(row=0, column=0, padx=(0, 6), sticky="nsew")
        self._panel_heading(sessions_panel, "Active Client Sessions", "● LIVE")
        self._build_sessions_table(sessions_panel)
        performance_panel = self._panel(bottom)
        performance_panel.grid(row=0, column=1, padx=(6, 0), sticky="nsew")
        self._panel_heading(performance_panel, "Performance Metrics", "CURRENT")
        self._build_performance(performance_panel)

        activity = self._panel(self.page)
        activity.pack(fill="x", padx=2, pady=(9, 4))
        self._panel_heading(activity, "System Activity", "EVENT LOG")
        self.log_box = ctk.CTkTextbox(
            activity, height=72, fg_color=PANEL_2, text_color="#A9C7E8",
            font=("Consolas", 10), border_width=0
        )
        self.log_box.pack(fill="x", padx=10, pady=(0, 10))

        history_panel = self._panel(self.page)
        history_panel.pack(fill="both", expand=True, padx=2, pady=(8, 10))
        self._panel_heading(history_panel, "Persistent Request History", "SQLITE DATABASE")
        self._build_request_history_table(history_panel)
        self.log("Dashboard initialized. Request history is stored in SQLite.")
        self._refresh_distribution()

    def _refresh_distribution(self):
        canvas = getattr(self, "distribution_canvas", None)
        if canvas is None or not canvas.winfo_exists():
            return
        canvas.delete("all")
        try:
            rows = self._analytics_rows()
            total = len(rows)
            success = sum(int(row.get("success", 0)) for row in rows)
            failed = total - success
        except Exception:
            total, success, failed = 0, 0, 0
        width = max(canvas.winfo_width(), 250)
        height = max(canvas.winfo_height(), 170)
        cx, cy = width * 0.5, height * 0.46
        radius = min(57, height * 0.34)
        canvas.create_oval(cx-radius, cy-radius, cx+radius, cy+radius,
                           outline="#26364D", width=13)
        if total:
            success_extent = 360 * success / total
            canvas.create_arc(cx-radius, cy-radius, cx+radius, cy+radius,
                              start=90, extent=-success_extent, style="arc",
                              outline=GREEN, width=13)
            if failed:
                canvas.create_arc(cx-radius, cy-radius, cx+radius, cy+radius,
                                  start=90-success_extent,
                                  extent=-(360-success_extent), style="arc",
                                  outline=RED, width=13)
        canvas.create_text(cx, cy-5, text=f"{total:,}", fill=TEXT,
                           font=("Arial", 18, "bold"))
        canvas.create_text(cx, cy+17, text="TOTAL", fill=MUTED,
                           font=("Arial", 8, "bold"))
        canvas.create_oval(18, height-35, 26, height-27, fill=GREEN, outline=GREEN)
        canvas.create_text(33, height-31, anchor="w", text=f"Success  {success}",
                           fill=TEXT, font=("Arial", 9))
        canvas.create_oval(width-145, height-35, width-137, height-27,
                           fill=RED, outline=RED)
        canvas.create_text(width-130, height-31, anchor="w", text=f"Failed  {failed}",
                           fill=TEXT, font=("Arial", 9))

    def _panel(self, parent):
        return ctk.CTkFrame(
            parent, fg_color=PANEL, corner_radius=10,
            border_width=1, border_color=BORDER
        )

    def _panel_heading(self, parent, title, tag):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=12, pady=(10, 7))
        ctk.CTkLabel(
            row, text=title, text_color=TEXT,
            font=("Arial", 12, "bold")
        ).pack(side="left")
        ctk.CTkLabel(
            row, text=tag, text_color=CYAN,
            font=("Arial", 8, "bold")
        ).pack(side="right")

    # ---------- Global traffic map visual ----------

    def _draw_network_map(self):
        c = self.map_canvas
        c.delete("all")
        w = max(c.winfo_width(), 400)
        h = max(c.winfo_height(), 200)

        # Subtle grid
        for x in range(0, w, 30):
            c.create_line(x, 0, x, h, fill="#142238")
        for y in range(0, h, 30):
            c.create_line(0, y, w, y, fill="#142238")

        # Stylized continent silhouettes (decorative map backdrop)
        shapes = [
            [(0.08, .25), (.16, .13), (.26, .16), (.31, .29), (.25, .39), (.22, .55), (.16, .50), (.12, .37)],
            [(.25, .53), (.31, .55), (.33, .69), (.29, .91), (.25, .77)],
            [(.43, .22), (.51, .15), (.58, .20), (.61, .32), (.56, .40), (.49, .37), (.45, .30)],
            [(.48, .42), (.55, .43), (.58, .60), (.54, .83), (.49, .69), (.46, .52)],
            [(.60, .23), (.72, .15), (.87, .22), (.92, .34), (.84, .42), (.75, .37), (.68, .45), (.61, .35)],
        ]
        for poly in shapes:
            coords = []
            for px, py in poly:
                coords.extend([px * w, py * h])
            c.create_polygon(
                coords, fill="#1A2A3D", outline="#263D56",
                width=1, smooth=True
            )

        points = {
            "US": (.19, .34), "EU": (.49, .29),
            "IN": (.67, .43), "SG": (.75, .57),
            "JP": (.85, .38), "BR": (.29, .72)
        }
        routes = [("US", "EU"), ("EU", "IN"), ("IN", "SG"),
                  ("EU", "JP"), ("US", "BR")]
        for a, b in routes:
            x1, y1 = points[a][0] * w, points[a][1] * h
            x2, y2 = points[b][0] * w, points[b][1] * h
            c.create_line(
                x1, y1, x2, y2,
                fill="#2878D7", width=2, smooth=True,
                dash=(4, 3)
            )
        for name, (px, py) in points.items():
            x, y = px * w, py * h
            color = GREEN if name in ("IN", "SG") else BLUE
            c.create_oval(
                x-8, y-8, x+8, y+8,
                outline=color, width=1, fill="#15304B"
            )
            c.create_oval(
                x-3, y-3, x+3, y+3,
                fill=color, outline=color
            )
            c.create_text(
                x, y+15, text=name, fill="#B8C8DA",
                font=("Arial", 8, "bold")
            )
        c.create_text(
            12, h-12, text="Illustrative map — remote client geolocation is not collected",
            anchor="w", fill=MUTED, font=("Arial", 8)
        )

    # ---------- Traffic chart ----------

    def _build_traffic_chart(self, parent):
        self.fig = Figure(figsize=(3.4, 1.55), dpi=100, facecolor=PANEL)
        self.ax = self.fig.add_subplot(111)
        self.ax.set_facecolor(PANEL)
        self.ax.tick_params(colors=MUTED, labelsize=7)
        for sp in self.ax.spines.values():
            sp.set_color(BORDER)
        self.ax.grid(color="#26364D", alpha=.55, linestyle="--", linewidth=.5)
        self.ax.set_ylabel("KB/s", color=MUTED, fontsize=8)
        x = list(range(len(self.traffic_in)))
        self.line_in, = self.ax.plot(x, list(self.traffic_in), color=BLUE, lw=1.8, label="Inbound")
        self.line_out, = self.ax.plot(x, list(self.traffic_out), color=GREEN, lw=1.8, label="Outbound")
        self.ax.legend(
            loc="upper left", frameon=False, fontsize=7,
            labelcolor=TEXT
        )
        self.fig.tight_layout(pad=1.5)
        self.chart = FigureCanvasTkAgg(self.fig, master=parent)
        self.chart.get_tk_widget().pack(fill="both", expand=True, padx=7, pady=(0, 7))

    def _update_chart(self):
        """Update traffic chart with adaptive Y-axis scaling."""

        x = list(range(len(self.traffic_in)))

        incoming = list(self.traffic_in)
        outgoing = list(self.traffic_out)

        self.line_in.set_data(x, incoming)
        self.line_out.set_data(x, outgoing)

        # Automatically scale according to actual traffic.
        peak = max(incoming + outgoing + [0.0])

        if peak > 0:
            upper = peak * 1.25
        else:
            upper = 0.001

        self.ax.set_ylim(0, upper)
        self.ax.set_xlim(0, max(1, len(x) - 1))

        self.chart.draw_idle()

    # ---------- Locations ----------

    def _build_location_bars(self, parent):
        self.traffic_breakdown_labels = {}
        self.traffic_breakdown_bars = {}

        rows = [
            ("Inbound", BLUE),
            ("Outbound", GREEN),
        ]
        for label, color in rows:
            row = ctk.CTkFrame(parent, fg_color="transparent")
            row.pack(fill="x", padx=13, pady=8)

            ctk.CTkLabel(
                row, text=label, width=75, anchor="w",
                text_color=MUTED, font=("Arial", 9)
            ).pack(side="left")

            bar_bg = ctk.CTkFrame(
                row, height=9, fg_color="#25334A", corner_radius=5
            )
            bar_bg.pack(side="left", fill="x", expand=True, padx=6)

            bar = ctk.CTkFrame(
                bar_bg, height=9, width=1,
                fg_color=color, corner_radius=5
            )
            bar.pack(side="left")

            value_label = ctk.CTkLabel(
                row, text="0 B", width=58, text_color=TEXT,
                font=("Arial", 8)
            )
            value_label.pack(side="right")

            self.traffic_breakdown_labels[label] = value_label
            self.traffic_breakdown_bars[label] = (bar_bg, bar)

    # ---------- Sessions table ----------

    def _build_sessions_table(self, parent):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Proxy.Treeview",
            background="#0C1625", foreground=TEXT,
            fieldbackground="#0C1625", rowheight=25,
            borderwidth=0, font=("Arial", 8)
        )
        style.configure(
            "Proxy.Treeview.Heading",
            background="#1A2A40", foreground="#C9D7E8",
            relief="flat", font=("Arial", 8, "bold")
        )
        style.map("Proxy.Treeview", background=[("selected", "#214B7A")])

        columns = ("ip", "country", "protocol", "city", "bandwidth", "status")
        self.sessions = ttk.Treeview(
            parent, columns=columns, show="headings",
            height=7, style="Proxy.Treeview"
        )
        headings = {
            "ip": "IP Address", "country": "Country",
            "protocol": "Protocol", "city": "City",
            "bandwidth": "BW", "status": "Status"
        }
        widths = {"ip": 105, "country": 65, "protocol": 65,
                  "city": 75, "bandwidth": 65, "status": 60}
        for col in columns:
            self.sessions.heading(col, text=headings[col])
            self.sessions.column(col, width=widths[col], anchor="w")
        self.sessions.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    # ---------- Performance bars ----------

    def _build_performance(self, parent):
        self.performance_labels = {}
        metrics = [
            ("Avg. Response Time", BLUE, "— ms"),
            ("Successful Requests", GREEN, "— %"),
            ("Cache Efficiency", PURPLE, "N/A"),
            ("Worker Utilization", CYAN, "0.0%"),
        ]

        for title, color, value in metrics:
            row = ctk.CTkFrame(parent, fg_color="transparent")
            row.pack(fill="x", padx=13, pady=7)

            top = ctk.CTkFrame(row, fg_color="transparent")
            top.pack(fill="x")

            ctk.CTkLabel(
                top, text=title, text_color=MUTED,
                font=("Arial", 9)
            ).pack(side="left")

            val = ctk.CTkLabel(
                top, text=value, text_color=TEXT,
                font=("Arial", 9, "bold")
            )
            val.pack(side="right")
            self.performance_labels[title] = val

            bar_bg = ctk.CTkFrame(
                row, height=7, fg_color="#26364D", corner_radius=5
            )
            bar_bg.pack(fill="x", pady=(4, 0))

            bar = ctk.CTkFrame(
                bar_bg, height=7, width=1,
                fg_color=color, corner_radius=5
            )
            bar.pack(side="left")
            self._performance_bars[title] = (bar_bg, bar)

    def _set_bar_fraction(self, bar_key, fraction):
        """Resize a dashboard bar using a clamped 0..1 fraction."""
        if bar_key not in self._performance_bars:
            return
        background, bar = self._performance_bars[bar_key]
        width = max(1, background.winfo_width())
        target = max(1, int(width * max(0.0, min(1.0, fraction))))
        bar.configure(width=target)

    def _update_traffic_breakdown(self):
        incoming = self.metrics.get("bytes_in", 0)
        outgoing = self.metrics.get("bytes_out", 0)
        maximum = max(incoming, outgoing, 1)

        for label, amount in (("Inbound", incoming), ("Outbound", outgoing)):
            self.traffic_breakdown_labels[label].configure(
                text=self._format_bytes(amount)
            )
            background, bar = self.traffic_breakdown_bars[label]
            available = max(1, background.winfo_width() - 2)
            fraction = (amount / maximum) if maximum else 0.0
            # CustomTkinter frames must not be configured with width=0 on Windows.
            # A 2 px minimum avoids Tk_GetPixmap/CreateDIBSection errors.
            target_width = max(2, int(available * fraction)) if amount > 0 else 2
            bar.configure(width=target_width)

    def _sample_traffic(self):
        """Convert cumulative server byte counters into one-second KB/s samples."""
        now = datetime.now()
        elapsed = max((now - self._last_traffic_sample).total_seconds(), 0.001)

        current_in = self.metrics.get("bytes_in", 0)
        current_out = self.metrics.get("bytes_out", 0)

        delta_in = max(0, current_in - self._last_bytes_in)
        delta_out = max(0, current_out - self._last_bytes_out)

        inbound_kbps = (delta_in / 1024.0) / elapsed
        outbound_kbps = (delta_out / 1024.0) / elapsed

        self._last_bytes_in = current_in
        self._last_bytes_out = current_out
        self._last_traffic_sample = now

        self.traffic_in.append(inbound_kbps)
        self.traffic_out.append(outbound_kbps)
        self._update_chart()
        self._update_traffic_breakdown()

        self.root.after(1000, self._sample_traffic)

    # ---------- Persistent request history ----------

    def _build_request_history_table(self, parent):
        columns = ("time", "client", "url", "status", "latency", "size")
        self.history_table = ttk.Treeview(
            parent, columns=columns, show="headings", height=8,
            style="Proxy.Treeview"
        )
        headings = {
            "time": "Time", "client": "Client IP", "url": "Requested URL",
            "status": "Status", "latency": "Latency", "size": "Downloaded"
        }
        widths = {
            "time": 135, "client": 100, "url": 390,
            "status": 75, "latency": 85, "size": 90
        }
        for column in columns:
            self.history_table.heading(column, text=headings[column])
            self.history_table.column(column, width=widths[column], anchor="w")
        self.history_table.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    def _insert_history_row(self, item):
        values = (
            item.get("created_at", ""),
            item.get("client_ip", ""),
            item.get("url", ""),
            item.get("status", ""),
            f"{float(item.get('latency_ms', 0)):.0f} ms",
            self._format_bytes(int(item.get("bytes_downloaded", 0))),
        )
        self.history_table.insert("", 0, values=values)
        children = self.history_table.get_children()
        for old_item in children[self._max_history_rows:]:
            self.history_table.delete(old_item)

    def _load_request_history(self):
        try:
            for item in reversed(get_recent_requests(100)):
                self._insert_history_row(item)
        except Exception as exc:
            self.log(f"Could not load saved request history: {exc}")

    # ---------- Backend integration API ----------

    def set_server_status(self, running, host="127.0.0.1", port=9000):
        """Call this from the server controller after bind/listen succeeds."""
        self.events.put(("server", running, host, port))

    def update_metrics(self, clients=None, requests=None, latency_ms=None,
                       success_rate=None, bytes_in=None, bytes_out=None,
                       threads=None, cache_hits=None):
        """Thread-safe entry point for real backend metrics."""
        self.events.put(("metrics", {
            "clients": clients, "requests": requests,
            "latency": latency_ms, "success": success_rate,
            "bytes_in": bytes_in, "bytes_out": bytes_out,
            "threads": threads, "cache_hits": cache_hits
        }))

    def add_session(self, session_id, ip, country="—", protocol="HTTP",
                    city="—", bandwidth="—", status="Active"):
        self.events.put(("session", session_id, ip, country, protocol, city, bandwidth, status))

    def remove_session(self, session_id):
        self.events.put(("remove_session", session_id))

    def add_request(self, url, status_code, response_ms):
        self.events.put(("request", url, status_code, response_ms))

    def add_traffic_sample(self, inbound_kbps, outbound_kbps):
        self.events.put(("traffic", inbound_kbps, outbound_kbps))

    def log(self, message):
        self.events.put(("log", str(message)))

    def _process_events(self):
        """Process a bounded batch so bursts cannot monopolize the Tk UI thread."""
        processed = 0
        while processed < self._max_events_per_cycle:
            try:
                event = self.events.get_nowait()
            except queue.Empty:
                break

            processed += 1
            kind = event[0]
            try:
                if kind == "server":
                    _, running, host, port = event
                    self.server_running = running
                    self.server_badge.configure(
                        text="● ONLINE" if running else "● OFFLINE",
                        text_color=GREEN if running else RED
                    )
                    self.start_btn.configure(state="disabled" if running else "normal")
                    self.stop_btn.configure(state="normal" if running else "disabled")
                    socket_label = self.service_status_labels.get("TCP SOCKET")
                    if socket_label is not None:
                        socket_label.configure(text="LISTENING" if running else "STOPPED")
                    self.log(f"Server {'started' if running else 'stopped'} at {host}:{port}")

                elif kind == "metrics":
                    data = event[1]
                    if data["clients"] is not None:
                        self.kpi_values["clients"].configure(text=str(data["clients"]))
                    if data["requests"] is not None:
                        self.metrics["requests"] = data["requests"]
                        self.kpi_values["requests"].configure(text=str(data["requests"]))
                    if data["latency"] is not None:
                        self.kpi_values["latency"].configure(text=f"{data['latency']:.0f} ms")
                        self.performance_labels["Avg. Response Time"].configure(
                            text=f"{data['latency']:.0f} ms"
                        )
                        self._set_bar_fraction(
                            "Avg. Response Time", min(1.0, data["latency"] / 2000.0)
                        )
                    if data["success"] is not None:
                        self.kpi_values["success"].configure(text=f"{data['success']:.1f}%")
                        self.performance_labels["Successful Requests"].configure(
                            text=f"{data['success']:.1f}%"
                        )
                        self._set_bar_fraction(
                            "Successful Requests", data["success"] / 100.0
                        )
                    if data["bytes_in"] is not None:
                        self.metrics["bytes_in"] = data["bytes_in"]
                    if data["bytes_out"] is not None:
                        self.metrics["bytes_out"] = data["bytes_out"]
                    total_bytes = self.metrics["bytes_in"] + self.metrics["bytes_out"]
                    self.kpi_values["data"].configure(text=self._format_bytes(total_bytes))

                    if data["threads"] is not None:
                        self.metrics["threads"] = data["threads"]
                        utilization = min(
                            100.0, data["threads"] / self.max_workers * 100.0
                        )
                        self.performance_labels["Worker Utilization"].configure(
                            text=f"{utilization:.1f}%"
                        )
                        self._set_bar_fraction(
                            "Worker Utilization", utilization / 100.0
                        )
                    if data["cache_hits"] is not None:
                        self.metrics["cache_hits"] = data["cache_hits"]
                    self._update_traffic_breakdown()

                elif kind == "session":
                    _, sid, ip, country, protocol, city, bandwidth, status = event
                    values = (ip, country, protocol, city, bandwidth, status)
                    if sid in self.session_rows:
                        self.sessions.item(self.session_rows[sid], values=values)
                    else:
                        self.session_rows[sid] = self.sessions.insert(
                            "", "end", values=values
                        )

                elif kind == "remove_session":
                    sid = event[1]
                    iid = self.session_rows.pop(sid, None)
                    if iid:
                        self.sessions.delete(iid)

                elif kind == "request":
                    _, url, status_code, response_ms = event
                    try:
                        saved = get_recent_requests(1)
                        history_item = saved[0] if saved else {
                            "url": url, "status": status_code,
                            "latency_ms": response_ms,
                            "created_at": datetime.now().isoformat(timespec="seconds"),
                            "client_ip": "127.0.0.1", "bytes_downloaded": 0
                        }
                    except Exception as exc:
                        self.log(f"Could not refresh request history: {exc}")
                        history_item = {
                            "url": url, "status": status_code,
                            "latency_ms": response_ms,
                            "created_at": datetime.now().isoformat(timespec="seconds"),
                            "client_ip": "127.0.0.1", "bytes_downloaded": 0
                        }
                    self.request_rows.append(history_item)
                    self._insert_history_row(history_item)
                    self.kpi_values["requests"].configure(text=str(len(self._analytics_rows())))
                    self._refresh_distribution()
                    self.log(f"Request {status_code} | {response_ms:.0f} ms | {url}")

                elif kind == "traffic":
                    _, incoming, outgoing = event
                    self.traffic_in.append(float(incoming))
                    self.traffic_out.append(float(outgoing))
                    self._update_chart()

                elif kind == "log":
                    self._append_log(event[1])

            except Exception as exc:
                try:
                    self._append_log(f"Dashboard event error ({kind}): {exc}")
                except Exception:
                    pass

        self.root.after(100, self._process_events)

    @staticmethod
    def _format_bytes(value):
        if value < 1024:
            return f"{value:.0f} B"
        if value < 1024 ** 2:
            return f"{value / 1024:.1f} KB"
        if value < 1024 ** 3:
            return f"{value / (1024 ** 2):.1f} MB"
        return f"{value / (1024 ** 3):.2f} GB"

    def _append_log(self, message):
        stamp = datetime.now().strftime("%H:%M:%S")
        self.log_box.insert("end", f"[{stamp}]  {message}\n")
        line_count = int(self.log_box.index("end-1c").split(".")[0])
        excess = line_count - self._max_log_lines
        if excess > 0:
            self.log_box.delete("1.0", f"{excess + 1}.0")
        self.log_box.see("end")

    # ---------- Controls (backend hook points) ----------

    def _start_clicked(self):
        if self.server_running:
            return
        try:
            self.server_controller.start(host="127.0.0.1", port=9000)
        except OSError as exc:
            messagebox.showerror(
                "Could not start server",
                f"Unable to bind 127.0.0.1:9000.\\n{exc}\\n\\n"
                "Check whether another application is already using port 9000."
            )
            self.log(f"Server start failed: {exc}")
        except Exception as exc:
            messagebox.showerror("Server error", str(exc))
            self.log(f"Server start failed: {exc}")

    def _stop_clicked(self):
        try:
            self.server_controller.stop()
        except Exception as exc:
            messagebox.showerror("Server stop error", str(exc))
            self.log(f"Server stop failed: {exc}")

    def _on_close(self):
        if self.server_running:
            if not messagebox.askyesno("Exit", "The server is online. Stop it and close the dashboard?"):
                return
            self.server_controller.stop()
        self.root.destroy()


if __name__ == "__main__":
    app = ctk.CTk()
    dashboard = ProxyDashboard(app)
    app.mainloop()
