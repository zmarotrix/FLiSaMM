"""
Custom, theme-aware dialogs: message boxes, text input, choices, and a
progress dialog for work that runs on a background thread.
"""

import threading
import tkinter

import customtkinter as ctk


class _Dialog(ctk.CTkToplevel):
    """Base class for modal dialogs centred on their parent window."""

    def __init__(self, parent, title):
        super().__init__(parent)
        self.transient(parent)
        self.title(title)
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.bind("<Escape>", lambda e: self._cancel())
        self.result = None

    def _show(self):
        """Centres the dialog, makes it modal and waits until it is closed."""
        self.update_idletasks()
        parent = self.master
        x = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        self.lift()
        self.wait_visibility()
        self.grab_set()
        self.master.wait_window(self)
        return self.result

    def _finish(self, value):
        self.result = value
        self.destroy()

    def _cancel(self):
        self._finish(None)


class MessageBox(_Dialog):
    """A message with a row of buttons; returns the text of the one clicked."""

    def __init__(self, parent, title, message, buttons=("OK",)):
        super().__init__(parent, title)
        self.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self, text=message, wraplength=420, justify="left").grid(
            row=0, column=0, padx=20, pady=20, sticky="w")

        button_frame = ctk.CTkFrame(self, fg_color="transparent")
        button_frame.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="e")
        for i, text in enumerate(buttons):
            btn = ctk.CTkButton(button_frame, text=text, width=100,
                                command=lambda v=text: self._finish(v))
            btn.pack(side="left", padx=5)
            if i == 0:
                btn.focus_set()
                self.bind("<Return>", lambda e, v=text: self._finish(v))

    def show(self):
        return self._show()


class InputDialog(_Dialog):
    """Asks for a non-empty line of text; returns it stripped, or None."""

    def __init__(self, parent, title, prompt, initial_value="", random_name_func=None):
        super().__init__(parent, title)
        self._random_name_func = random_name_func

        ctk.CTkLabel(self, text=prompt, wraplength=380).pack(pady=(15, 5), padx=15, fill="x")
        self._value = tkinter.StringVar(value=initial_value)
        self._entry = ctk.CTkEntry(self, textvariable=self._value, width=380)
        self._entry.pack(pady=5, padx=15)
        self._entry.select_range(0, "end")
        self._entry.focus_set()
        self._default_border = self._entry.cget("border_color")

        button_frame = ctk.CTkFrame(self, fg_color="transparent")
        button_frame.pack(pady=15, padx=15)
        if random_name_func:
            ctk.CTkButton(button_frame, text="Generate Random", fg_color="gray",
                          command=lambda: self._value.set(random_name_func())).pack(side="left", padx=5)
        ctk.CTkButton(button_frame, text="OK", width=100, command=self._ok).pack(side="left", padx=5)
        ctk.CTkButton(button_frame, text="Cancel", width=100, command=self._cancel).pack(side="left", padx=5)
        self.bind("<Return>", lambda e: self._ok())

    def _ok(self):
        value = self._value.get().strip()
        if not value:
            self._entry.configure(border_color="#E53935")
            return
        self._finish(value)

    def show(self):
        return self._show()


class ChoiceDialog(_Dialog):
    """Lets the user pick one option from a list; returns it, or None."""

    def __init__(self, parent, title, prompt, options):
        super().__init__(parent, title)
        ctk.CTkLabel(self, text=prompt).pack(pady=(15, 5), padx=15)
        self._choice = tkinter.StringVar(value=options[0])
        ctk.CTkOptionMenu(self, variable=self._choice, values=list(options), width=380).pack(
            pady=5, padx=15, fill="x")
        button_frame = ctk.CTkFrame(self, fg_color="transparent")
        button_frame.pack(pady=15, padx=15)
        ctk.CTkButton(button_frame, text="OK", width=100,
                      command=lambda: self._finish(self._choice.get())).pack(side="left", padx=5)
        ctk.CTkButton(button_frame, text="Cancel", width=100, command=self._cancel).pack(side="left", padx=5)

    def show(self):
        return self._show()


class _ProgressDialog(_Dialog):
    def __init__(self, parent, message):
        super().__init__(parent, "Please wait")
        self.protocol("WM_DELETE_WINDOW", lambda: None)  # Can't be cancelled.
        self.unbind("<Escape>")
        ctk.CTkLabel(self, text=message, wraplength=360).pack(padx=25, pady=(20, 10))
        bar = ctk.CTkProgressBar(self, mode="indeterminate", width=320)
        bar.pack(padx=25, pady=(0, 25))
        bar.start()


def run_with_progress(parent, message, func, *args):
    """Runs func on a worker thread behind a modal progress dialog.

    The UI stays responsive while it runs. Returns func's result, or re-raises
    the exception it raised.
    """
    outcome = {}

    def worker():
        try:
            outcome["result"] = func(*args)
        except BaseException as e:
            outcome["error"] = e

    dialog = _ProgressDialog(parent, message)
    thread = threading.Thread(target=worker, name="Worker", daemon=True)
    thread.start()

    def poll():
        # Wait until the dialog is on screen too, so _show() is ready for it to close.
        if thread.is_alive() or not dialog.winfo_viewable():
            dialog.after(100, poll)
        else:
            dialog.destroy()

    dialog.after(100, poll)
    dialog._show()
    if "error" in outcome:
        raise outcome["error"]
    return outcome.get("result")


def show_message(parent, title, message):
    MessageBox(parent, title, message).show()


def ask_yes_no(parent, title, message):
    return MessageBox(parent, title, message, buttons=("Yes", "No")).show() == "Yes"


def ask_yes_no_cancel(parent, title, message):
    """Returns True for Yes, False for No and None for Cancel."""
    answer = MessageBox(parent, title, message, buttons=("Yes", "No", "Cancel")).show()
    return {"Yes": True, "No": False}.get(answer)
