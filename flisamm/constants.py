"""
Stores static resources and configuration constants for the application.
"""

# --- Application Configuration ---
APP_NAME = "Fantasy Life i - Save & Mod Manager"
APP_VERSION = "1.0.0"
APP_DATA_DIR_NAME = "FLiSaMM"
WINDOW_SIZE = (1000, 850)
WINDOW_MIN_SIZE = (900, 600)

# --- Game Constants ---
STEAM_APP_ID = "2993780"
GAME_FOLDER_NAME = "FANTASY LIFE i"
EAC_LAUNCHER_EXE = "EACLauncher.exe"
GAME_EXE = "NFL1.exe"
SHIPPING_EXE_REL = "Game/Binaries/Win64/NFL1-Win64-Shipping.exe"
GAME_PROCESS_NAMES = ("NFL1-Win64-Shipping.exe",)
MODS_DIR_REL = "Game/Content/Paks/~mods"
TENOKE_SAVE_REL = "Game/Binaries/Win64/SteamData"

# --- Word Lists for Random Name Generation ---
FL_ADJECTIVES = [
    "Adept", "Ancient", "Apprentice", "Arcane", "Artisan", "Brave",
    "Legendary", "Celebrity", "Creator", "Divine", "Elder", "Expert",
    "Fabled", "Famous", "Fledgling", "Forgotten", "God-in-Training",
    "Golden", "Hero", "Illustrious", "Iron", "Leathern", "Magical",
    "Master", "Mythic", "Novice", "Royal", "Sacred", "Silken", "Silvern",
    "Star", "Sturdy", "Whimsical", "Wise", "Wooden", "Blissful",
    "Bubbling", "Buzzy", "Carved", "Cooked", "Courageous", "Curious",
    "Daring", "Dashing", "Floating", "Fluffy", "Forged", "Glimmering",
    "Grassy", "Happy", "Heroic", "Humble", "Jolly", "Joyful", "Lucky",
    "Mysterious", "Nimble", "Oceanic", "Peaceful", "Plushy", "Radiant",
    "Sandy", "Sassy", "Shiny", "Sleepy", "Sparkling", "Spooky",
    "Starlight", "Sunny", "Woven"
]
FL_NOUNS = [
    "Alchemist", "Angler", "Blacksmith", "Carpenter", "Cook", "Hunter",
    "Magician", "Mercenary", "Miner", "Paladin", "Tailor", "Woodcutter",
    "Artist", "Bandit", "Butterfly", "Divinus", "Explorer", "Farmer",
    "Goddess", "Islander", "King", "Knight", "Laura", "Noelia", "Pam",
    "Queen", "Yuelia", "Behemoth", "Carrot", "Dragon", "Ghost", "Golem",
    "Jell-O", "Mandragora", "Napdragon", "Puffer", "Spirit", "Spiky",
    "Wyvern", "Aquade", "Castele", "Crystal", "Desert", "Dosh", "Farm",
    "Forest", "Island", "Key", "Library", "Meadow", "Mountain", "Past",
    "Present", "Relic", "Reveria", "Rune", "Shrine", "Time", "Volcano",
    "Waterfall", "Workshop", "Axe", "Bow", "Dagger", "Elixir", "Fabric",
    "Fish", "Gem", "Hammer", "Log", "Meal", "Moon", "Ore", "Potion",
    "Scroll", "Staff", "Star", "Sun", "Sword"
]