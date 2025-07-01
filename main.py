"""
Main application file for the Fantasy Life i Mod Manager.

This file contains the main UI window and orchestrates the application's
behavior by delegating tasks to the backend managers.
"""

import json
import os
import random
import shutil
import zipfile

import tkinter
from datetime import datetime
from tkinter import filedialog

import customtkinter as ctk
import psutil
from PIL import Image

from managers import ModManager, PathManager, SaveProfileManager
from resources import (
    APP_DIMENSIONS,
    APP_NAME,
    APP_VERSION,
    CONFIG_FILE,
    FL_ADJECTIVES,
    FL_NOUNS,
)
from ui_components import CustomInputDialog, CustomMessageBox


class FLiModManager(ctk.CTk):
    """The main application window class."""

    def __init__(self):
        super().__init__()
        self.title(f'{"Save & Mod Manager"} v{APP_VERSION}')

        self.geometry(APP_DIMENSIONS)
        self.resizable(False, False)
        self.update_idletasks()  # Ensure dimensions are calculated
        window_width, window_height = [int(v) for v in APP_DIMENSIONS.split("x")]
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x_pos = (screen_width // 2) - (window_width // 2)
        y_pos = (screen_height // 2) - (window_height // 2)
        self.geometry(f"{APP_DIMENSIONS}+{x_pos}+{y_pos}")

        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")

        try:
            self.logo_image = ctk.CTkImage(
                light_image=Image.open("resources/logo.png"),
                dark_image=Image.open("resources/logo.png"),
                size=(242, 80),
            )
            self.steam_icon = ctk.CTkImage(
                light_image=Image.open("resources/steam.png"),
                dark_image=Image.open("resources/steam.png"),
                size=(24, 24),
            )
        except FileNotFoundError:
            self.logo_image, self.steam_icon = None, None
            print("Warning: Image resources not found in 'resources' folder.")

        self.config_data = self._load_config()
        self.launch_via_steam_enabled = self.config_data.get("launch_via_steam", True)

        self.path_manager = PathManager()
        self.mod_manager = ModManager(self.path_manager.game_path)
        self.profile_managers = {}
        self.tab_widgets = {}
        self.is_game_running = False
        self.process_check_iterator = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._create_header()
        self._create_main_tabs()

        self.after(250, self._first_launch_check)
        self.after(2000, self._check_game_process)

    def _create_header(self):
        """Creates the main application header and status bar."""
        header_frame = ctk.CTkFrame(self, corner_radius=0)
        header_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(0, 10))
        header_frame.grid_columnconfigure(0, weight=1)

        # Display the logo if it was loaded successfully
        if self.logo_image:
            logo_label = ctk.CTkLabel(header_frame, image=self.logo_image, text="")
            logo_label.grid(row=0, column=0, pady=(10, 0))

        ctk.CTkLabel(
            header_frame, text=APP_NAME, font=ctk.CTkFont(size=20, weight="bold")
        ).grid(row=1, column=0)

        self.game_status_label = ctk.CTkLabel(
            header_frame,
            text="GAME RUNNING - CONTROLS LOCKED",
            text_color="#E53935",
            font=ctk.CTkFont(weight="bold"),
        )

    def _create_main_tabs(self):
        """Creates the main tab view for Mod and Save Management."""
        self.main_tab_view = ctk.CTkTabview(self, anchor="w")
        self.main_tab_view.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="nsew")
        self.main_tab_view.add("Save Management")
        self.main_tab_view.add("Mod Management")

        # Create the content for both tabs
        self._create_mod_management_tab()
        self.save_master_tab = self.main_tab_view.tab("Save Management")
        self.save_master_tab.grid_columnconfigure(0, weight=1)
        self.save_master_tab.grid_rowconfigure(0, weight=1)
        self.save_tab_view = None

    def _create_mod_management_tab(self):
        """Creates the UI for the Mod Management tab, including utilities."""
        tab = self.main_tab_view.tab("Mod Management")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(2, weight=1)

        top_frame = ctk.CTkFrame(tab)
        top_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        top_frame.grid_columnconfigure(1, weight=1)
        self.mod_top_frame = top_frame

        ctk.CTkButton(
            top_frame, text="Change...", width=80, command=self._prompt_for_game_path
        ).grid(row=0, column=0, padx=(10, 5), pady=5)
        self.game_path_label = ctk.CTkLabel(
            top_frame,
            text="Game Path: Not Set",
            wraplength=600,
            justify="left",
            anchor="w",
        )
        self.game_path_label.grid(row=0, column=1, sticky="ew", padx=5, pady=5)
        self.install_mod_button = ctk.CTkButton(
            top_frame, text="Install Mod(s)...", command=self._select_mod_file
        )
        self.install_mod_button.grid(row=0, column=2, padx=(5, 10), pady=5)

        warning_frame = ctk.CTkFrame(
            tab, fg_color="#4A2B2B", border_width=1, border_color="#C75450"
        )
        warning_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 10))
        warning_frame.grid_columnconfigure(1, weight=1)
        info_icon = ctk.CTkLabel(warning_frame, text="⚠️", font=ctk.CTkFont(size=24))
        info_icon.grid(row=0, column=0, padx=15, pady=10, sticky="ns")
        warning_text = "Use mods at your own risk. There are no reported bans from modding so far, but we do not know how LEVEL-5 will handle this in the future."
        warning_label = ctk.CTkLabel(
            warning_frame, text=warning_text, wraplength=800, justify="left"
        )
        warning_label.grid(row=0, column=1, padx=(0, 15), pady=10, sticky="ew")

        self.mod_list_frame = ctk.CTkScrollableFrame(tab, label_text="Installed Mods")
        self.mod_list_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=0)
        self.mod_list_frame.grid_columnconfigure(0, weight=1)

        utils_frame = ctk.CTkFrame(tab)
        utils_frame.grid(row=3, column=0, sticky="ew", padx=10, pady=10)
        utils_frame.grid_columnconfigure(0, weight=1)
        self.utils_frame = utils_frame

        eac_label = ctk.CTkLabel(
            utils_frame,
            text="Easy Anti-Cheat Bypass",
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        eac_label.grid(row=0, column=0, columnspan=2, sticky="w", padx=10, pady=10)

        eac_desc_text = "Enable this to launch without EAC, which may be required for some mods. You will only be able to play online with other users who also have the bypass enabled."
        eac_desc = ctk.CTkLabel(
            utils_frame, justify="left", wraplength=800, text=eac_desc_text
        )
        eac_desc.grid(row=1, column=0, columnspan=2, sticky="w", padx=10, pady=(0, 10))

        initial_eac_state = "on" if self.path_manager.is_eac_bypassed() else "off"
        self.eac_switch_var = tkinter.StringVar(value=initial_eac_state)
        self.eac_switch = ctk.CTkSwitch(
            utils_frame,
            text="Bypass Enabled",
            variable=self.eac_switch_var,
            onvalue="on",
            offvalue="off",
            command=self._toggle_eac_bypass,
        )
        self.eac_switch.grid(row=2, column=0, sticky="w", padx=10, pady=10)

        launch_sub_frame = ctk.CTkFrame(utils_frame, fg_color="transparent")
        launch_sub_frame.grid(row=2, column=1, sticky="e", padx=10, pady=10)

        if self.steam_icon:
            ctk.CTkLabel(launch_sub_frame, image=self.steam_icon, text="").pack(
                side="left", padx=(0, 5)
            )

        initial_launch_state = "on" if self.launch_via_steam_enabled else "off"
        self.launch_steam_var = tkinter.StringVar(value=initial_launch_state)
        self.launch_steam_switch = ctk.CTkSwitch(
            launch_sub_frame,
            text="Launch via Steam",
            variable=self.launch_steam_var,
            onvalue="on",
            offvalue="off",
            command=self._on_launch_toggle_changed,
        )
        self.launch_steam_switch.pack(side="left", padx=10)
        self.launch_button = ctk.CTkButton(
            launch_sub_frame, text="Launch Game", command=self._launch_game
        )
        self.launch_button.pack(side="left")

    def _first_launch_check(self):
        """Handles the application's initial setup and path validation."""
        config_path = self.config_data.get("game_path")

        if config_path:
            is_valid, _ = PathManager.validate_game_path(config_path)
            if not is_valid:
                self._show_message(
                    "Path Invalid", "The saved game path is no longer valid."
                )
                self._prompt_for_game_path()
            else:
                self.path_manager.set_game_path(config_path)
                self._update_all_paths_and_ui()
        else:
            if self.path_manager.find_game_automatically():
                self._save_config()
                self._update_all_paths_and_ui()
            else:
                self._show_message(
                    "Game Not Found",
                    "Could not automatically detect the game directory. Please select it manually.",
                )
                self._prompt_for_game_path()

    def _prompt_for_game_path(self):
        """Opens a dialog to ask the user for the game path."""
        while True:
            path = filedialog.askdirectory(title="Select 'FANTASY LIFE i' game folder")
            if not path:
                if not self.path_manager.game_path:
                    self._show_message(
                        "Setup Required",
                        "A valid game path is required to use the application.",
                    )
                    self.quit()
                return

            is_valid, errors = PathManager.validate_game_path(path)
            if is_valid:
                self.path_manager.set_game_path(path)
                self._save_config()
                self._update_all_paths_and_ui()
                return
            else:
                errors_block = "\n- ".join(errors)
                error_str = (
                    f"The selected folder failed validation:\n\n- {errors_block}"
                )
                if self._ask_yes_no(
                    "Validation Failed",
                    f"{error_str}\n\nThis may not be the correct folder. Use it anyway?",
                ):
                    self.path_manager.set_game_path(path)
                    self._save_config()
                    self._update_all_paths_and_ui()
                    return

    def _load_config(self):
        """Loads the entire configuration dictionary from the JSON file."""
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except (IOError, json.JSONDecodeError):
            return {}

    def _save_config(self):
        """Saves the current application settings to the configuration file."""
        config_to_save = {
            "game_path": self.path_manager.game_path,
            "launch_via_steam": self.launch_steam_var.get() == "on",
            "eac_bypass_enabled": self.path_manager.is_eac_bypassed(),
        }
        with open(CONFIG_FILE, "w") as f:
            json.dump(config_to_save, f, indent=4)

    def _toggle_eac_bypass(self):
        """Handles the logic when the EAC bypass switch is toggled."""
        target_state = self.eac_switch_var.get()

        if target_state == "on":
            result = self.path_manager.apply_eac_bypass()
            if not result["success"]:
                self._show_message(
                    "Error", f"Failed to apply EAC bypass: {result['error']}"
                )
                self.eac_switch_var.set("off")
                return  # Do not save config on failure
        else:
            result = self.path_manager.remove_eac_bypass()
            if not result["success"]:
                self._show_message(
                    "Error", f"Failed to remove EAC bypass: {result['error']}"
                )
                self.eac_switch_var.set("on")
                return  # Do not save config on failure

        # The EAC state is not saved directly, but the bypass check will
        # correctly set the switch on next launch.
        self._save_config()

    def _on_launch_toggle_changed(self):
        """Saves the configuration when the launch method is changed."""
        self._save_config()

    def _launch_game(self):
        """Launches the game either via Steam or directly, based on the toggle."""
        if not self.path_manager.game_path:
            self._show_message("Error", "Game path is not set.")
            return

        if self.launch_steam_var.get() == "on":
            try:
                os.startfile("steam://run/2993780")
            except Exception as e:
                self._show_message("Error", f"Failed to launch game via Steam: {e}")
        else:
            eac_launcher_path = os.path.join(
                self.path_manager.game_path, "EACLauncher.exe"
            )
            if os.path.exists(eac_launcher_path):
                try:
                    os.startfile(eac_launcher_path)
                except Exception as e:
                    self._show_message("Error", f"Failed to launch game directly: {e}")
            else:
                self._show_message(
                    "Error", "EACLauncher.exe not found in the game directory."
                )

    def _update_all_paths_and_ui(self):
        """Updates all paths and rebuilds UI elements that depend on them."""
        self.game_path_label.configure(text=f"Game Path: {self.path_manager.game_path}")
        self.mod_manager = ModManager(self.path_manager.game_path)
        self._populate_mod_list()

        if hasattr(self, "eac_switch_var"):
            new_eac_state = "on" if self.path_manager.is_eac_bypassed() else "off"
            self.eac_switch_var.set(new_eac_state)

        self._rebuild_save_management_tabs()

    def _rebuild_save_management_tabs(self):
        """Rebuilds save management tabs, defaulting to the loaded slot."""
        if self.save_tab_view is not None:
            self.save_tab_view.destroy()

        self.profile_managers.clear()
        self.tab_widgets.clear()
        self.path_to_tab_name = {}

        self.save_tab_view = ctk.CTkTabview(
            self.save_master_tab, anchor="w", command=self._on_profile_tab_changed
        )
        self.save_tab_view.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        all_profiles = {}
        steam_profiles = self.path_manager.steam_user_profiles
        if len(steam_profiles) == 1:
            all_profiles["Steam"] = list(steam_profiles.values())[0]
        else:
            for sid, path in steam_profiles.items():
                all_profiles[f"Steam ({sid})"] = path
        all_profiles.update(self.path_manager.other_save_locations)

        for name, path in all_profiles.items():
            if not path or not os.path.isdir(os.path.dirname(path)):
                continue
            manager = SaveProfileManager(path)
            if not manager.metadata["slots"] and not manager.has_active_save_file():
                continue

            self.profile_managers[path] = manager
            self.path_to_tab_name[path] = name
            tab = self.save_tab_view.add(name)
            self._populate_save_profile_tab(tab, path)

        if self.save_tab_view.get():
            self._on_profile_tab_changed()
        else:
            ctk.CTkLabel(
                self.save_master_tab,
                text="No Fantasy Life i save profiles found.",
                font=ctk.CTkFont(size=16),
            ).place(relx=0.5, rely=0.5, anchor="center")

    def _populate_save_profile_tab(self, tab, profile_path):
        """Creates the permanent UI structure for a single save profile tab."""
        manager = self.profile_managers[profile_path]
        if manager.has_active_save_file() and not manager.metadata.get(
            "active_slot_uuid"
        ):
            manager.initialize_from_game_save(self._generate_random_name())

        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(1, weight=1)
        widgets = {
            "selected_slot_uuid": None,
            "selected_backup_uuid": None,
            "backup_sort_order": tkinter.StringVar(value="date_desc"),
            "backup_search_term": tkinter.StringVar(),
            "slot_buttons": {},
            "backup_entry_pool": [],
        }
        self.tab_widgets[profile_path] = widgets

        tab_name = self.path_to_tab_name.get(profile_path, "")
        title_frame = ctk.CTkFrame(tab, fg_color="transparent")
        title_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(5, 0))
        title_icon = None
        if "Steam" in tab_name and self.steam_icon:
            title_icon = self.steam_icon
        title_label = ctk.CTkLabel(
            title_frame,
            text=tab_name,
            font=ctk.CTkFont(size=14, weight="bold"),
            image=title_icon,
            compound="left",
            anchor="w",
        )
        title_label.pack(side="left", pady=5)

        main_content_frame = ctk.CTkFrame(tab, fg_color="transparent")
        main_content_frame.grid(row=1, column=0, sticky="nsew")
        main_content_frame.grid_columnconfigure(0, weight=1)
        main_content_frame.grid_columnconfigure(1, weight=3)
        main_content_frame.grid_rowconfigure(0, weight=1)

        left_panel = ctk.CTkFrame(main_content_frame)
        left_panel.grid(row=0, column=0, sticky="nsew", padx=(10, 2), pady=10)
        left_panel.grid_rowconfigure(0, weight=1)
        widgets["slot_list_frame"] = ctk.CTkScrollableFrame(
            left_panel, label_text="Save Slots"
        )
        widgets["slot_list_frame"].grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        widgets["load_slot_button"] = ctk.CTkButton(
            left_panel,
            text="Load Slot",
            state="disabled",
            fg_color="gray",
            command=lambda: self._load_active_save_for_slot(
                profile_path, widgets["selected_slot_uuid"]
            ),
        )
        widgets["load_slot_button"].grid(row=1, column=0, sticky="ew", padx=5, pady=5)
        slot_actions = ctk.CTkFrame(left_panel, fg_color="transparent")
        slot_actions.grid(row=2, column=0, sticky="ew", padx=5, pady=(5, 0))
        widgets["rename_slot_button"] = ctk.CTkButton(
            slot_actions,
            text="Rename Slot",
            state="disabled",
            fg_color="gray",
            command=lambda: self._rename_slot(profile_path),
        )
        widgets["rename_slot_button"].pack(fill="x", pady=(0, 5))
        widgets["copy_slot_button"] = ctk.CTkButton(
            slot_actions,
            text="Copy Slot to...",
            state="disabled",
            fg_color="gray",
            command=lambda: self._copy_slot(profile_path),
        )
        widgets["copy_slot_button"].pack(fill="x")
        ctk.CTkButton(
            left_panel,
            text="[ + ] Create New Empty Slot",
            command=lambda: self._create_new_slot(profile_path),
        ).grid(row=3, column=0, sticky="ew", padx=5, pady=5)
        details_panel = ctk.CTkFrame(main_content_frame, fg_color="gray14")
        details_panel.grid(row=0, column=1, sticky="nsew", padx=(2, 10), pady=10)
        widgets["details_panel"] = details_panel
        widgets["details_placeholder_frame"] = ctk.CTkFrame(
            details_panel, fg_color="transparent"
        )
        ctk.CTkLabel(
            widgets["details_placeholder_frame"],
            text="Select a slot or create one.",
            wraplength=300,
        ).pack(expand=True, padx=20)
        content = ctk.CTkFrame(details_panel, fg_color="transparent")
        content.grid_columnconfigure(0, weight=1)
        content.grid_rowconfigure(2, weight=1)
        widgets["details_content_frame"] = content
        active_save_frame = ctk.CTkFrame(content, border_width=2, border_color="gray24")
        active_save_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        active_save_frame.grid_columnconfigure(0, weight=1)
        widgets["active_save_frame"] = active_save_frame
        widgets["active_save_label"] = ctk.CTkLabel(
            active_save_frame, text="No active save for this slot.", anchor="w"
        )
        widgets["active_save_label"].grid(row=0, column=0, sticky="ew", padx=10, pady=5)

        controls_frame = ctk.CTkFrame(content)
        controls_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 10))
        search = ctk.CTkEntry(
            controls_frame,
            placeholder_text="Search manual backups...",
            textvariable=widgets["backup_search_term"],
        )
        search.pack(side="left", padx=(0, 10), expand=True, fill="x")
        search.bind(
            "<KeyRelease>", lambda e: self._refresh_backup_display(profile_path)
        )
        ctk.CTkOptionMenu(
            controls_frame,
            variable=widgets["backup_sort_order"],
            values=["date_desc", "date_asc", "name_asc"],
            command=lambda e: self._refresh_backup_display(profile_path),
        ).pack(side="left")

        widgets["backups_list_frame"] = ctk.CTkScrollableFrame(
            content, label_text="Manual Backups"
        )
        widgets["backups_list_frame"].grid(
            row=2, column=0, sticky="nsew", padx=10, pady=0
        )

        for _ in range(30):
            entry = ctk.CTkFrame(widgets["backups_list_frame"], fg_color="transparent")
            entry.columnconfigure(0, weight=1)
            name_btn = ctk.CTkButton(entry, text="", fg_color="transparent", anchor="w")
            name_btn.grid(row=0, column=0, sticky="ew")
            load_btn = ctk.CTkButton(entry, text="Load", width=60)
            load_btn.grid(row=0, column=1, padx=5)
            widgets["backup_entry_pool"].append(
                {"frame": entry, "name_btn": name_btn, "load_btn": load_btn}
            )
            entry.pack_forget()

        backup_actions = ctk.CTkFrame(content)
        backup_actions.grid(row=3, column=0, sticky="ew", padx=10, pady=10)
        widgets["rename_backup_button"] = ctk.CTkButton(
            backup_actions,
            text="Rename Backup",
            state="disabled",
            fg_color="gray",
            command=lambda: self._rename_backup(profile_path),
        )
        widgets["rename_backup_button"].pack(side="left", padx=5)
        widgets["delete_backup_button"] = ctk.CTkButton(
            backup_actions,
            text="Delete Backup",
            state="disabled",
            fg_color="#D32F2F",
            hover_color="#B71C1C",
            command=lambda: self._delete_backup(profile_path),
        )
        widgets["delete_backup_button"].pack(side="left", padx=5)
        widgets["create_backup_button"] = ctk.CTkButton(
            backup_actions,
            text="Create New Backup",
            state="disabled",
            fg_color="gray",
            command=lambda: self._create_new_backup(profile_path),
        )
        widgets["create_backup_button"].pack(side="right", padx=5)

    def _on_profile_tab_changed(self):
        """Handles the event when a user clicks a new profile tab."""
        tab_name = self.save_tab_view.get()
        if not tab_name:
            return
        profile_path = next(
            (p for p, n in self.path_to_tab_name.items() if n == tab_name), None
        )
        if not profile_path:
            return

        manager = self.profile_managers[profile_path]
        widgets = self.tab_widgets[profile_path]
        if widgets["selected_slot_uuid"]:
            return

        default_slot = None
        if manager.has_active_save_file() and manager.metadata.get("active_slot_uuid"):
            default_slot = manager.metadata["active_slot_uuid"]
        elif manager.metadata["slots"]:
            default_slot = list(manager.metadata["slots"].keys())[0]

        if default_slot:
            self._on_slot_selected(profile_path, default_slot)
        else:
            self._refresh_slot_list(profile_path)
            self._populate_details_panel(profile_path)

    def _on_slot_selected(self, profile_path, slot_uuid):
        """Handles UI updates when a save slot is selected."""
        widgets = self.tab_widgets.get(profile_path)
        manager = self.profile_managers.get(profile_path)
        if not widgets or not manager:
            return

        widgets["selected_slot_uuid"] = slot_uuid
        widgets["selected_backup_uuid"] = None
        game_locked = self.is_game_running

        widgets["rename_slot_button"].configure(state="normal")
        widgets["load_slot_button"].configure(
            state="disabled" if game_locked else "normal"
        )
        can_copy = any(p != profile_path for p in self.profile_managers.keys())
        widgets["copy_slot_button"].configure(
            state="disabled" if game_locked or not can_copy else "normal"
        )

        is_loaded = (
            slot_uuid == manager.metadata.get("active_slot_uuid")
        ) and manager.has_active_save_file()
        can_backup = is_loaded and not game_locked
        btn_color = ctk.ThemeManager.theme["CTkButton"]["fg_color"]
        widgets["create_backup_button"].configure(
            state="normal" if can_backup else "disabled",
            fg_color=btn_color if can_backup else "gray",
        )
        widgets["rename_backup_button"].configure(state="disabled")
        widgets["delete_backup_button"].configure(state="disabled")

        self._refresh_slot_list(profile_path)
        self._populate_details_panel(profile_path)
        for p_path in self.profile_managers:
            if p_path != profile_path:
                self._refresh_slot_list(p_path)

    def _refresh_slot_list(self, profile_path):
        """Redraws the list of save slots for a given profile."""
        widgets = self.tab_widgets[profile_path]
        manager = self.profile_managers[profile_path]
        for widget in widgets["slot_list_frame"].winfo_children():
            widget.destroy()
        widgets["slot_buttons"].clear()

        active_slot = manager.metadata.get("active_slot_uuid")
        is_loaded = active_slot and manager.has_active_save_file()
        sorted_slots = sorted(
            manager.metadata.get("slots", {}).items(),
            key=lambda item: (
                item[0] != active_slot if is_loaded else True,
                item[1].get("name", "").lower(),
            ),
        )
        for uuid, data in sorted_slots:
            name = data.get("name", "Unnamed")
            if is_loaded and uuid == active_slot:
                name = f"{name} [LOADED]"
            btn = ctk.CTkButton(
                widgets["slot_list_frame"],
                text=name,
                command=lambda u=uuid: self._on_slot_selected(profile_path, u),
            )
            btn.pack(fill="x", pady=2, padx=2)
            widgets["slot_buttons"][uuid] = btn

            is_selected = uuid == widgets["selected_slot_uuid"]
            fg_color = (
                "#1F6AA5"
                if is_selected
                else ("#0E496D" if is_loaded and uuid == active_slot else "gray30")
            )
            btn.configure(fg_color=fg_color)
            btn.bind(
                "<Button-3>",
                lambda e, u=uuid, n=data.get("name"): self._show_slot_context_menu(
                    e, profile_path, u, n
                ),
            )

    def _show_slot_context_menu(self, event, profile_path, slot_uuid, name):
        """Displays the right-click context menu for a save slot."""
        menu = tkinter.Menu(self, tearoff=0)
        menu.add_command(
            label=f"Delete '{name}'",
            command=lambda: self._delete_slot(profile_path, slot_uuid),
        )
        menu.post(event.x_root, event.y_root)

    def _populate_details_panel(self, profile_path):
        """Populates the right-hand details panel based on the selected slot."""
        widgets = self.tab_widgets.get(profile_path)
        manager = self.profile_managers.get(profile_path)
        if not widgets or not manager:
            return

        selected_uuid = widgets.get("selected_slot_uuid")
        if selected_uuid and selected_uuid in manager.metadata["slots"]:
            widgets["details_placeholder_frame"].pack_forget()
            widgets["details_content_frame"].pack(expand=True, fill="both")
            slot_data = manager.metadata["slots"][selected_uuid]
            active_ts = slot_data.get("active_save_timestamp")
            is_loaded = (
                manager.metadata.get("active_slot_uuid") == selected_uuid
                and manager.has_active_save_file()
            )
            widgets["active_save_frame"].configure(
                border_color="#1F6AA5" if is_loaded else "gray24"
            )
            if active_ts:
                ts_str = datetime.fromtimestamp(active_ts).strftime("%Y-%m-%d %H:%M:%S")
                widgets["active_save_label"].configure(
                    text=f"{'[LOADED] ' if is_loaded else ''}Last Played: {ts_str}"
                )
            else:
                widgets["active_save_label"].configure(
                    text="No active save for this slot."
                )
            self._refresh_backup_display(profile_path)
        else:
            widgets["details_content_frame"].pack_forget()
            widgets["details_placeholder_frame"].pack(expand=True, fill="both")

    def _refresh_backup_display(self, profile_path):
        """Efficiently updates the list of manual backups using a widget pool."""
        widgets = self.tab_widgets[profile_path]
        manager = self.profile_managers[profile_path]
        slot_uuid = widgets["selected_slot_uuid"]
        slot_data = manager.metadata["slots"].get(slot_uuid, {})
        backups = list(slot_data.get("backups", {}).items())

        search_term = widgets["backup_search_term"].get().lower()
        if search_term:
            backups = [
                b for b in backups if search_term in b[1].get("name", "").lower()
            ]
        sort_key = widgets["backup_sort_order"].get()
        if sort_key == "date_desc":
            backups.sort(key=lambda i: i[1]["timestamp"], reverse=True)
        elif sort_key == "date_asc":
            backups.sort(key=lambda i: i[1]["timestamp"])
        elif sort_key == "name_asc":
            backups.sort(key=lambda i: i[1].get("name", ""))
        is_parent_slot_loaded = slot_uuid == manager.metadata.get("active_slot_uuid")

        for i, (backup_uuid, backup_data) in enumerate(backups):
            if i >= len(widgets["backup_entry_pool"]):
                break
            entry = widgets["backup_entry_pool"][i]
            is_selected = backup_uuid == widgets["selected_backup_uuid"]
            ts_str = datetime.fromtimestamp(backup_data["timestamp"]).strftime(
                "%Y-%m-%d %H:%M"
            )
            label_text = f"{backup_data.get('name')}  ({ts_str})"
            entry["name_btn"].configure(
                text=label_text,
                fg_color="gray20" if is_selected else "transparent",
                command=lambda b=backup_uuid: self._on_backup_selected(profile_path, b),
            )

            # Disable loading if game is running OR if the backup is not in the active slot
            can_load = not self.is_game_running and is_parent_slot_loaded
            entry["load_btn"].configure(
                state="normal" if can_load else "disabled",
                command=lambda s=slot_uuid, b=backup_uuid: self._activate_backup(
                    profile_path, s, b
                ),
            )
            entry["frame"].pack(fill="x", pady=2)

        for i in range(len(backups), len(widgets["backup_entry_pool"])):
            widgets["backup_entry_pool"][i]["frame"].pack_forget()

    def _on_backup_selected(self, profile_path, backup_uuid):
        """Handles UI updates when a manual backup is selected."""
        widgets = self.tab_widgets.get(profile_path)
        if not widgets:
            return
        widgets["selected_backup_uuid"] = backup_uuid
        widgets["rename_backup_button"].configure(state="normal")
        widgets["delete_backup_button"].configure(state="normal")
        self._refresh_backup_display(profile_path)

    def _check_game_process(self):
        """Cooperatively checks if the game process is running."""
        if self.process_check_iterator is None:
            self.process_check_iterator = psutil.process_iter(["name"])
            self.game_was_found_in_scan = False
        try:
            for _ in range(20):
                p = next(self.process_check_iterator)
                if p.info["name"] == "NFL1-Win64-Shipping.exe":
                    self.game_was_found_in_scan = True
                    raise StopIteration
            self.after(10, self._check_game_process)
        except StopIteration:
            self.process_check_iterator = None
            if self.game_was_found_in_scan != self.is_game_running:
                self.is_game_running = self.game_was_found_in_scan
                self._update_ui_for_game_state(locked=self.is_game_running)
            self.after(2000, self._check_game_process)

    def _update_ui_for_game_state(self, locked):
        """Enables or disables all sensitive UI controls based on game state."""
        if locked:
            self.game_status_label.grid(row=2, column=0, sticky="ew", pady=(5, 10))
        else:
            self.game_status_label.grid_forget()

        # Update Mod Management controls
        self._populate_mod_list()
        if hasattr(self, "install_mod_button"):
            self.install_mod_button.configure(state="disabled" if locked else "normal")
        if hasattr(self, "eac_switch"):
            self.eac_switch.configure(state="disabled" if locked else "normal")

        # Update Save Management controls
        if self.save_tab_view and self.save_tab_view.get():
            current_tab = self.save_tab_view.get()
            profile_path = next(
                (p for p, n in self.path_to_tab_name.items() if n == current_tab), None
            )
            if profile_path and profile_path in self.tab_widgets:
                selected_uuid = self.tab_widgets[profile_path]["selected_slot_uuid"]
                if selected_uuid:
                    self._on_slot_selected(profile_path, selected_uuid)

    def _select_mod_file(self):
        """Orchestrates the mod installation process."""
        if not self.path_manager.game_path:
            self._show_message("Error", "The game path has not been set.")
            return

        filepaths = filedialog.askopenfilenames(
            title="Select Mod Zip File(s)", filetypes=[("Zip Archives", "*.zip")]
        )
        if not filepaths:
            return

        for zip_path in filepaths:
            mod_name = os.path.splitext(os.path.basename(zip_path))[0]
            problem_paths = self.mod_manager.pre_install_check(zip_path)
            if problem_paths:
                path_list = "\n - ".join(problem_paths[:5])
                msg = f"The mod '{mod_name}' contains files with destination directories that do not exist:\n\n - {path_list}\n\nThis could be an error in packaging. Install anyway?"
                if not self._ask_yes_no("Installation Warning", msg):
                    continue
            result = self.mod_manager.install_mod(zip_path)
            if not result["success"]:
                self._show_message(
                    "Installation Failed",
                    result.get("error", "An unknown error occurred."),
                )
        self._populate_mod_list()

    def _populate_mod_list(self):
        """Clears and rebuilds the list of mods in the UI."""
        for widget in self.mod_list_frame.winfo_children():
            widget.destroy()
        if not self.mod_manager:
            return

        mods = self.mod_manager.get_mods()
        if not mods:
            ctk.CTkLabel(self.mod_list_frame, text="No mods installed.").pack(pady=20)
            return

        for i, mod_info in enumerate(mods):
            mod_name, mod_status = mod_info["name"], mod_info["status"]

            row_color = "gray22" if i % 2 == 0 else "gray17"
            row_frame = ctk.CTkFrame(self.mod_list_frame, fg_color=row_color)
            row_frame.pack(fill="x", padx=5, pady=2)
            row_frame.grid_columnconfigure(1, weight=1)

            switch_var = tkinter.StringVar(
                value="on" if mod_status == "enabled" else "off"
            )
            switch = ctk.CTkSwitch(
                row_frame,
                text="",
                variable=switch_var,
                onvalue="on",
                offvalue="off",
                command=lambda n=mod_name: (
                    self.mod_manager.toggle_mod_status(n),
                    self._populate_mod_list(),
                ),
                state="disabled" if self.is_game_running else "normal",
            )
            switch.grid(row=0, column=0, padx=10, pady=10)
            ctk.CTkLabel(row_frame, text=mod_name, anchor="w").grid(
                row=0, column=1, sticky="ew", padx=10
            )
            delete_btn = ctk.CTkButton(
                row_frame,
                text="Delete",
                fg_color="#D32F2F",
                hover_color="#B71C1C",
                width=80,
                command=lambda n=mod_name: self._delete_mod(n),
                state="disabled" if self.is_game_running else "normal",
            )
            delete_btn.grid(row=0, column=2, padx=10)

    def _delete_mod(self, mod_name):
        """Handles the user action to delete a mod."""
        if self._ask_yes_no(
            "Confirm Deletion",
            f"Permanently delete the mod '{mod_name}' and all its files?",
        ):
            self.mod_manager.delete_mod(mod_name)
            self._populate_mod_list()

    def _generate_random_name(self):
        """Generates a random name from the resource lists."""
        return f"{random.choice(FL_ADJECTIVES)} {random.choice(FL_NOUNS)}"

    def _show_message(self, title, message, buttons=("OK",)):
        """Shows a custom message box."""
        dialog = CustomMessageBox(self, title=title, message=message, buttons=buttons)
        return dialog.get()

    def _ask_yes_no(self, title, message):
        """Shows a custom Yes/No dialog and returns True for 'Yes'."""
        result = self._show_message(title, message, buttons=("Yes", "No"))
        return result == "Yes"

    def _load_active_save_for_slot(self, profile_path, slot_uuid):
        """
        Orchestrates loading a slot's Active Save. Handles both existing saves
        and preparing a new, empty slot for a fresh game save.
        """
        if self.is_game_running:
            self._show_message(
                "Action Blocked",
                "Cannot load a different save slot while the game is running.",
            )
            return

        if not slot_uuid:
            return
        dest_manager = self.profile_managers[profile_path]

        # Save the state of the currently active slot *within this profile* before doing anything else.
        current_active_slot = dest_manager.metadata.get("active_slot_uuid")
        if (
            current_active_slot
            and current_active_slot != slot_uuid
            and dest_manager.has_active_save_file()
        ):
            dest_manager.save_active_game_state(current_active_slot)

        active_save_zip = os.path.join(
            dest_manager.slots_path, slot_uuid, "active_save.zip"
        )

        if not os.path.exists(active_save_zip):
            # This is a new/empty slot. Prepare it for a fresh game start.
            # 1. Clear any existing live save file in this profile's directory.
            for item in os.listdir(dest_manager.path):
                if item.endswith("gamedata.bin") or item.endswith(".binbak"):
                    os.remove(os.path.join(dest_manager.path, item))

            # 2. Set this empty slot as the active one in the metadata.
            dest_manager.metadata["active_slot_uuid"] = slot_uuid

            # 3. Ensure no old timestamp exists, so the UI shows "No active save".
            if "active_save_timestamp" in dest_manager.metadata["slots"][slot_uuid]:
                del dest_manager.metadata["slots"][slot_uuid]["active_save_timestamp"]

            dest_manager._save_metadata()

            # 4. Inform the user of the next step.
            self._show_message(
                "New Save Slot Loaded",
                "The save directory has been cleared. Launch the game to create a new save file for this slot.",
            )

        else:
            # This is a normal load for a slot that already has a save.
            dest_manager.load_active_save_for_slot(slot_uuid)

        # Finally, refresh the UI to show the new state.
        self._on_slot_selected(profile_path, slot_uuid)

    def _activate_backup(self, profile_path, slot_uuid, backup_uuid):
        """Orchestrates loading a manual backup within a single profile."""
        if self.is_game_running:
            self._show_message(
                "Action Blocked", "Cannot load a backup while the game is running."
            )
            return

        dest_manager = self.profile_managers[profile_path]

        # Check if there is a currently active slot *in this profile* to back up.
        current_active_slot = dest_manager.metadata.get("active_slot_uuid")
        if current_active_slot and dest_manager.has_active_save_file():
            slot_name = dest_manager.metadata["slots"][current_active_slot].get(
                "name", "Unknown"
            )
            prompt = f"You are about to load a backup, which will overwrite the currently loaded slot '{slot_name}'.\n\nBackup current progress for '{slot_name}' first?"
            if self._ask_yes_no("Backup Current Save?", prompt):
                auto_name = (
                    f"Auto-Backup {datetime.now().strftime('%Y-%m-%d %H.%M.%S')}"
                )
                dest_manager.create_new_backup(current_active_slot, auto_name)

        # Directly extract the backup to the destination, overwriting any existing live file.
        backup_zip_path = os.path.join(
            dest_manager.slots_path, slot_uuid, f"{backup_uuid}.zip"
        )
        with zipfile.ZipFile(backup_zip_path, "r") as zf:
            zf.extractall(dest_manager.path)

        # Set this slot as the active one for THIS profile
        dest_manager.metadata["active_slot_uuid"] = slot_uuid
        dest_manager._save_metadata()

        # Immediately save the state of the just-restored backup as the new "Active Save"
        dest_manager.save_active_game_state(slot_uuid)

        # Trigger a full UI refresh
        self._on_slot_selected(profile_path, slot_uuid)

    def _create_new_slot(self, profile_path):
        """Handles the user action to create a new, empty save slot."""
        manager = self.profile_managers[profile_path]
        dialog = CustomInputDialog(
            self,
            title="Create New Empty Slot",
            prompt="Enter a name for the new slot:",
            initial_value=self._generate_random_name(),
            random_name_func=self._generate_random_name,
        )
        name = dialog.get_input()
        if name and name.strip():
            new_uuid = os.urandom(8).hex()
            # A new slot has no active save and thus no timestamp yet.
            manager.metadata["slots"][new_uuid] = {
                "name": name.strip(),
                "backup_counter": 1,
                "backups": {},
            }
            manager._save_metadata()
            self._refresh_slot_list(profile_path)

    def _rename_slot(self, profile_path):
        """Handles the user action to rename a save slot."""
        widgets = self.tab_widgets[profile_path]
        manager = self.profile_managers[profile_path]
        slot_uuid = widgets["selected_slot_uuid"]
        if not slot_uuid:
            return

        current_name = manager.metadata["slots"][slot_uuid].get("name", "")
        dialog = CustomInputDialog(
            self,
            title="Rename Slot",
            prompt="Enter new name:",
            initial_value=current_name,
            random_name_func=self._generate_random_name,
        )
        new_name = dialog.get_input()
        if new_name and new_name.strip():
            manager.metadata["slots"][slot_uuid]["name"] = new_name.strip()
            manager._save_metadata()
            self._refresh_slot_list(profile_path)

    def _delete_slot(self, profile_path, slot_uuid):
        """Handles the user action to delete a save slot."""
        manager = self.profile_managers[profile_path]
        slot_name = manager.metadata["slots"][slot_uuid].get("name")
        if not self._ask_yes_no(
            "Confirm Deletion",
            f"Permanently delete slot '{slot_name}' and ALL its data?",
        ):
            return

        is_loaded = manager.metadata.get("active_slot_uuid") == slot_uuid
        if is_loaded and self.is_game_running:
            self._show_message(
                "Action Blocked",
                "Cannot delete the loaded slot while the game is running.",
            )
            return

        if is_loaded:
            profile_name = self.path_to_tab_name.get(profile_path, "this profile")
            warn_msg = f"This is the loaded slot for the '{profile_name}' profile. Deleting it will clear the active save files for this profile only, leaving it with no loaded save.\n\nThis will not affect other profiles. Continue?"
            if not self._ask_yes_no("Warning!", warn_msg):
                return
            manager.metadata["active_slot_uuid"] = None
            for item in os.listdir(manager.path):
                if item.endswith("gamedata.bin") or item.endswith(".binbak"):
                    os.remove(os.path.join(manager.path, item))

        slot_dir = os.path.join(manager.slots_path, slot_uuid)
        if os.path.isdir(slot_dir):
            shutil.rmtree(slot_dir)
        del manager.metadata["slots"][slot_uuid]
        manager._save_metadata()

        self.tab_widgets[profile_path]["selected_slot_uuid"] = None
        self._on_profile_tab_changed()

    def _create_new_backup(self, profile_path):
        """Handles the user action to create a new manual backup."""
        manager = self.profile_managers.get(profile_path)
        if not manager:
            return
        slot_uuid = self.tab_widgets[profile_path]["selected_slot_uuid"]
        if not slot_uuid:
            return
        counter = manager.metadata["slots"][slot_uuid].get("backup_counter", 1)
        auto_name = f"Backup - {counter:04d}"
        if manager.create_new_backup(slot_uuid, auto_name):
            self._refresh_backup_display(profile_path)
        else:
            self._show_message(
                "Error",
                "Could not create backup. Is a save currently loaded in this slot?",
            )

    def _rename_backup(self, profile_path):
        """Handles the user action to rename a manual backup."""
        widgets = self.tab_widgets[profile_path]
        manager = self.profile_managers[profile_path]
        slot_uuid = widgets["selected_slot_uuid"]
        backup_uuid = widgets["selected_backup_uuid"]
        if not slot_uuid or not backup_uuid:
            return

        current_name = manager.metadata["slots"][slot_uuid]["backups"][backup_uuid].get(
            "name", ""
        )
        dialog = CustomInputDialog(
            self,
            title="Rename Backup",
            prompt="Enter new name:",
            initial_value=current_name,
        )
        new_name = dialog.get_input()
        if new_name and new_name.strip():
            manager.metadata["slots"][slot_uuid]["backups"][backup_uuid][
                "name"
            ] = new_name.strip()
            manager._save_metadata()
            self._refresh_backup_display(profile_path)
        elif new_name is not None:
            self._show_message("Invalid Name", "The backup name cannot be empty.")

    def _delete_backup(self, profile_path):
        """Handles the user action to delete a manual backup."""
        widgets = self.tab_widgets[profile_path]
        manager = self.profile_managers[profile_path]
        slot_uuid = widgets["selected_slot_uuid"]
        backup_uuid = widgets["selected_backup_uuid"]
        if not slot_uuid or not backup_uuid:
            return

        backup_name = manager.metadata["slots"][slot_uuid]["backups"][backup_uuid].get(
            "name", "this backup"
        )
        if self._ask_yes_no(
            "Confirm Deletion", f"Permanently delete the manual backup '{backup_name}'?"
        ):
            backup_zip = os.path.join(
                manager.slots_path, slot_uuid, f"{backup_uuid}.zip"
            )
            if os.path.exists(backup_zip):
                os.remove(backup_zip)
            del manager.metadata["slots"][slot_uuid]["backups"][backup_uuid]
            manager._save_metadata()
            widgets["selected_backup_uuid"] = None
            self._refresh_backup_display(profile_path)

    def _copy_slot(self, source_path):
        """Orchestrates copying a save slot to another profile."""
        source_manager = self.profile_managers.get(source_path)
        slot_uuid = self.tab_widgets[source_path]["selected_slot_uuid"]
        if not source_manager or not slot_uuid:
            return

        destination_options = {}
        steam_profiles = self.path_manager.steam_user_profiles
        if len(steam_profiles) == 1:
            path = list(steam_profiles.values())[0]
            if path != source_path and os.path.isdir(os.path.dirname(path)):
                destination_options["Steam"] = path
        else:
            for sid, path in steam_profiles.items():
                if path != source_path and os.path.isdir(os.path.dirname(path)):
                    destination_options[f"Steam ({sid})"] = path
        for name, path in self.path_manager.other_save_locations.items():
            if path and path != source_path and os.path.isdir(os.path.dirname(path)):
                destination_options[name] = path

        if not destination_options:
            self._show_message(
                "Copy Not Possible", "No other save profiles could be found to copy to."
            )
            return

        dialog = ctk.CTkToplevel(self)
        dialog.transient(self)
        dialog.title("Copy Slot to...")
        dialog.geometry("400x150")
        dialog.resizable(False, False)
        dialog.grab_set()

        ctk.CTkLabel(dialog, text="Select destination profile:").pack(
            pady=(10, 5), padx=10
        )
        dest_var = tkinter.StringVar(value=list(destination_options.keys())[0])
        ctk.CTkOptionMenu(
            dialog,
            variable=dest_var,
            width=380,
            values=list(destination_options.keys()),
        ).pack(pady=5, padx=10, fill="x")
        user_choice = None

        def ok():
            nonlocal user_choice
            user_choice = dest_var.get()
            dialog.destroy()

        def cancel():
            dialog.destroy()

        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(pady=20, padx=10)
        ctk.CTkButton(btn_frame, text="OK", command=ok, width=100).pack(
            side="left", padx=10
        )
        ctk.CTkButton(btn_frame, text="Cancel", command=cancel, width=100).pack(
            side="left", padx=10
        )
        dialog.protocol("WM_DELETE_WINDOW", cancel)
        self.wait_window(dialog)
        if not user_choice:
            return

        destination_path = destination_options[user_choice]
        dest_manager = self.profile_managers.get(
            destination_path, SaveProfileManager(destination_path)
        )

        if slot_uuid in dest_manager.metadata["slots"]:
            existing_name = dest_manager.metadata["slots"][slot_uuid].get(
                "name", "Unknown"
            )
            prompt = f"Slot '{existing_name}' already exists in '{user_choice}'.\n\nReplace it?"
            if not self._ask_yes_no("Confirm Replacement", prompt):
                return
        try:
            source_manager.copy_slot_to(dest_manager, slot_uuid)
            self._rebuild_save_management_tabs()
            self._show_message("Success", "Slot copied successfully.")
        except Exception as e:
            self._show_message("Copy Failed", f"An error occurred: {e}")
            self._rebuild_save_management_tabs()


if __name__ == "__main__":
    app = FLiModManager()
    app.mainloop()
