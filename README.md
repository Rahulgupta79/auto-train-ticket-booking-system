import queue
import threading
import time
from tkinter import messagebox

import customtkinter as ctk

from app.automation import IRCTCAssistant
from app.config import APP_TITLE, BOOKING_NOTE


class TrainBookingApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1000x700")
        self.minsize(900, 600)

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.result_queue = queue.Queue()
        self.assistant = IRCTCAssistant(log_callback=self._queue_log)
        self.current_thread = None

        self._build_ui()
        self.after(200, self._process_queue)

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self, corner_radius=12)
        header.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="ew")
        header.grid_columnconfigure((0, 1, 2, 3), weight=1)

        self.username_entry = ctk.CTkEntry(header, placeholder_text="IRCTC Username")
        self.username_entry.grid(row=0, column=0, padx=10, pady=10, sticky="ew")

        self.password_entry = ctk.CTkEntry(header, placeholder_text="Password", show="*")
        self.password_entry.grid(row=0, column=1, padx=10, pady=10, sticky="ew")

        self.from_entry = ctk.CTkEntry(header, placeholder_text="From Station")
        self.from_entry.grid(row=1, column=0, padx=10, pady=10, sticky="ew")

        self.to_entry = ctk.CTkEntry(header, placeholder_text="To Station")
        self.to_entry.grid(row=1, column=1, padx=10, pady=10, sticky="ew")

        self.date_entry = ctk.CTkEntry(header, placeholder_text="Journey Date (DD-MM-YYYY)")
        self.date_entry.grid(row=1, column=2, padx=10, pady=10, sticky="ew")

        self.class_var = ctk.StringVar(value="CC")
        self.class_menu = ctk.CTkOptionMenu(
            header,
            values=["CC", "SL", "2A", "3A", "3E"],
            variable=self.class_var,
        )
        self.class_menu.grid(row=1, column=3, padx=10, pady=10, sticky="ew")

        buttons = ctk.CTkFrame(self, corner_radius=12)
        buttons.grid(row=0, column=0, padx=20, pady=(0, 10), sticky="ew")
        buttons.grid_columnconfigure((0, 1), weight=1)

        self.start_button = ctk.CTkButton(buttons, text="Launch Browser & Search", command=self.start_automation)
        self.start_button.grid(row=0, column=0, padx=10, pady=12, sticky="ew")

        self.close_button = ctk.CTkButton(buttons, text="Close Browser", command=self.close_browser)
        self.close_button.grid(row=0, column=1, padx=10, pady=12, sticky="ew")

        content = ctk.CTkFrame(self, corner_radius=12)
        content.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="nsew")
        content.grid_rowconfigure(0, weight=1)
        content.grid_columnconfigure(0, weight=1)

        self.log_box = ctk.CTkTextbox(content, height=18, wrap="word")
        self.log_box.grid(row=0, column=0, padx=10, pady=(10, 5), sticky="nsew")

        self.results_box = ctk.CTkTextbox(content, height=18, wrap="word")
        self.results_box.grid(row=1, column=0, padx=10, pady=(5, 10), sticky="nsew")

        self.log_box.insert("end", BOOKING_NOTE + "\n\n")
        self.log_box.insert("end", "Ready. Enter your credentials and search details.\n")
        self.log_box.configure(state="disabled")
        self.results_box.configure(state="disabled")

    def _queue_log(self, message: str) -> None:
        self.result_queue.put(message)

    def _process_queue(self):
        try:
            while True:
                message = self.result_queue.get_nowait()
                self.log_box.configure(state="normal")
                self.log_box.insert("end", message + "\n")
                self.log_box.see("end")
                self.log_box.configure(state="disabled")
        except Exception:
            pass
        self.after(200, self._process_queue)

    def start_automation(self):
        username = self.username_entry.get().strip()
        password = self.password_entry.get().strip()
        from_station = self.from_entry.get().strip()
        to_station = self.to_entry.get().strip()
        journey_date = self.date_entry.get().strip()
        travel_class = self.class_var.get()

        if not username or not password:
            messagebox.showwarning("Missing data", "Please enter your username and password.")
            return

        if not from_station or not to_station:
            messagebox.showwarning("Missing data", "Please fill from and to stations.")
            return

        self.start_button.configure(state="disabled")
        self.current_thread = threading.Thread(
            target=self._run_task,
            args=(username, password, from_station, to_station, journey_date, travel_class),
            daemon=True,
        )
        self.current_thread.start()

    def _run_task(self, username, password, from_station, to_station, journey_date, travel_class):
        try:
            self.assistant.start_browser()
            self.assistant.login(username, password)
            results = self.assistant.search_trains(from_station, to_station, journey_date, travel_class)

            self.results_box.configure(state="normal")
            self.results_box.delete("1.0", "end")
            if not results:
                self.results_box.insert("end", "No train results found in the current page state.\n")
            else:
                for index, item in enumerate(results, start=1):
                    self.results_box.insert("end", f"{index}. {item}\n\n")
            self.results_box.configure(state="disabled")
            self.assistant.log("Task completed. Review the available trains and confirm the final booking action manually.")
        except Exception as exc:
            self.assistant.log(f"Task failed: {exc}")
        finally:
            self.start_button.configure(state="normal")

    def close_browser(self):
        try:
            self.assistant.close()
            self.results_box.configure(state="normal")
            self.results_box.delete("1.0", "end")
            self.results_box.insert("end", "Browser closed.\n")
            self.results_box.configure(state="disabled")
        except Exception as exc:
            self.assistant.log(f"Close failed: {exc}")

    def on_close(self):
        self.assistant.close()
        self.destroy()
