# PyInstaller build definition: `pyinstaller FLiSaMM.spec` creates dist/FLiSaMM.exe
from PyInstaller.utils.hooks import collect_data_files

a = Analysis(
    ["main.py"],
    datas=[("resources", "resources")] + collect_data_files("customtkinter"),
    hiddenimports=["py7zr"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    name="FLiSaMM",
    console=False,
    upx=False,
)
