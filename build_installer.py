"""Builds dist/ChatBridge-Setup.exe from dist/ChatBridge (run build_exe.py first):  python build_installer.py"""
import importlib.metadata as md
import os
import re
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.join(HERE, "dist", "ChatBridge")
if not os.path.isfile(os.path.join(APP_DIR, "ChatBridge.exe")):
    sys.exit("Run build_exe.py first - dist/ChatBridge/ChatBridge.exe is missing.")

# Same Anaconda 'pathlib' workaround as build_exe.py (see the note there); harmless on a normal Python install.
_real = md.distribution
md.distribution = lambda name: (_ for _ in ()).throw(md.PackageNotFoundError(name)) if name.lower() == "pathlib" else _real(name)

version = re.search(r'VERSION = "([^"]+)"', open(os.path.join(HERE, "chatbridge_app.py"), encoding="utf-8").read()).group(1)
build = os.path.join(HERE, "build", "installer")
os.makedirs(build, exist_ok=True)
with open(os.path.join(build, "version.txt"), "w", encoding="utf-8") as f:
    f.write(version)

payload = os.path.join(build, "payload.zip")
with zipfile.ZipFile(payload, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
    for d, _, files in os.walk(APP_DIR):
        for name in files:
            full = os.path.join(d, name)
            z.write(full, os.path.relpath(full, APP_DIR))
print(f"payload: {os.path.getsize(payload) / 1e6:.1f} MB, version {version}")

from version_info import write_version_file  # noqa: E402

VERSION_FILE = os.path.join(build, "version_info_setup.txt")
write_version_file(VERSION_FILE, version, "ChatBridge Setup")

import PyInstaller.__main__ as pyi  # noqa: E402

EXCLUDE = ["numpy", "scipy", "pandas", "matplotlib", "IPython", "notebook", "PyQt5", "PyQt6", "PySide2", "PySide6", "sphinx",
           "pytest", "sklearn", "numba", "bokeh", "dask", "h5py", "lxml", "sqlalchemy", "cryptography", "webview", "clr_loader"]
args = ["--noconfirm", "--clean", "--onefile", "--windowed", "--name", "ChatBridge-Setup",
        "--icon", os.path.join(HERE, "assets", "chatbridge.ico"), "--version-file", VERSION_FILE,
        "--add-data", f"{payload};.", "--add-data", f"{os.path.join(build, 'version.txt')};.",
        "--add-data", f"{os.path.join(HERE, 'assets', 'chatbridge.png')};assets",
        *[a for n in (48, 96, 144, 192) for a in ("--add-data", f"{os.path.join(HERE, 'assets', f'installer-logo-{n}.png')};assets")],
        "--distpath", os.path.join(HERE, "dist"), "--workpath", os.path.join(build, "work"), "--specpath", build]
for m in EXCLUDE:
    args += ["--exclude-module", m]
args.append(os.path.join(HERE, "installer.py"))
pyi.run(args)
