"""
Contains the backend manager classes that handle all non-UI logic, such as
file system operations, data management, and path discovery.
"""

import os
import json
import winreg
import zipfile
import shutil
from datetime import datetime


class PathManager:
    """Handles discovery, validation, and utility functions for game paths."""

    EAC_BACKUP_NAME = "EACLauncher.exe.bak"

    def __init__(self, game_path=""):
        self.game_path = game_path
        self.steam_user_profiles = {}
        self.other_save_locations = {}
        self.define_save_locations()

    def set_game_path(self, path):
        """Sets the game path and re-discovers save locations."""
        self.game_path = path
        self.define_save_locations()

    def is_eac_bypassed(self):
        """Checks if the EAC bypass is currently active."""
        if not self.game_path:
            return False
        return os.path.exists(os.path.join(self.game_path, self.EAC_BACKUP_NAME))

    def apply_eac_bypass(self):
        """Applies the EAC bypass by renaming and copying executables."""
        if not self.game_path or self.is_eac_bypassed():
            return {"success": True}

        eac_original = os.path.join(self.game_path, "EACLauncher.exe")
        eac_backup = os.path.join(self.game_path, self.EAC_BACKUP_NAME)
        game_exe = os.path.join(self.game_path, "NFL1.exe")

        if not os.path.exists(eac_original) or not os.path.exists(game_exe):
            return {"success": False, "error": "Required executables not found."}

        try:
            shutil.move(eac_original, eac_backup)
            shutil.copy(game_exe, eac_original)
            return {"success": True}
        except Exception as e:
            if os.path.exists(eac_backup):
                shutil.move(eac_backup, eac_original)
            return {"success": False, "error": f"An error occurred: {e}"}

    def remove_eac_bypass(self):
        """Removes the EAC bypass by restoring the original launcher."""
        if not self.game_path or not self.is_eac_bypassed():
            return {"success": True}

        eac_original = os.path.join(self.game_path, "EACLauncher.exe")
        eac_backup = os.path.join(self.game_path, self.EAC_BACKUP_NAME)

        try:
            os.remove(eac_original)
            shutil.move(eac_backup, eac_original)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": f"An error occurred: {e}"}

    @staticmethod
    def validate_game_path(path_to_check):
        """Checks if a given path is a valid game directory."""
        if not path_to_check or not os.path.isdir(path_to_check):
            return False, ["Path does not exist."]
        errors = []
        if os.path.basename(os.path.normpath(path_to_check)) != "FANTASY LIFE i":
            errors.append("Folder not named 'FANTASY LIFE i'.")
        if not os.path.exists(os.path.join(path_to_check, "EACLauncher.exe")):
            errors.append("Missing 'EACLauncher.exe'.")
        if not os.path.exists(os.path.join(path_to_check, "NFL1.exe")):
            errors.append("Missing 'NFL1.exe'.")
        if not os.path.exists(
            os.path.join(path_to_check, "Game/Binaries/Win64/NFL1-Win64-Shipping.exe")
        ):
            errors.append("Missing shipping executable.")
        return not errors, errors

    def find_game_automatically(self):
        """Tries to find the game directory via the Steam registry."""
        try:
            hkey = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam"
            )
            steam_path = winreg.QueryValueEx(hkey, "InstallPath")[0]
            winreg.CloseKey(hkey)
            potential_path = os.path.join(
                steam_path, "steamapps", "common", "FANTASY LIFE i"
            )
            is_valid, _ = self.validate_game_path(potential_path)
            if is_valid:
                self.set_game_path(potential_path)
                return True
        except Exception:
            pass
        return False

    def define_save_locations(self):
        """Discovers and defines all potential save file locations."""
        self.steam_user_profiles = {}
        self.other_save_locations = {}
        appdata = os.getenv("APPDATA")
        public_docs = os.path.expandvars("%PUBLIC%\\Documents")
        tenoke_path = (
            os.path.join(self.game_path, "Game/Binaries/Win64/SteamData")
            if self.game_path
            else ""
        )

        try:
            hkey = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam"
            )
            steam_path = winreg.QueryValueEx(hkey, "InstallPath")[0]
            winreg.CloseKey(hkey)
            userdata_path = os.path.join(steam_path, "userdata")
            if os.path.isdir(userdata_path):
                for steam_id in os.listdir(userdata_path):
                    if steam_id.isdigit():
                        steam_save_path = os.path.join(
                            userdata_path, steam_id, "2993780", "remote"
                        )
                        self.steam_user_profiles[steam_id] = steam_save_path
        except Exception:
            pass

        self.other_save_locations = {
            "Online-Fix": os.path.join(public_docs, "OnlineFix", "2993780", "Saves"),
            "GBE_Fork": os.path.join(appdata, "GSE Saves", "2993780", "remote"),
            "Goldberg": os.path.join(
                appdata, "Goldberg SteamEmu Saves", "2993780", "remote"
            ),
            "RUNE": os.path.join(public_docs, "RUNE", "2993780", "Saves"),
            "TENOKE": tenoke_path,
        }


class SaveProfileManager:
    """Manages all data and file operations for a single save profile."""

    SAVE_MANAGER_DIR = "_manager_data"

    def __init__(self, profile_path):
        self.path = profile_path
        self.manager_path = os.path.join(self.path, self.SAVE_MANAGER_DIR)
        self.slots_path = os.path.join(self.manager_path, "slots")
        self.metadata_path = os.path.join(self.manager_path, "metadata.json")
        self.metadata = self._load_metadata()

    def _load_metadata(self):
        """Loads the metadata for this profile from its JSON file."""
        if not os.path.exists(self.metadata_path):
            return {"active_slot_uuid": None, "slots": {}}
        try:
            with open(self.metadata_path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {"active_slot_uuid": None, "slots": {}}

    def _save_metadata(self):
        """Saves the current in-memory metadata to its JSON file."""
        os.makedirs(self.manager_path, exist_ok=True)
        with open(self.metadata_path, "w") as f:
            json.dump(self.metadata, f, indent=4)

    def has_active_save_file(self):
        """Checks if a gamedata.bin file exists in the profile root."""
        if not os.path.isdir(self.path):
            return False
        return any(f.endswith("gamedata.bin") for f in os.listdir(self.path))

    def initialize_from_game_save(self, name):
        """Creates the first slot from an existing game save."""
        slot_uuid = os.urandom(8).hex()
        slot_dir = os.path.join(self.slots_path, slot_uuid)
        os.makedirs(slot_dir, exist_ok=True)

        self.metadata["slots"][slot_uuid] = {
            "name": name,
            "backup_counter": 1,
            "backups": {},
            "active_save_timestamp": datetime.now().timestamp(),
        }
        self.metadata["active_slot_uuid"] = slot_uuid
        self._save_metadata()
        self.save_active_game_state(slot_uuid)

    def save_active_game_state(self, slot_uuid):
        """Zips gamedata.bin into the slot's active_save.zip."""
        if not self.has_active_save_file():
            return

        slot_dir = os.path.join(self.slots_path, slot_uuid)
        active_save_zip = os.path.join(slot_dir, "active_save.zip")
        with zipfile.ZipFile(active_save_zip, "w") as zf:
            for item in os.listdir(self.path):
                if item.endswith("gamedata.bin") or item.endswith(".binbak"):
                    zf.write(os.path.join(self.path, item), arcname=item)

        self.metadata["slots"][slot_uuid][
            "active_save_timestamp"
        ] = datetime.now().timestamp()
        self._save_metadata()

    def load_active_save_for_slot(self, slot_uuid):
        """Extracts a slot's active_save.zip to the profile root."""
        active_save_zip = os.path.join(self.slots_path, slot_uuid, "active_save.zip")
        if not os.path.exists(active_save_zip):
            return False

        for item in os.listdir(self.path):
            if item.endswith("gamedata.bin") or item.endswith(".binbak"):
                os.remove(os.path.join(self.path, item))

        with zipfile.ZipFile(active_save_zip, "r") as zf:
            zf.extractall(self.path)

        self.metadata["active_slot_uuid"] = slot_uuid
        self._save_metadata()
        return True

    def create_new_backup(self, slot_uuid, name):
        """Creates a new manual backup from the currently active game save."""
        if not self.has_active_save_file():
            return False

        backup_uuid = os.urandom(8).hex()
        backup_zip = os.path.join(self.slots_path, slot_uuid, f"{backup_uuid}.zip")

        with zipfile.ZipFile(backup_zip, "w") as zf:
            for item in os.listdir(self.path):
                if item.endswith("gamedata.bin") or item.endswith(".binbak"):
                    zf.write(os.path.join(self.path, item), arcname=item)

        slot_data = self.metadata["slots"][slot_uuid]
        slot_data["backups"][backup_uuid] = {
            "timestamp": datetime.now().timestamp(),
            "name": name,
        }
        slot_data["backup_counter"] = slot_data.get("backup_counter", 1) + 1
        self._save_metadata()
        return True

    def copy_slot_to(self, dest_manager, slot_uuid):
        """Copies a slot and all its data to another profile manager."""
        source_slot_dir = os.path.join(self.slots_path, slot_uuid)
        dest_slot_dir = os.path.join(dest_manager.slots_path, slot_uuid)

        if os.path.exists(dest_slot_dir):
            shutil.rmtree(dest_slot_dir)

        shutil.copytree(source_slot_dir, dest_slot_dir)

        slot_data_to_copy = self.metadata["slots"][slot_uuid]
        dest_manager.metadata["slots"][slot_uuid] = slot_data_to_copy
        dest_manager._save_metadata()


class ModManager:
    """Handles backend logic for mod installation, tracking, and management."""

    def __init__(self, game_path):
        self.game_path = game_path
        self.manifest_path = ""
        self.mods = []
        if game_path:
            self.manifest_path = os.path.join(
                game_path, SaveProfileManager.SAVE_MANAGER_DIR, "mods.json"
            )
            self._load_manifest()

    def _load_manifest(self):
        """Loads the list of tracked mods from mods.json."""
        if os.path.exists(self.manifest_path):
            try:
                with open(self.manifest_path, "r") as f:
                    self.mods = json.load(f)
            except (json.JSONDecodeError, IOError):
                self.mods = []
        else:
            self.mods = []

    def _save_manifest(self):
        """Saves the current list of mods to mods.json."""
        if not self.game_path:
            return
        os.makedirs(os.path.dirname(self.manifest_path), exist_ok=True)
        with open(self.manifest_path, "w") as f:
            json.dump(self.mods, f, indent=4)

    def get_mods(self):
        """Returns the list of mods, sorted alphabetically."""
        return sorted(self.mods, key=lambda m: m["name"].lower())

    def install_mod(self, zip_path):
        """Installs a mod from a zip file, tracks its files, and enables it."""
        mod_name = os.path.splitext(os.path.basename(zip_path))[0]
        if any(m["name"] == mod_name for m in self.mods):
            return {
                "success": False,
                "error": f"A mod named '{mod_name}' is already installed.",
            }

        installed_files = []
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                for file_info in zf.infolist():
                    if file_info.is_dir():
                        continue
                    rel_path = file_info.filename.replace("\\", "/")
                    if rel_path.lower().startswith("game/content/paks/~mods/"):
                        os.makedirs(
                            os.path.join(self.game_path, "Game/Content/Paks/~mods"),
                            exist_ok=True,
                        )

                    zf.extract(file_info, self.game_path)
                    installed_files.append(rel_path)

            self.mods.append(
                {"name": mod_name, "status": "enabled", "files": installed_files}
            )
            self._save_manifest()
            return {"success": True}
        except Exception as e:
            for file_path in installed_files:
                full_path = os.path.join(self.game_path, file_path)
                if os.path.exists(full_path):
                    os.remove(full_path)
            return {"success": False, "error": f"An unexpected error occurred: {e}"}

    def pre_install_check(self, zip_path):
        """Checks a zip file for potentially problematic file paths."""
        problematic_paths = []
        with zipfile.ZipFile(zip_path, "r") as zf:
            for file_info in zf.infolist():
                if file_info.is_dir():
                    continue
                rel_path = file_info.filename.replace("\\", "/")
                if rel_path.lower().startswith("game/content/paks/~mods/"):
                    continue
                destination_dir = os.path.dirname(
                    os.path.join(self.game_path, rel_path)
                )
                if not os.path.isdir(destination_dir):
                    problematic_paths.append(rel_path)
        return problematic_paths

    def toggle_mod_status(self, mod_name):
        """Enables or disables a mod by renaming its files."""
        for mod in self.mods:
            if mod["name"] == mod_name:
                is_enabled = mod["status"] == "enabled"
                new_status = "disabled" if is_enabled else "enabled"
                for file_rel_path in mod["files"]:
                    base_path = os.path.join(self.game_path, file_rel_path)
                    if is_enabled:
                        if os.path.exists(base_path):
                            shutil.move(base_path, base_path + ".disabled")
                    else:
                        disabled_path = base_path + ".disabled"
                        if os.path.exists(disabled_path):
                            shutil.move(disabled_path, base_path)
                mod["status"] = new_status
                self._save_manifest()
                return True
        return False

    def delete_mod(self, mod_name):
        """Deletes a mod and removes all its tracked files."""
        mod_to_delete = next((m for m in self.mods if m["name"] == mod_name), None)
        if not mod_to_delete:
            return

        for file_rel_path in mod_to_delete["files"]:
            for path in [
                os.path.join(self.game_path, file_rel_path),
                os.path.join(self.game_path, file_rel_path) + ".disabled",
            ]:
                try:
                    if os.path.exists(path):
                        os.remove(path)
                except OSError:
                    pass
        self.mods.remove(mod_to_delete)
        self._save_manifest()
