# FLiSaMM - Fantasy Life i Save and Mod Manager

![image](https://github.com/user-attachments/assets/e3538e2a-750b-4836-b8eb-038043d23fb5) ![image](https://github.com/user-attachments/assets/9343d33b-0e22-49a7-ac33-5cc9c69a7ad4)



## A comprehensive tool for managing mods and save files for Fantasy Life i.

This application provides a user-friendly interface to streamline your modding and save management experience for Fantasy Life i: The Girl Who Steals Time on PC.

## Features

*   **Comprehensive Save Management:**
    *   Detects multiple save locations (Steam, Online-Fix, Goldberg, RUNE, TENOKE).
    *   Create, load, rename, and delete individual save slots.
    *   Each slot tracks its "Active Save" (your last played state) for quick loading.
    *   Create manual, named backups within each save slot.
    *   Load any manual backup, with an optional prompt to save current progress.
    *   Copy entire save slots between different save profiles.
*   **Intuitive Mod Management:**
    *   Install mods from `.zip` files directly into your game directory.
    *   Track all installed mod files for easy management.
    *   Enable and disable mods with a simple toggle switch.
    *   Delete mods and automatically remove their installed files.
    *   Pre-install checks warn about potentially malformed mod packages.
*   **Game Utilities:**
    *   **Easy Anti-Cheat (EAC) Bypass:** Toggle EAC on/off for mod compatibility, with clear warnings.
    *   **Flexible Game Launch:** Launch the game via Steam or directly using the game's executable.
*   **Smart & Safe Operation:**
    *   Detects if the game is running and automatically locks sensitive controls (loading saves, modifying mods) to prevent data corruption.
    *   Automatically organizes save data and mod manifests in a `_manager_data` folder within each save profile.

## Installation

### Prerequisites

*   **Python 3.8+:** Download from [python.org](https://www.python.org/downloads/).
*   **`pip`:** Usually comes installed with Python.
*   **`git` (Optional, but recommended for cloning):** Download from [git-scm.com](https://git-scm.com/downloads).

### Setup Steps

1.  **Clone the repository (recommended):**
    ```bash
    git clone https://github.com/zmarotrix/FLiSaMM.git
    cd FLiSaMM
    ```

    **Alternatively, download the ZIP:**
    Go to the GitHub repository page, click "Code" -> "Download ZIP", then extract the contents to your desired folder.

2.  **Create a Virtual Environment (Recommended for dependency management):**
    ```bash
    python -m venv venv
    ```

3.  **Activate the Virtual Environment:**
    ```bash
    .\venv\Scripts\activate
    ```

4.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

5.  **Run the Application:**
    ```bash
    python main.py
    ```

## Usage Guide

Upon first launch, the application will attempt to automatically locate your `FANTASY LIFE i` game directory. If it cannot, you will be prompted to select it manually.

### Save Management

The "Save Management" tab is designed to handle all your game saves.

#### Save Profiles

The top row of tabs (e.g., "Steam", "Online-Fix", "Goldberg") represents different save *profiles* or locations on your system. Each profile manages its own set of save slots independently.

#### Save Slots

The left panel lists your "Save Slots". Each slot is an independent container for a save game.

*   **Creating a New Empty Slot:** Click `[ + ] Create New Empty Slot`. You'll be prompted to name it.
*   **Renaming a Slot:** Select a slot, then click "Rename Slot".
*   **Deleting a Slot:** Right-click on a slot and choose "Delete". This will permanently remove the slot and all its backups.

#### Active Save (`[LOADED]`)

When you select a save slot, the top section of the right panel displays information about its "Active Save". This represents the most recent state of that slot.

*   When you load a slot or restore a backup, its "Active Save" becomes the live `gamedata.bin` file that the game uses.
*   If a slot's Active Save is currently loaded by the game, it will show `[LOADED]` next to its name in the slot list, and the Active Save panel will have a blue border.
*   **Loading a Slot's Active Save:** Select a slot, then click "Load Slot" on the left panel.
    *   If the slot is empty (newly created), the application will clear the game's save directory. You must then launch the game to create a new save file for this slot.
    *   If the slot contains an existing Active Save, it will be loaded.

#### Manual Backups

The main section of the right panel, "Manual Backups", lists all the specific snapshots you've created for the selected save slot.

*   **Creating a New Backup:** Select a loaded slot, then click "Create New Backup". It will automatically be named sequentially (e.g., "Backup - 0001").
*   **Loading a Backup:** Select a backup in the list, then click "Load". You will be prompted to save your current game progress before the backup overwrites it.
*   **Renaming a Backup:** Select a backup in the list, then click "Rename Backup".
*   **Deleting a Backup:** Select a backup in the list, then click "Delete Backup".

#### Actions: Load Slot, Create/Rename/Delete/Copy Slot/Backup

*   **Load Slot:** Loads the Active Save for the selected slot.
*   **Create New Empty Slot:** Creates a new, blank save slot.
*   **Rename Slot:** Renames the selected save slot.
*   **Delete Slot:** Permanently deletes the selected slot and all its data.
*   **Copy Slot to...:** Copies the selected slot (including its Active Save and all Manual Backups) to another save profile. You will choose the destination from a list of detected save locations.
*   **Create New Backup:** Creates a new manual backup of the currently loaded game save for the selected slot.
*   **Rename Backup:** Renames the selected manual backup.
*   **Delete Backup:** Permanently deletes the selected manual backup.

### Mod Management

The "Mod Management" tab is where you control your game modifications.

#### Installing Mods

1.  Click "Install Mod(s)..." at the top right of the tab.
2.  Select one or more `.zip` mod files.
3.  The application will warn you if a mod seems to be packaged incorrectly (e.g., extracting to non-existent directories). You can choose to proceed or cancel.
4.  Mods are extracted directly into your game's root directory.

#### Enabling/Disabling Mods

*   In the "Installed Mods" list, use the **toggle switch** next to each mod name to instantly enable or disable it.
*   Disabling a mod renames its files with a `.disabled` extension, making them inactive without deleting them. Enabling reverses this process.

#### Deleting Mods

*   Click the **"Delete" button** next to a mod name in the list.
*   Confirm deletion to permanently remove the mod's files from your game directory.

#### ⚠️ Modding Warning ⚠️

A prominent red banner on the Mod Management tab serves as an important reminder:
**"Use mods at your own risk. There are no reported bans from modding so far, but we do not know how LEVEL-5 will handle this in the future."**

### Game Utilities

Located at the bottom of the "Mod Management" tab.

#### Easy Anti-Cheat (EAC) Bypass

*   **"Bypass Enabled" Switch:** Toggle this on to launch the game without EAC. This is often required for certain types of mods to function correctly.
*   **How it Works:** Enabling the bypass renames the original `EACLauncher.exe` to `EACLauncher.exe.bak` (in the same folder) and renames `NFL1.exe` (the game's main executable) to `EACLauncher.exe`. Disabling reverses this.
*   **Online Play:** If you play with the bypass enabled, you will **only be able to play online with other users who also have the bypass enabled**.

#### Launch Game

*   **"Launch via Steam" Switch:** Toggle this on to launch the game through Steam (recommended for Steam features like overlays). Toggle it off to launch the game directly via its `EACLauncher.exe` file.
*   **"Launch Game" Button:** Clicks this to launch the game using your selected method.

### Game Running Lockout

For your safety and to prevent data corruption:

*   The application detects if `NFL1-Win64-Shipping.exe` is running.
*   When the game is detected, a **"GAME RUNNING - CONTROLS LOCKED"** banner appears in the header.
*   All sensitive actions (loading saves and installing/enabling/disabling/deleting mods) are automatically disabled. You can still browse, rename save slots and create save backups.
*   Controls are re-enabled once the game process is no longer detected.

## Troubleshooting

*   **"Path Invalid" or "Game Not Found":** Ensure your selected game directory is named `FANTASY LIFE i` and contains `EACLauncher.exe`, `NFL1.exe`, and the `Game/Binaries/Win64/NFL1-Win64-Shipping.exe` path.
*   **"TypeError: _path_isdir: path should be string..." at startup:** Delete the `config.json` file in the application's root directory and restart the manager. This usually indicates a malformed config.
*   **Errors on File Operations (e.g., deleting/renaming):** Ensure the game is not running. Files are often in use by the game process.

## Contributing

Contributions are welcome! If you have suggestions for improvements, bug fixes, or new features:

1.  Fork the repository.
2.  Create a new branch (`git checkout -b feature/your-feature`).
3.  Make your changes.
4.  Write clear commit messages.
5.  Push your branch (`git push origin feature/your-feature`).
6.  Open a Pull Request.

## License

This project is open-source and available under the [GNU General Public License v3.0](LICENSE).

## Acknowledgements

*   **CustomTkinter:** For providing a modern Tkinter UI toolkit.
*   **psutil:** For cross-platform system and process utilities.
*   **Pillow:** For image processing capabilities.
*   **LEVEL-5:** For creating Fantasy Life i. This is a fan-made tool and is not affiliated with them.

---
