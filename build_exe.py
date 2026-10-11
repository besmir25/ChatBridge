"""Builds dist/ChatBridge/ChatBridge.exe  (run:  python build_exe.py).

Some Anaconda installs carry an old 'pathlib' backport that PyInstaller refuses to run next to, even though Python
loads its own built-in pathlib. We confirm that, then skip only that metadata check, so no one's environment is changed.
On a normal Python install the check passes by itself.
"""
import importlib.metadata as md
import os
import pathlib
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

if "site-packages" in pathlib.__file__:
    sys.exit("A third-party pathlib is shadowing the built-in one; remove it before building.")
_real = md.distribution


def _distribution(name):
    if name.lower() == "pathlib":
        raise md.PackageNotFoundError(name)
    return _real(name)


md.distribution = _distribution

import PyInstaller.__main__ as pyi  # noqa: E402

EXCLUDE = ["numpy", "scipy", "pandas", "matplotlib", "IPython", "notebook", "jupyter", "PyQt5", "PyQt6", "PySide2",
           "PySide6", "sphinx", "pytest", "sklearn", "numba", "bokeh", "dask", "h5py", "lxml", "sqlalchemy", "cryptography"]
args = ["--noconfirm", "--clean", "--windowed", "--name", "ChatBridge",
        "--icon", os.path.join(HERE, "assets", "chatbridge.ico"),
        "--add-data", f"{os.path.join(HERE, 'ui')};ui",
        "--add-data", f"{os.path.join(HERE, 'assets', 'chatbridge.png')};assets",
        "--add-data", f"{os.path.join(HERE, 'extension')};extension",
        "--distpath", os.path.join(HERE, "dist"), "--workpath", os.path.join(HERE, "build"),
        "--specpath", os.path.join(HERE, "build")]
for m in EXCLUDE:
    args += ["--exclude-module", m]
args.append(os.path.join(HERE, "chatbridge_app.py"))
pyi.run(args)
