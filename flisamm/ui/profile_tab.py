"""
The contents of one save profile tab: its slot list and the selected slot's
Active Save and manual backups.
"""

import logging
import random
import tkinter
from datetime import datetime

import customtkinter as ctk

from ..constants import FL_ADJECTIVES, FL_NOUNS
from ..saves import SaveError, SaveProfile
from .dialogs import (
    ChoiceDialog, InputDialog, ask_yes_no, ask_yes_no_cancel, run_with_progress, show_message
)

log = logging.getLogger(__name__)

SELECTED_COLOR = "#1F6AA5"
LOADED_COLOR = "#0E496D"
DANGER_COLOR, DANGER_HOVER = "#D32F2F", "#B71C1C"
SORT_OPTIONS = {
    "Newest first": (lambda b: b[1].timestamp, True),
    "Oldest first": (lambda b: b[1].timestamp, False),
    "Name (A-Z)": (lambda b: b[1].name.lower(), False),
}


def random_slot_name():
    return f"{random.choice(FL_ADJECTIVES)} {random.choice(FL_NOUNS)}"


def _format_time(ts, seconds=False):
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S" if seconds else "%Y-%m-%d %H:%M")


class ProfileTab(ctk.CTkFrame):
    """UI and actions for a single save profile."""

    def __init__(self, master, app, profile: SaveProfile, icon=None):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.profile = profile
        self.selected_slot = None
        self.selected_backup = None
        self.locked = False
        self.search_var = tkinter.StringVar()
        self.sort_var = tkinter.StringVar(value=next(iter(SORT_OPTIONS)))
        self._backup_rows = []

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._build_title(icon)
        self._build_body()

        if profile.active_slot_id:
            self.selected_slot = profile.active_slot_id
        elif profile.slots:
            self.selected_slot = next(iter(profile.slots))
        self.refresh()

    # --- Layout ---

    def _build_title(self, icon):
        title_frame = ctk.CTkFrame(self, fg_color="transparent")
        title_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(5, 0))
        ctk.CTkLabel(
            title_frame, text=f" {self.profile.name}", image=icon, compound="left",
            font=ctk.CTkFont(size=14, weight="bold"), anchor="w").pack(side="left", pady=5)
        ctk.CTkLabel(
            title_frame, text=str(self.profile.live_path), text_color="gray60",
            font=ctk.CTkFont(size=11), anchor="w").pack(side="left", padx=10)
        if self.profile.name.startswith("Steam"):
            ctk.CTkLabel(
                self, text="Steam Cloud: if Steam reports a sync conflict after you switch slots, "
                           "keep the files on this PC.",
                text_color="gray60", font=ctk.CTkFont(size=11), anchor="w"
            ).grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 2))

    def _build_body(self):
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew")
        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=3)
        body.grid_rowconfigure(0, weight=1)

        # Left: slots.
        left = ctk.CTkFrame(body)
        left.grid(row=0, column=0, sticky="nsew", padx=(10, 2), pady=10)
        left.grid_rowconfigure(0, weight=1)
        left.grid_columnconfigure(0, weight=1)
        self.slot_list = ctk.CTkScrollableFrame(left, label_text="Save Slots")
        self.slot_list.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self.load_slot_button = ctk.CTkButton(left, text="Load Slot", command=self._load_slot)
        self.load_slot_button.grid(row=1, column=0, sticky="ew", padx=5, pady=5)
        actions = ctk.CTkFrame(left, fg_color="transparent")
        actions.grid(row=2, column=0, sticky="ew", padx=5)
        actions.grid_columnconfigure((0, 1), weight=1)
        self.rename_slot_button = ctk.CTkButton(actions, text="Rename", command=self._rename_slot)
        self.rename_slot_button.grid(row=0, column=0, sticky="ew", padx=(0, 3), pady=(0, 5))
        self.delete_slot_button = ctk.CTkButton(
            actions, text="Delete", fg_color=DANGER_COLOR, hover_color=DANGER_HOVER,
            command=lambda: self._delete_slot(self.selected_slot))
        self.delete_slot_button.grid(row=0, column=1, sticky="ew", padx=(3, 0), pady=(0, 5))
        self.copy_slot_button = ctk.CTkButton(actions, text="Copy Slot to...", command=self._copy_slot)
        self.copy_slot_button.grid(row=1, column=0, columnspan=2, sticky="ew")
        ctk.CTkButton(left, text="[ + ] Create New Empty Slot", command=self._create_slot).grid(
            row=3, column=0, sticky="ew", padx=5, pady=5)

        # Right: details of the selected slot.
        details = ctk.CTkFrame(body, fg_color="gray14")
        details.grid(row=0, column=1, sticky="nsew", padx=(2, 10), pady=10)
        self.placeholder = ctk.CTkLabel(details, text="Select a slot or create one.")
        self.content = ctk.CTkFrame(details, fg_color="transparent")
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(2, weight=1)

        self.active_frame = ctk.CTkFrame(self.content, border_width=2, border_color="gray24")
        self.active_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        self.active_frame.grid_columnconfigure(0, weight=1)
        self.active_label = ctk.CTkLabel(self.active_frame, text="", anchor="w")
        self.active_label.grid(row=0, column=0, sticky="ew", padx=10, pady=5)

        controls = ctk.CTkFrame(self.content)
        controls.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 10))
        search = ctk.CTkEntry(controls, placeholder_text="Search manual backups...",
                              textvariable=self.search_var)
        search.pack(side="left", padx=(0, 10), expand=True, fill="x")
        self.search_var.trace_add("write", lambda *_: self._refresh_backups())
        ctk.CTkOptionMenu(controls, variable=self.sort_var, values=list(SORT_OPTIONS),
                          command=lambda _: self._refresh_backups()).pack(side="left")

        self.backup_list = ctk.CTkScrollableFrame(self.content, label_text="Manual Backups")
        self.backup_list.grid(row=2, column=0, sticky="nsew", padx=10)
        self.backup_list.grid_columnconfigure(0, weight=1)
        self.empty_backups_label = ctk.CTkLabel(self.backup_list, text="No backups yet.", text_color="gray60")

        backup_actions = ctk.CTkFrame(self.content)
        backup_actions.grid(row=3, column=0, sticky="ew", padx=10, pady=10)
        self.rename_backup_button = ctk.CTkButton(
            backup_actions, text="Rename Backup", command=self._rename_backup)
        self.rename_backup_button.pack(side="left", padx=5, pady=5)
        self.delete_backup_button = ctk.CTkButton(
            backup_actions, text="Delete Backup", fg_color=DANGER_COLOR, hover_color=DANGER_HOVER,
            command=self._delete_backup)
        self.delete_backup_button.pack(side="left", padx=5, pady=5)
        self.create_backup_button = ctk.CTkButton(
            backup_actions, text="Create New Backup", command=self._create_backup)
        self.create_backup_button.pack(side="right", padx=5, pady=5)

    # --- Refreshing ---

    def refresh(self):
        """Redraws the slot list and details to match the profile."""
        if self.selected_slot not in self.profile.slots:
            self.selected_slot = None
        if self.selected_slot is None or self.selected_backup not in self.profile.slots[self.selected_slot].backups:
            self.selected_backup = None
        self._refresh_slots()
        self._refresh_details()
        self._update_buttons()

    def set_locked(self, locked):
        self.locked = locked
        self._update_buttons()
        self._refresh_backups()

    def on_game_stopped(self):
        """Captures the latest progress into the loaded slot once the game closes."""
        try:
            self.profile.sync_active_slot()
        except (OSError, SaveError):
            log.exception("Could not sync the loaded slot for %s", self.profile.name)
        self.refresh()

    def _refresh_slots(self):
        for widget in self.slot_list.winfo_children():
            widget.destroy()
        active = self.profile.active_slot_id
        loaded = active if self.profile.has_live_save() else None
        slots = sorted(self.profile.slots.items(),
                       key=lambda item: (item[0] != loaded, item[1].name.lower()))
        for slot_id, slot in slots:
            text = f"{slot.name} [LOADED]" if slot_id == loaded else slot.name
            color = SELECTED_COLOR if slot_id == self.selected_slot else (
                LOADED_COLOR if slot_id == loaded else "gray30")
            btn = ctk.CTkButton(self.slot_list, text=text, fg_color=color, anchor="w",
                                command=lambda s=slot_id: self._select_slot(s))
            btn.pack(fill="x", pady=2, padx=2)
            btn.bind("<Button-3>", lambda e, s=slot_id: self._show_slot_menu(e, s))
        if not slots:
            ctk.CTkLabel(self.slot_list, text="No slots yet.", text_color="gray60").pack(pady=10)

    def _refresh_details(self):
        slot = self.profile.slots.get(self.selected_slot)
        if slot is None:
            self.content.pack_forget()
            self.placeholder.pack(expand=True)
            return
        self.placeholder.pack_forget()
        self.content.pack(expand=True, fill="both")
        is_loaded = self.profile.is_slot_loaded(self.selected_slot)
        self.active_frame.configure(border_color=SELECTED_COLOR if is_loaded else "gray24")
        if slot.active_save_timestamp:
            prefix = "[LOADED] " if is_loaded else ""
            self.active_label.configure(
                text=f"{prefix}Active Save - last played {_format_time(slot.active_save_timestamp, True)}")
        elif self.selected_slot == self.profile.active_slot_id:
            self.active_label.configure(text="Empty slot - launch the game to start a new save for it.")
        else:
            self.active_label.configure(text="No active save for this slot.")
        self._refresh_backups()

    def _refresh_backups(self):
        slot = self.profile.slots.get(self.selected_slot)
        if slot is None:
            return
        backups = list(slot.backups.items())
        term = self.search_var.get().strip().lower()
        if term:
            backups = [b for b in backups if term in b[1].name.lower()]
        key, reverse = SORT_OPTIONS[self.sort_var.get()]
        backups.sort(key=key, reverse=reverse)

        # Reuse row widgets; the pool grows to fit any number of backups.
        while len(self._backup_rows) < len(backups):
            self._backup_rows.append(self._make_backup_row())
        for row, (backup_id, backup) in zip(self._backup_rows, backups):
            selected = backup_id == self.selected_backup
            row["name"].configure(
                text=f"{backup.name}  ({_format_time(backup.timestamp)})",
                fg_color="gray25" if selected else "transparent",
                command=lambda b=backup_id: self._select_backup(b))
            row["load"].configure(
                state="disabled" if self.locked else "normal",
                command=lambda b=backup_id: self._restore_backup(b))
            row["frame"].pack(fill="x", pady=2)
        for row in self._backup_rows[len(backups):]:
            row["frame"].pack_forget()
        if backups:
            self.empty_backups_label.pack_forget()
        else:
            self.empty_backups_label.configure(text="No matching backups." if term else "No backups yet.")
            self.empty_backups_label.pack(pady=10)

    def _make_backup_row(self):
        frame = ctk.CTkFrame(self.backup_list, fg_color="transparent")
        frame.grid_columnconfigure(0, weight=1)
        name = ctk.CTkButton(frame, text="", fg_color="transparent", anchor="w", hover_color="gray25")
        name.grid(row=0, column=0, sticky="ew")
        load = ctk.CTkButton(frame, text="Load", width=60)
        load.grid(row=0, column=1, padx=5)
        return {"frame": frame, "name": name, "load": load}

    def _update_buttons(self):
        has_slot = self.selected_slot in self.profile.slots
        is_loaded = has_slot and self.profile.is_slot_loaded(self.selected_slot)
        is_active = has_slot and self.selected_slot == self.profile.active_slot_id

        def state(enabled):
            return "normal" if enabled else "disabled"

        self.load_slot_button.configure(state=state(has_slot and not self.locked and not is_loaded))
        self.rename_slot_button.configure(state=state(has_slot))
        self.delete_slot_button.configure(state=state(has_slot and not (is_active and self.locked)))
        self.copy_slot_button.configure(state=state(has_slot))
        self.create_backup_button.configure(state=state(is_loaded))
        self.rename_backup_button.configure(state=state(self.selected_backup is not None))
        self.delete_backup_button.configure(state=state(self.selected_backup is not None))

    # --- Selection ---

    def _select_slot(self, slot_id):
        self.selected_slot = slot_id
        self.selected_backup = None
        self.refresh()

    def _select_backup(self, backup_id):
        self.selected_backup = backup_id
        self._refresh_backups()
        self._update_buttons()

    def _show_slot_menu(self, event, slot_id):
        menu = tkinter.Menu(self, tearoff=0)
        menu.add_command(label="Rename", command=lambda: (self._select_slot(slot_id), self._rename_slot()))
        menu.add_command(label=f"Delete '{self.profile.slots[slot_id].name}'",
                         command=lambda: self._delete_slot(slot_id))
        menu.tk_popup(event.x_root, event.y_root)

    # --- Actions ---

    def _run(self, action, *args, progress=None):
        """Runs a profile operation, reporting failures instead of crashing."""
        try:
            if progress:
                return run_with_progress(self.app, progress, action, *args)
            return action(*args)
        except (SaveError, OSError) as e:
            log.exception("Save operation failed")
            show_message(self.app, "Error", str(e))
            return None
        finally:
            self.refresh()

    def _load_slot(self):
        if not self.app.ensure_game_closed("load a save slot"):
            return
        had_save = self._run(self.profile.load_slot, self.selected_slot, progress="Loading save slot...")
        if had_save is False:
            show_message(self.app, "Empty Slot Loaded",
                         "The save folder has been cleared. Launch the game to create a new save for this slot.")

    def _create_slot(self):
        name = InputDialog(self.app, "Create New Empty Slot", "Enter a name for the new slot:",
                           random_slot_name(), random_slot_name).show()
        if name:
            self.selected_slot = self._run(self.profile.create_slot, name) or self.selected_slot
            self.refresh()

    def _rename_slot(self):
        slot = self.profile.slots.get(self.selected_slot)
        if not slot:
            return
        name = InputDialog(self.app, "Rename Slot", "Enter new name:", slot.name, random_slot_name).show()
        if name:
            self._run(self.profile.rename_slot, self.selected_slot, name)

    def _delete_slot(self, slot_id):
        slot = self.profile.slots.get(slot_id)
        if not slot:
            return
        is_active = slot_id == self.profile.active_slot_id
        if is_active and not self.app.ensure_game_closed("delete the loaded slot"):
            return
        if not ask_yes_no(self.app, "Confirm Deletion",
                          f"Permanently delete slot '{slot.name}' and ALL its backups?"):
            return
        if is_active:
            if not ask_yes_no(self.app, "Warning!",
                              f"'{slot.name}' is the loaded slot for '{self.profile.name}'. Deleting it also "
                              "clears the game's save files in this location (a safety copy is kept in the "
                              "data folder).\n\nOther profiles are not affected. Continue?"):
                return
        self._run(self.profile.delete_slot, slot_id)

    def _copy_slot(self):
        destinations = self.app.copy_destinations(self.profile)
        if not destinations:
            show_message(self.app, "Copy Not Possible", "No other save profiles could be found to copy to.")
            return
        choice = ChoiceDialog(self.app, "Copy Slot to...", "Select destination profile:", list(destinations)).show()
        if not choice:
            return
        dest = destinations[choice]
        slot_id = self.selected_slot
        if slot_id in dest.slots and not ask_yes_no(
                self.app, "Confirm Replacement",
                f"Slot '{dest.slots[slot_id].name}' already exists in '{choice}'.\n\nReplace it?"):
            return
        try:
            run_with_progress(self.app, "Copying slot...", self.profile.copy_slot_to, dest, slot_id)
        except (SaveError, OSError) as e:
            log.exception("Copy failed")
            show_message(self.app, "Copy Failed", str(e))
            return
        show_message(self.app, "Success", f"Slot copied to '{choice}'.")
        self.app.rebuild_save_tabs(keep=self.profile.name)

    def _create_backup(self):
        self._run(self.profile.create_backup, self.selected_slot)

    def _rename_backup(self):
        slot = self.profile.slots.get(self.selected_slot)
        if not slot or self.selected_backup not in slot.backups:
            return
        name = InputDialog(self.app, "Rename Backup", "Enter new name:",
                           slot.backups[self.selected_backup].name).show()
        if name:
            self._run(self.profile.rename_backup, self.selected_slot, self.selected_backup, name)

    def _delete_backup(self):
        slot = self.profile.slots.get(self.selected_slot)
        if not slot or self.selected_backup not in slot.backups:
            return
        name = slot.backups[self.selected_backup].name
        if ask_yes_no(self.app, "Confirm Deletion", f"Permanently delete the manual backup '{name}'?"):
            self._run(self.profile.delete_backup, self.selected_slot, self.selected_backup)

    def _restore_backup(self, backup_id):
        if not self.app.ensure_game_closed("load a backup"):
            return
        slot_id = self.selected_slot
        backup_name = self.profile.slots[slot_id].backups[backup_id].name
        active = self.profile.active_slot_id
        if active and self.profile.has_live_save():
            active_name = self.profile.slots[active].name
            answer = ask_yes_no_cancel(
                self.app, "Backup Current Save?",
                f"Loading '{backup_name}' will replace the current progress of '{active_name}'.\n\n"
                f"Make a backup of '{active_name}' first?")
            if answer is None:
                return
            if answer:
                name = f"Auto-Backup {datetime.now():%Y-%m-%d %H.%M.%S}"
                if self._run(self.profile.create_backup, active, name) is None:
                    return
        self._run(self.profile.restore_backup, slot_id, backup_id, progress="Loading backup...")
