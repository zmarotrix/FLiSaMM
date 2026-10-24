"""
Main application window. It owns the backend objects and the game-running
lock, and hosts the Save Management and Mod Management tabs.
"""

import logging
import os
import traceback
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk
from PIL import Image

from ..config import AppConfig
from ..constants import APP_NAME, APP_VERSION, GAME_FOLDER_NAME, WINDOW_MIN_SIZE, WINDOW_SIZE
from ..game import EacState, GameError, GameInstall, GameWatcher, is_game_running, validate_game_path
from ..mods import ModError, ModManager
from ..paths import path_key, resource_path
from ..saves import SaveError, SaveProfile, discover_save_locations
from ..steam import find_game_install, find_steam_path
from .dialogs import ask_yes_no, show_message
from .mods_tab import ModsTab
from .profile_tab import ProfileTab, random_slot_name

log = logging.getLogger(__name__)


class App(ctk.CTk):
    """The main application window."""

    def __init__(self, data_dir):
        super().__init__()
        self.data_dir = Path(data_dir)
        self.installs_root = self.data_dir / "installs"
        self.profiles_root = self.data_dir / "profiles"
        self.config = AppConfig.load(self.data_dir)
        self.game = None
        self.mod_manager = None
        self.profile_tabs = {}
        self.locked = False
        self.steam_path = find_steam_path()

        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")
        self.title(f"{APP_NAME} v{APP_VERSION}")
        self._place_window()
        self.report_callback_exception = self._on_callback_error
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self.logo_image = self._load_image("logo.png", (242, 80))
        self.steam_icon = self._load_image("steam.png", (24, 24))

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._create_header()
        self._create_tabs()

        self.watcher = GameWatcher()
        self.watcher.start()
        self.after(100, self._startup)
        self.after(500, self._poll_game_state)

    # --- Window setup ---

    def _place_window(self):
        width, height = WINDOW_SIZE
        screen_w, screen_h = self.winfo_screenwidth(), self.winfo_screenheight()
        # Leave room for the taskbar on small screens.
        width, height = min(width, screen_w - 40), min(height, screen_h - 80)
        x, y = (screen_w - width) // 2, max((screen_h - height) // 2 - 20, 0)
        self.geometry(f"{width}x{height}+{x}+{y}")
        self.minsize(*WINDOW_MIN_SIZE)

    @staticmethod
    def _load_image(name, size):
        try:
            image = Image.open(resource_path(name))
        except OSError:
            log.warning("Image resource '%s' not found.", name)
            return None
        return ctk.CTkImage(light_image=image, dark_image=image, size=size)

    def _create_header(self):
        header = ctk.CTkFrame(self, corner_radius=0)
        header.grid(row=0, column=0, sticky="ew", padx=10, pady=(0, 10))
        header.grid_columnconfigure(0, weight=1)
        if self.logo_image:
            ctk.CTkLabel(header, image=self.logo_image, text="").grid(row=0, column=0, pady=(10, 0))
        ctk.CTkLabel(header, text=APP_NAME, font=ctk.CTkFont(size=20, weight="bold")).grid(row=1, column=0)
        ctk.CTkButton(header, text="Open Data Folder", width=130, fg_color="gray30",
                      command=lambda: os.startfile(self.data_dir)).grid(row=0, column=0, sticky="ne", padx=10, pady=10)
        self.game_status_label = ctk.CTkLabel(
            header, text="GAME RUNNING - CONTROLS LOCKED", text_color="#E53935",
            font=ctk.CTkFont(weight="bold"))

    def _create_tabs(self):
        self.main_tabs = ctk.CTkTabview(self, anchor="w")
        self.main_tabs.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="nsew")
        save_tab = self.main_tabs.add("Save Management")
        mod_tab = self.main_tabs.add("Mod Management")
        for tab in (save_tab, mod_tab):
            tab.grid_columnconfigure(0, weight=1)
            tab.grid_rowconfigure(0, weight=1)
        self.save_master = save_tab
        self.save_tabs = None
        self.mods_tab = ModsTab(mod_tab, self, self.steam_icon)
        self.mods_tab.grid(row=0, column=0, sticky="nsew")
        self.mods_tab.refresh()

    # --- Game path ---

    def _startup(self):
        """Finds the game folder from the config, Steam, or by asking."""
        configured = self.config.game_path
        if configured and not validate_game_path(configured):
            self.set_game_path(configured)
            return
        if configured:
            show_message(self, "Path Invalid", "The saved game path is no longer valid.")
        found = find_game_install(self.steam_path)
        if found and not validate_game_path(found):
            self.set_game_path(found)
            return
        if not configured:
            show_message(self, "Game Not Found",
                         "Could not automatically detect the game directory. Please select it manually.")
        self.prompt_for_game_path()

    def prompt_for_game_path(self):
        """Asks the user to pick the game folder until a usable one is chosen."""
        while True:
            path = filedialog.askdirectory(title=f"Select '{GAME_FOLDER_NAME}' game folder", parent=self)
            if not path:
                if not self.game:
                    show_message(self, "Setup Required", "A valid game path is required to use the application.")
                    self._on_close()
                return
            errors = validate_game_path(path)
            if not errors or ask_yes_no(
                    self, "Validation Failed",
                    "The selected folder failed validation:\n\n- " + "\n- ".join(errors) +
                    "\n\nThis may not be the correct folder. Use it anyway?"):
                self.set_game_path(path)
                return

    def set_game_path(self, path):
        """Switches to a game folder and rebuilds everything that depends on it."""
        path = Path(path)
        self.config.game_path = str(path)
        self.config.save()
        state_dir = self.installs_root / path_key(path)
        self.game = GameInstall(path, state_dir)
        try:
            self.mod_manager = ModManager(path, self.installs_root)
        except ModError as e:
            log.exception("Could not load mods")
            self.mod_manager = None
            show_message(self, "Mod List Unreadable",
                         f"{e}\n\nMod management is disabled. See the data folder for the mods.json backup.")
        self._check_game_files()
        self.mods_tab.refresh()
        self.rebuild_save_tabs()

    def _check_game_files(self):
        """Repairs state that game updates or Steam's 'verify files' may have changed."""
        if is_game_running():
            return
        try:
            state = self.game.eac_state()
            if state is EacState.ON:
                self.game.refresh_eac_bypass()
            elif state is EacState.STALE:
                self.game.remove_eac_bypass()
                show_message(self, "EAC Bypass Turned Off",
                             "Steam has restored the original EAC launcher (probably after an update or "
                             "a file check), so the bypass is no longer active. Turn it back on in the "
                             "Mod Management tab if you need it.")
        except (GameError, OSError):
            log.exception("EAC check failed")
        if self.mod_manager:
            try:
                self.mod_manager.sync()
            except ModError:
                log.exception("Could not re-apply mods at startup")

    # --- Save profiles ---

    def _all_locations(self):
        return discover_save_locations(self.game.path if self.game else None, self.steam_path)

    def rebuild_save_tabs(self, keep=None):
        """Recreates one tab per save location that has saves or slots."""
        current = keep or (self.save_tabs.get() if self.save_tabs else None)
        if self.save_tabs is not None:
            self.save_tabs.destroy()
        for child in self.save_master.winfo_children():
            child.destroy()
        self.profile_tabs.clear()

        self.save_tabs = ctk.CTkTabview(self.save_master, anchor="w")
        self.save_tabs.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        for name, live_path in self._all_locations().items():
            try:
                profile = SaveProfile(name, live_path, self.profiles_root)
                if not profile.slots and not profile.has_live_save():
                    continue
                profile.initialize_from_live_save(random_slot_name())
            except (SaveError, OSError):
                log.exception("Could not open save profile %s", live_path)
                continue
            tab = self.save_tabs.add(name)
            tab.grid_columnconfigure(0, weight=1)
            tab.grid_rowconfigure(0, weight=1)
            icon = self.steam_icon if name.startswith("Steam") else None
            profile_tab = ProfileTab(tab, self, profile, icon)
            profile_tab.grid(row=0, column=0, sticky="nsew")
            profile_tab.set_locked(self.locked)
            self.profile_tabs[name] = profile_tab

        if not self.profile_tabs:
            self.save_tabs.destroy()
            self.save_tabs = None
            ctk.CTkLabel(self.save_master, text="No Fantasy Life i save profiles found.",
                         font=ctk.CTkFont(size=16)).grid(row=0, column=0)
        elif current in self.profile_tabs:
            self.save_tabs.set(current)

    def copy_destinations(self, source):
        """Returns {name: SaveProfile} for every other location a slot can be copied to."""
        destinations = {}
        for name, live_path in self._all_locations().items():
            if name == source.name or not live_path.parent.is_dir():
                continue
            existing = self.profile_tabs.get(name)
            destinations[name] = existing.profile if existing else SaveProfile(name, live_path, self.profiles_root)
        return destinations

    # --- Game running lock ---

    def _poll_game_state(self):
        if self.watcher.checked and self.watcher.running != self.locked:
            self._set_locked(self.watcher.running)
        self.after(500, self._poll_game_state)

    def _set_locked(self, locked):
        self.locked = locked
        if locked:
            self.game_status_label.grid(row=2, column=0, sticky="ew", pady=(5, 10))
        else:
            self.game_status_label.grid_forget()
        self.mods_tab.set_locked(locked)
        for tab in self.profile_tabs.values():
            if not locked:
                tab.on_game_stopped()
            tab.set_locked(locked)

    def ensure_game_closed(self, action):
        """Double-checks the game is closed right before a risky action."""
        if is_game_running():
            if not self.locked:
                self._set_locked(True)
            show_message(self, "Action Blocked", f"Close the game before you {action}.")
            return False
        return True

    # --- Errors and shutdown ---

    def _on_callback_error(self, exc_type, exc_value, exc_tb):
        log.error("Unhandled error", exc_info=(exc_type, exc_value, exc_tb))
        details = "".join(traceback.format_exception_only(exc_type, exc_value)).strip()
        try:
            show_message(self, "Unexpected Error",
                         f"Something went wrong:\n\n{details}\n\n"
                         f"Details were written to {self.data_dir / 'logs' / 'flisamm.log'}.")
        except Exception:
            log.exception("Could not show the error dialog")

    def _on_close(self):
        self.watcher.stop()
        self.destroy()
