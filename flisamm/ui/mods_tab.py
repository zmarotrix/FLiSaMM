"""
The Mod Management tab: installed mods with load order, plus the EAC bypass
and game launch controls.
"""

import logging
import tkinter
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from ..game import EacState, GameError
from ..mods import ARCHIVE_EXTENSIONS, PAK_EXTENSIONS, ModError
from .dialogs import MessageBox, ask_yes_no, run_with_progress, show_message

log = logging.getLogger(__name__)

DANGER_COLOR, DANGER_HOVER = "#D32F2F", "#B71C1C"
TEXT_WRAP = 760  # Fits the minimum window width.
WARNING_TEXT = ("Use mods at your own risk. There are no reported bans from modding so far, "
                "but we do not know how LEVEL-5 will handle this in the future.")
EAC_TEXT = ("Enable this to launch without EAC, which may be required for some mods. You will only "
            "be able to play online with other users who also have the bypass enabled.")


class ModRow(ctk.CTkFrame):
    """One installed mod: on/off switch, name, conflict info and actions."""

    def __init__(self, master, tab):
        super().__init__(master)
        self.tab = tab
        self.mod_id = None
        self.grid_columnconfigure(1, weight=1)
        self.switch_var = tkinter.BooleanVar()
        self.switch = ctk.CTkSwitch(self, text="", width=40, variable=self.switch_var,
                                    command=lambda: tab.toggle_mod(self.mod_id, self.switch_var.get()))
        self.switch.grid(row=0, column=0, rowspan=2, padx=10, pady=8)
        self.name_label = ctk.CTkLabel(self, text="", anchor="w", font=ctk.CTkFont(weight="bold"))
        self.name_label.grid(row=0, column=1, sticky="ew", padx=5, pady=(6, 0))
        self.info_label = ctk.CTkLabel(self, text="", anchor="w", text_color="gray60",
                                       font=ctk.CTkFont(size=11))
        self.info_label.grid(row=1, column=1, sticky="ew", padx=5, pady=(0, 6))
        self.up_button = ctk.CTkButton(self, text="▲", width=30, command=lambda: tab.move_mod(self.mod_id, -1))
        self.up_button.grid(row=0, column=2, rowspan=2, padx=(5, 2))
        self.down_button = ctk.CTkButton(self, text="▼", width=30, command=lambda: tab.move_mod(self.mod_id, 1))
        self.down_button.grid(row=0, column=3, rowspan=2, padx=(2, 5))
        self.delete_button = ctk.CTkButton(self, text="Delete", width=70, fg_color=DANGER_COLOR,
                                           hover_color=DANGER_HOVER, command=lambda: tab.delete_mod(self.mod_id))
        self.delete_button.grid(row=0, column=4, rowspan=2, padx=10)

    def update_row(self, mod, index, count, overrides, overridden_by, locked):
        self.mod_id = mod.id
        self.configure(fg_color="gray22" if index % 2 == 0 else "gray17")
        self.switch_var.set(mod.enabled)
        default_color = ctk.ThemeManager.theme["CTkLabel"]["text_color"]
        self.name_label.configure(text=mod.name, text_color=default_color if mod.enabled else "gray55")
        info = [f"{len(mod.files)} file{'s' if len(mod.files) != 1 else ''}"]
        if overridden_by:
            info.append("overridden by " + ", ".join(sorted(overridden_by)))
        if overrides:
            info.append("overrides " + ", ".join(sorted(overrides)))
        self.info_label.configure(text="  ·  ".join(info),
                                  text_color="#E0A030" if overridden_by else "gray60")
        state = "disabled" if locked else "normal"
        self.switch.configure(state=state)
        self.delete_button.configure(state=state)
        self.up_button.configure(state="disabled" if locked or index == 0 else "normal")
        self.down_button.configure(state="disabled" if locked or index == count - 1 else "normal")


class ModsTab(ctk.CTkFrame):
    """UI for installing and managing mods and game utilities."""

    def __init__(self, master, app, steam_icon=None):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.locked = False
        self._rows = {}
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        self._build(steam_icon)

    @property
    def mods(self):
        return self.app.mod_manager

    def _build(self, steam_icon):
        top = ctk.CTkFrame(self)
        top.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        top.grid_columnconfigure(1, weight=1)
        ctk.CTkButton(top, text="Change...", width=80, command=self.app.prompt_for_game_path).grid(
            row=0, column=0, padx=(10, 5), pady=5)
        self.game_path_label = ctk.CTkLabel(top, text="Game Path: Not Set", anchor="w")
        self.game_path_label.grid(row=0, column=1, sticky="ew", padx=5, pady=5)
        self.install_button = ctk.CTkButton(top, text="Install Mod(s)...", command=self.install_mods)
        self.install_button.grid(row=0, column=2, padx=(5, 10), pady=5)

        warning = ctk.CTkFrame(self, fg_color="#4A2B2B", border_width=1, border_color="#C75450")
        warning.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 10))
        warning.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(warning, text="⚠️", font=ctk.CTkFont(size=24)).grid(row=0, column=0, padx=15, pady=10)
        ctk.CTkLabel(warning, text=WARNING_TEXT, justify="left", anchor="w", wraplength=TEXT_WRAP).grid(
            row=0, column=1, padx=(0, 15), pady=10, sticky="ew")

        self.mod_list = ctk.CTkScrollableFrame(
            self, label_text="Installed Mods  (lower in the list wins when mods change the same file)")
        self.mod_list.grid(row=2, column=0, sticky="nsew", padx=10)
        self.mod_list.grid_columnconfigure(0, weight=1)
        self.empty_label = ctk.CTkLabel(self.mod_list, text="No mods installed.", text_color="gray60")
        self.detected = []
        self.detected_frame = ctk.CTkFrame(self.mod_list, fg_color="#22384A", border_width=1,
                                           border_color="#1F6AA5")
        self.detected_frame.grid_columnconfigure(0, weight=1)
        self.detected_label = ctk.CTkLabel(self.detected_frame, text="", justify="left", anchor="w",
                                           wraplength=TEXT_WRAP - 140)
        self.detected_label.grid(row=0, column=0, sticky="ew", padx=12, pady=8)
        self.import_button = ctk.CTkButton(self.detected_frame, text="Import", width=90,
                                           command=self.import_detected)
        self.import_button.grid(row=0, column=1, padx=12, pady=8)

        list_actions = ctk.CTkFrame(self, fg_color="transparent")
        list_actions.grid(row=3, column=0, sticky="ew", padx=10, pady=(5, 0))
        self.disable_all_button = ctk.CTkButton(list_actions, text="Disable All", width=110,
                                                fg_color="gray30", command=self.disable_all)
        self.disable_all_button.pack(side="left")
        self.reapply_button = ctk.CTkButton(list_actions, text="Re-apply Mods", width=110,
                                            fg_color="gray30", command=self.reapply)
        self.reapply_button.pack(side="left", padx=10)

        utils = ctk.CTkFrame(self)
        utils.grid(row=4, column=0, sticky="ew", padx=10, pady=10)
        utils.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(utils, text="Easy Anti-Cheat Bypass", font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", padx=10, pady=(10, 0))
        ctk.CTkLabel(utils, text=EAC_TEXT, justify="left", anchor="w", wraplength=TEXT_WRAP).grid(
            row=1, column=0, columnspan=2, sticky="ew", padx=10, pady=(0, 5))
        self.eac_var = tkinter.BooleanVar()
        self.eac_switch = ctk.CTkSwitch(utils, text="Bypass Enabled", variable=self.eac_var,
                                        command=self._toggle_eac)
        self.eac_switch.grid(row=2, column=0, sticky="w", padx=10, pady=10)

        launch = ctk.CTkFrame(utils, fg_color="transparent")
        launch.grid(row=2, column=1, sticky="e", padx=10, pady=10)
        if steam_icon:
            ctk.CTkLabel(launch, image=steam_icon, text="").pack(side="left", padx=(0, 5))
        self.steam_var = tkinter.BooleanVar(value=self.app.config.launch_via_steam)
        ctk.CTkSwitch(launch, text="Launch via Steam", variable=self.steam_var,
                      command=self._on_launch_mode_changed).pack(side="left", padx=10)
        self.launch_button = ctk.CTkButton(launch, text="Launch Game", command=self._launch)
        self.launch_button.pack(side="left")

    # --- Refreshing ---

    def refresh(self):
        """Updates the game path, EAC switch and mod rows in place."""
        game = self.app.game
        self.game_path_label.configure(text=f"Game Path: {game.path if game else 'Not Set'}")
        self._refresh_eac()
        self.rescan()

    def rescan(self):
        """Looks for mods in the game folder that FLiSaMM isn't managing yet."""
        try:
            self.detected = self.mods.detect_unmanaged() if self.mods else []
        except OSError:
            log.exception("Could not scan the mods folder")
            self.detected = []
        self._refresh_mods()
        self._update_buttons()

    def set_locked(self, locked):
        self.locked = locked
        self._refresh_mods()
        self._update_buttons()

    def _refresh_eac(self):
        game = self.app.game
        try:
            state = game.eac_state() if game else EacState.OFF
        except OSError:
            log.exception("Could not read the EAC state")
            state = EacState.OFF
        self.eac_var.set(state is EacState.ON)

    def _refresh_mods(self):
        mods = self.mods.mods if self.mods else []
        conflicts = self.mods.conflicts() if self.mods else {}
        for mod_id in list(self._rows):
            if all(m.id != mod_id for m in mods):
                self._rows.pop(mod_id).destroy()
        for row in self._rows.values():
            row.pack_forget()
        self.detected_frame.pack_forget()
        if self.detected:
            names = ", ".join(d.name for d in self.detected[:5])
            more = f" and {len(self.detected) - 5} more" if len(self.detected) > 5 else ""
            count = len(self.detected)
            self.detected_label.configure(
                text=f"Found {count} mod{'s' if count != 1 else ''} in the game folder that FLiSaMM "
                     f"isn't managing yet: {names}{more}.\nImport them to switch them on and off, "
                     "change their load order and delete them from here.")
            self.detected_frame.pack(fill="x", padx=5, pady=(2, 6))
        for i, mod in enumerate(mods):
            row = self._rows.get(mod.id)
            if row is None:
                row = self._rows[mod.id] = ModRow(self.mod_list, self)
            overrides, overridden_by = conflicts.get(mod.id, (set(), set()))
            row.update_row(mod, i, len(mods), overrides, overridden_by, self.locked)
            row.pack(fill="x", padx=5, pady=2)
        if mods or self.detected:
            self.empty_label.pack_forget()
        else:
            self.empty_label.pack(pady=20)

    def _update_buttons(self):
        ready = self.mods is not None and not self.locked
        state = "normal" if ready else "disabled"
        self.install_button.configure(state=state)
        self.reapply_button.configure(state=state)
        self.disable_all_button.configure(state=state if self.mods and self.mods.mods else "disabled")
        self.import_button.configure(state=state)
        self.eac_switch.configure(state="normal" if self.app.game and not self.locked else "disabled")

    # --- Mod actions ---

    def _run(self, message, func, *args):
        """Runs a mod operation in the background and reports any failure."""
        try:
            return run_with_progress(self.app, message, func, *args)
        except (ModError, OSError) as e:
            log.exception("Mod operation failed")
            show_message(self.app, "Mod Error", str(e))
            return None
        finally:
            self.rescan()

    def import_detected(self):
        if not self.mods or not self.app.ensure_game_closed("import mods"):
            return
        self.rescan()
        if self.detected:
            self._run("Importing mods...", self.mods.adopt, self.detected)

    def install_mods(self):
        if not self.mods or not self.app.ensure_game_closed("install mods"):
            return
        patterns = " ".join(f"*{ext}" for ext in sorted(ARCHIVE_EXTENSIONS | PAK_EXTENSIONS))
        paths = filedialog.askopenfilenames(
            title="Select Mod Archive(s) or .pak Files",
            filetypes=[("Mods", patterns), ("All files", "*.*")])
        if not paths:
            return
        for group in _group_sources([Path(p) for p in paths]):
            self._install_one(group)

    def _install_one(self, sources):
        pending = self._run(f"Unpacking {sources[0].name}...", self.mods.stage, sources)
        if pending is None:
            return
        try:
            existing = self.mods.find_by_name(pending.name)
            if pending.warnings:
                message = "\n".join(f"• {w}" for w in pending.warnings)
                if not ask_yes_no(self.app, "Installation Warning",
                                  f"'{pending.name}' may not be packaged correctly:\n\n{message}\n\nInstall anyway?"):
                    return
            if existing:
                answer = MessageBox(self.app, "Mod Already Installed",
                                    f"A mod named '{pending.name}' is already installed.\n\nReplace it with this version?",
                                    buttons=("Replace", "Cancel")).show()
                if answer != "Replace":
                    return
            self._run(f"Installing {pending.name}...", self.mods.commit, pending, bool(existing))
        finally:
            pending.cleanup()

    def toggle_mod(self, mod_id, enabled):
        if not self.app.ensure_game_closed("change mods"):
            self._refresh_mods()
            return
        self._run("Updating mod files...", self.mods.set_enabled, mod_id, enabled)

    def move_mod(self, mod_id, offset):
        if self.app.ensure_game_closed("change the load order"):
            self._run("Updating load order...", self.mods.move, mod_id, offset)

    def delete_mod(self, mod_id):
        mod = self.mods.get(mod_id)
        if not ask_yes_no(self.app, "Confirm Deletion",
                          f"Delete the mod '{mod.name}'? Its files are removed from the game folder and "
                          "any game files it replaced are restored."):
            return
        if self.app.ensure_game_closed("delete mods"):
            self._run(f"Removing {mod.name}...", self.mods.delete, mod_id)

    def disable_all(self):
        if self.app.ensure_game_closed("change mods"):
            self._run("Disabling all mods...", self.mods.disable_all)

    def reapply(self):
        if self.app.ensure_game_closed("re-apply mods"):
            self._run("Re-applying mods...", self.mods.sync)

    # --- Game utilities ---

    def _toggle_eac(self):
        game = self.app.game
        if not game or not self.app.ensure_game_closed("change the EAC bypass"):
            self._refresh_eac()
            return
        try:
            if self.eac_var.get():
                game.apply_eac_bypass()
            else:
                game.remove_eac_bypass()
        except (GameError, OSError) as e:
            log.exception("EAC toggle failed")
            show_message(self.app, "Error", str(e))
        self._refresh_eac()

    def _on_launch_mode_changed(self):
        self.app.config.launch_via_steam = self.steam_var.get()
        self.app.config.save()

    def _launch(self):
        if not self.app.game:
            show_message(self.app, "Error", "Game path is not set.")
            return
        try:
            self.app.game.launch(via_steam=self.steam_var.get())
        except GameError as e:
            show_message(self.app, "Error", str(e))


def _group_sources(paths):
    """Groups selected files into installs: one per archive, one per .pak set."""
    groups, paks = [], {}
    for path in paths:
        if path.suffix.lower() in PAK_EXTENSIONS:
            paks.setdefault(path.stem.lower(), []).append(path)
        else:
            groups.append([path])
    return groups + list(paks.values())

