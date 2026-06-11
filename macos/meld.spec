import json
import subprocess
import sys
from pathlib import Path


def get_install_tree_library_path():
    lib_base = Path("lib")
    python_paths = list(lib_base.glob("python3.*"))
    if len(python_paths) > 1:
        raise RuntimeError("Multiple python installs found")
    return python_paths[0] / "site-packages"


def get_install_languages():
    share_base = Path("share")
    mo_paths = (share_base / "locale").glob("*/LC_MESSAGES/meld.mo")
    return [p.parents[1].name for p in mo_paths]


def get_version():
    projectinfo = json.loads(
        subprocess.run(
            ["meson", "introspect", "../meson.build", "--projectinfo"],
            encoding="utf-8",
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    )
    return projectinfo["version"]


# Insert the site-packages path installed by meson into PYTHONPATH
sys.path.insert(0, str(get_install_tree_library_path()))

version = get_version()

a = Analysis(
    ["bin/meld"],
    binaries=[],
    datas=[
        ("share", "share"),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={
        "gi": {
            "icons": ["Adwaita"],
            "themes": ["Adwaita"],
            "languages": get_install_languages(),
            "module-versions": {
                "Gtk": "4.0",
                "GtkSource": "5",
            },
        },
    },
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="meld",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Meld",
)

app = BUNDLE(
    coll,
    name="Meld.app",
    icon="meld.icns",
    bundle_identifier="org.gnome.Meld",
    info_plist={
        "CFBundleShortVersionString": version,
        "CFBundleVersion": version,
        "CFBundleName": "Meld",
        "CFBundleDisplayName": "Meld",
        "CFBundleExecutable": "meld",
        "CFBundlePackageType": "APPL",
        "NSHighResolutionCapable": True,
        "NSRequiresAquaSystemAppearance": False,
    },
)
