# FLiSaMM - Fantasy Life i Save and Mod Manager

![image](https://github.com/user-attachments/assets/e3538e2a-750b-4836-b8eb-038043d23fb5) ![image](https://github.com/user-attachments/assets/9343d33b-0e22-49a7-ac33-5cc9c69a7ad4)



## A comprehensive tool for managing mods and save files for Fantasy Life i.

This application provides a user-friendly interface to streamline your modding and save management experience for Fantasy Life i: The Girl Who Steals Time on PC.

## Features

*   **Comprehensive Save Management:**
    *   Detects multiple save locations (Steam, Online-Fix, GBE_Fork, Goldberg, RUNE, TENOKE).
    *   Create, load, rename, and delete individual save slots.
    *   Each slot tracks its "Active Save" (your last played state), updated automatically when you close the game.
    *   Create manual, named backups within each save slot, with search and sorting (no limit on how many are shown).
    *   Load any manual backup, with an optional prompt to back up your current progress first.
    *   Copy entire save slots between different save profiles.
*   **Safe by Design:**
    *   Every time the live save is replaced or deleted, a safety copy is kept first (the last 10 per profile).
    *   Save swaps are rolled back automatically if anything fails part-way, so a locked file can't leave you with no save.
    *   All manager data is written atomically, with a backup copy, so a crash can't corrupt it.
    *   Manager data is kept in `%LOCALAPPDATA%\FLiSaMM`, not inside the game folder or Steam's cloud-synced save folder.
*   **Intuitive Mod Management:**
    *   Install mods from `.zip` or `.7z` archives, or directly from loose `.pak`/`.utoc`/`.ucas` files.
    *   `.pak` mods are placed in `Game/Content/Paks/~mods` automatically, however the archive is laid out.
    *   Enable and disable mods with a toggle switch. Mods are stored separately and linked into the game, so nothing is ever renamed or lost.
    *   Game files replaced by a mod are backed up and restored when the mod is disabled or deleted.
    *   Load order with conflict detection: when two mods change the same file, the one lower in the list wins.
    *   Re-install a mod with the same name to update it in place.
    *   Detects mods you installed by hand (or with another tool) in `~mods` and offers to import them.
*   **Game Utilities:**
    *   **Easy Anti-Cheat (EAC) Bypass:** Toggle EAC on/off for mod compatibility. Detects when a game update or Steam's "Verify integrity of game files" has undone it.
    *   **Flexible Game Launch:** Launch the game via Steam or directly using the game's executable.
    *   Finds the game automatically in any of your Steam library folders.
*   **Smart & Safe Operation:**
    *   Detects if the game is running and automatically locks sensitive controls (loading saves, modifying mods) to prevent data corruption.

## Installation

### Option 1: Download the app (recommended)

Download `FLiSaMM.exe` from the [Releases page](https://github.com/zmarotrix/FLiSaMM/releases) and run it. No Python needed.

### Option 2: Run from source

Requires **Python 3.11+** from [python.org](https://www.python.org/downloads/).

1.  Clone the repository (or download the ZIP from GitHub and extract it):
    ```bash
    git clone https://github.com/zmarotrix/FLiSaMM.git
    cd FLiSaMM
    ```
2.  Double-click `Launch.bat`. It creates a virtual environment, installs the dependencies the first time, and starts the app.

    Or do it by hand:
    ```bash
    python -m venv venv
    .\venv\Scripts\activate
    pip install -r requirements.txt
    python main.py
    ```

### Upgrading from 0.9

Just run the new version. On first start it moves your existing data:

*   Save slots and backups move from each save folder's `_manager_data` folder into `%LOCALAPPDATA%\FLiSaMM\profiles`.
*   Installed mods are imported into the mod store and keep their enabled/disabled state.
*   Your settings (`config.json`) are imported.

The old files are kept in a `legacy_import` folder inside the data folder, just in case.

## Usage Guide

Upon first launch, the application will attempt to automatically locate your `FANTASY LIFE i` game directory. If it cannot, you will be prompted to select it manually.

### Save Management

The "Save Management" tab is designed to handle all your game saves.

#### Save Profiles

The row of tabs (e.g., "Steam", "Online-Fix", "Goldberg") represents different save *profiles* or locations on your system. Each profile manages its own set of save slots independently.

#### Save Slots

The left panel lists your "Save Slots". Each slot is an independent container for a save game.

*   **Creating a New Empty Slot:** Click `[ + ] Create New Empty Slot`. You'll be prompted to name it.
*   **Renaming a Slot:** Select a slot, then click "Rename" (or right-click the slot).
*   **Deleting a Slot:** Select a slot and click "Delete" (or right-click it). This permanently removes the slot and all its backups.
*   **Copy Slot to...:** Copies the selected slot (including its latest progress and all Manual Backups) to another save profile.

#### Active Save (`[LOADED]`)

The top of the right panel shows the selected slot's "Active Save", the most recent state of that slot.

*   The loaded slot is marked `[LOADED]` in the slot list, and its Active Save panel has a blue border.
*   **Load Slot:** Makes the selected slot's Active Save the live save file the game uses. Your progress in the previously loaded slot is saved into that slot first.
    *   If the slot is empty (newly created), the game's save is cleared. Launch the game to create a new save for this slot.

#### Manual Backups

The main section of the right panel lists the snapshots you've made of the selected slot.

*   **Create New Backup:** Snapshots the current game save of the loaded slot. Backups are named sequentially (e.g., "Backup - 0001"). This works while the game is running.
*   **Load:** Restores a backup and makes its slot the loaded slot. You will be offered a backup of your current progress first.
*   **Rename Backup / Delete Backup:** Select a backup in the list first.

#### Steam Cloud

If Steam reports a cloud sync conflict after you switch slots, choose to keep the files on this PC; those are the ones you just loaded.

### Mod Management

The "Mod Management" tab is where you control your game modifications.

#### Installing Mods

1.  Click "Install Mod(s)..." at the top right of the tab.
2.  Select one or more `.zip`/`.7z` archives, or `.pak` files (a `.pak` with matching `.utoc`/`.ucas` files is installed as one mod).
3.  The app works out where the files belong. If something looks wrong (for example, the mod would create new folders in the game directory), it warns you and asks before installing.

Readme files and images inside an archive are not copied into the game.

#### Mods Installed Outside FLiSaMM

If you copied mods into `Game/Content/Paks/~mods` yourself, FLiSaMM lists them at the top of the mod list and offers to **Import** them. Each subfolder of `~mods` counts as one mod, and loose files are grouped by name (a `.pak` with its `.utoc`/`.ucas`). Files ending in `.disabled` (how 0.9 turned mods off) are imported as disabled mods. Nothing is moved until you click Import; after that, the mods can be toggled, reordered and deleted like any other.

#### Enabling/Disabling Mods and Load Order

*   Use the **toggle switch** next to each mod to enable or disable it.
*   Use the **▲ ▼** buttons to change the load order. If two enabled mods contain the same file, the one lower in the list wins; the list shows which mods override each other.
*   **Disable All** turns every mod off and restores the game's original files.
*   **Re-apply Mods** puts back any mod files that were removed (for example by Steam's "Verify integrity of game files").

#### Deleting Mods

Click the **Delete** button next to a mod. Its files are removed from the game folder and any original game files it replaced are restored.

#### How mods are stored

Mods are kept in `%LOCALAPPDATA%\FLiSaMM\installs\<id>\mods` and linked into the game folder with hard links (or copied, if the game is on a different drive). Original game files a mod replaces are kept in the `vanilla` folder next to it.

#### ⚠️ Modding Warning ⚠️

A prominent red banner on the Mod Management tab serves as an important reminder:
**"Use mods at your own risk. There are no reported bans from modding so far, but we do not know how LEVEL-5 will handle this in the future."**

### Game Utilities

Located at the bottom of the "Mod Management" tab.

#### Easy Anti-Cheat (EAC) Bypass

*   **"Bypass Enabled" Switch:** Toggle this on to launch the game without EAC. This is often required for certain types of mods to function correctly.
*   **How it Works:** Enabling the bypass renames the original `EACLauncher.exe` to `EACLauncher.exe.bak` and puts a copy of `NFL1.exe` (the game's main executable) in its place. Disabling reverses this.
*   **After game updates:** If Steam restores the original launcher, the app notices on startup, cleans up, and turns the switch off so you can re-enable it. If an update changes `NFL1.exe`, the bypass copy is refreshed automatically.
*   **Online Play:** If you play with the bypass enabled, you will **only be able to play online with other users who also have the bypass enabled**.

#### Launch Game

*   **"Launch via Steam" Switch:** Toggle this on to launch the game through Steam (recommended for Steam features like overlays). Toggle it off to launch the game directly via its `EACLauncher.exe` file.
*   **"Launch Game" Button:** Launches the game using your selected method.

### Game Running Lockout

For your safety and to prevent data corruption:

*   The application detects if `NFL1-Win64-Shipping.exe` is running.
*   When the game is detected, a **"GAME RUNNING - CONTROLS LOCKED"** banner appears in the header.
*   Loading saves and backups, deleting the loaded slot, and changing mods or the EAC bypass are disabled. You can still browse, rename, copy slots and create save backups.
*   When the game closes, the loaded slot's Active Save is updated with your latest progress and the controls are re-enabled.

## Data Folder

Everything the manager stores lives in `%LOCALAPPDATA%\FLiSaMM` (the "Open Data Folder" button opens it):

| Folder | Contents |
| --- | --- |
| `config.json` | Your settings |
| `profiles\<id>\` | Save slots, backups and `safety` copies for each save location |
| `installs\<id>\` | Installed mods, backed-up original game files and the EAC state |
| `logs\flisamm.log` | Log file; include it when reporting a bug |

Set the `FLISAMM_DATA_DIR` environment variable to use a different folder (for example, for a portable setup), and `FLISAMM_STEAM_PATH` if Steam can't be found automatically.

## Troubleshooting

*   **"Path Invalid" or "Game Not Found":** Ensure your selected game directory is named `FANTASY LIFE i` and contains `EACLauncher.exe`, `NFL1.exe`, and the `Game/Binaries/Win64/NFL1-Win64-Shipping.exe` path.
*   **Lost progress after a mistake:** Check the `safety` folder for the profile in the data folder. Each zip holds the save as it was right before it was replaced; extract it into the game's save folder while the game is closed.
*   **Errors on File Operations:** Ensure the game is not running. Files are often in use by the game process. Details are in `logs\flisamm.log`.

## Development

```bash
pip install -r requirements-dev.txt
python -m pytest              # run the tests
pyinstaller FLiSaMM.spec      # build dist/FLiSaMM.exe
```

The code lives in the `flisamm` package: `saves.py`, `mods.py`, `game.py` and `steam.py` hold all the logic (no UI code, fully covered by tests in `tests/`), and `flisamm/ui/` holds the CustomTkinter interface. Pushing a tag like `v1.0.0-e` builds the exe and publishes a GitHub release automatically.

## Contributing

Contributions are welcome! If you have suggestions for improvements, bug fixes, or new features:

1.  Fork the repository.
2.  Create a new branch (`git checkout -b feature/your-feature`).
3.  Make your changes and run the tests.
4.  Write clear commit messages.
5.  Push your branch (`git push origin feature/your-feature`).
6.  Open a Pull Request.

## License

This project is open-source and available under the [GNU General Public License v3.0](LICENSE).

## Acknowledgements

*   **CustomTkinter:** For providing a modern Tkinter UI toolkit.
*   **psutil:** For cross-platform system and process utilities.
*   **Pillow:** For image processing capabilities.
*   **py7zr:** For 7z archive support.
*   **LEVEL-5:** For creating Fantasy Life i. This is a fan-made tool and is not affiliated with them.
