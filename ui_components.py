"""
Contains custom, theme-aware UI components for the application, such as
dialog boxes and message boxes.
"""

import tkinter
import customtkinter as ctk


class CustomMessageBox(ctk.CTkToplevel):
    """A custom, theme-aware messagebox that matches the application's style."""
    def __init__(self, parent, title="Message", message="", buttons=("OK",)):
        super().__init__(parent)
        self.transient(parent)
        self.title(title)
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self._cancel_pressed)
        self.grab_set()

        self._result = None
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        ctk.CTkLabel(self, text=message, wraplength=380, justify="left").grid(
            row=0, column=0, padx=20, pady=20)

        button_frame = ctk.CTkFrame(self, fg_color="transparent")
        button_frame.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="e")

        for i, button_text in enumerate(reversed(buttons)):
            btn = ctk.CTkButton(
                button_frame, text=button_text,
                command=lambda val=button_text: self._button_pressed(val),
                width=100
            )
            btn.pack(side="right", padx=5)
            if i == 0:
                btn.focus_set()
                self.bind("<Return>", lambda e, val=button_text: self._button_pressed(val))

        self.bind("<Escape>", self._cancel_pressed)
        self.update_idletasks()

        parent_x, parent_y = parent.winfo_x(), parent.winfo_y()
        parent_w, parent_h = parent.winfo_width(), parent.winfo_height()
        self_w, self_h = self.winfo_width(), self.winfo_height()
        self.geometry(f"+{parent_x + (parent_w - self_w) // 2}+{parent_y + (parent_h - self_h) // 2}")

    def _button_pressed(self, value):
        self._result = value
        self.destroy()

    def _cancel_pressed(self, event=None):
        self.destroy()

    def get(self):
        """Waits for user input and returns the text of the button clicked."""
        self.master.wait_window(self)
        return self._result


class CustomInputDialog(ctk.CTkToplevel):
    """A custom dialog window for user text input."""
    def __init__(self, parent, title="Input", prompt="", initial_value="",
                 random_name_func=None):
        super().__init__(parent)
        self.transient(parent)
        self.title(title)
        self.geometry("400x180")
        self.protocol("WM_DELETE_WINDOW", self._cancel_pressed)
        self.resizable(False, False)

        self._user_input = None
        self._random_name_func = random_name_func

        ctk.CTkLabel(self, text=prompt, wraplength=380).pack(
            pady=(10, 5), padx=10, fill="x")

        self._entry_value = tkinter.StringVar(value=initial_value)
        self._entry = ctk.CTkEntry(
            self, textvariable=self._entry_value, width=380)
        self._entry.pack(pady=5, padx=10)
        self._entry.focus_set()

        button_frame = ctk.CTkFrame(self, fg_color="transparent")
        button_frame.pack(pady=20, padx=10)

        if self._random_name_func:
            ctk.CTkButton(
                button_frame, text="Generate Random", fg_color="gray",
                command=self._generate_random).pack(side="left", padx=10)

        ctk.CTkButton(
            button_frame, text="OK", command=self._ok_pressed,
            width=100).pack(side="left", padx=10)
        ctk.CTkButton(
            button_frame, text="Cancel", command=self._cancel_pressed,
            width=100).pack(side="left", padx=10)

        self.bind("<Return>", self._ok_pressed)
        self.bind("<Escape>", self._cancel_pressed)
        self.grab_set()

        # --- ADDED: Center the dialog on the parent window ---
        self.update_idletasks()
        parent_x, parent_y = parent.winfo_x(), parent.winfo_y()
        parent_w, parent_h = parent.winfo_width(), parent.winfo_height()
        self_w, self_h = self.winfo_width(), self.winfo_height()
        self.geometry(f"+{parent_x + (parent_w - self_w) // 2}+{parent_y + (parent_h - self_h) // 2}")

    def _generate_random(self):
        if self._random_name_func:
            self._entry_value.set(self._random_name_func())

    def _ok_pressed(self, event=None):
        self._user_input = self._entry_value.get()
        self.destroy()

    def _cancel_pressed(self, event=None):
        self._user_input = None
        self.destroy()

    def get_input(self):
        """Waits for the dialog to close and returns the user's input."""
        self.master.wait_window(self)
        return self._user_input