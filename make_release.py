"""One command to make a release:  python make_release.py

Runs the tests, builds the app and the installer, zips the browser extension, and writes SHA-256 checksums into release/.
Then see RELEASING.md for signing and publishing.
"""
import hashlib
import os
import re
import shutil
import subprocess
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)


def run(*cmd):
    print("\n>", " ".join(cmd))
    if subprocess.run([sys.executable, *cmd]).returncode:
        sys.exit(f"Stopped: {' '.join(cmd)} failed.")


import release_tools  # noqa: E402

version = re.search(r'VERSION = "([^"]+)"', open("chatbridge_app.py", encoding="utf-8").read()).group(1)
try:  # fail early, before the slow builds, if the changelog has nothing to say about this version
    notes = release_tools.release_notes(version, open("CHANGELOG.md", encoding="utf-8").read())
except ValueError as e:
    sys.exit(str(e))
run("-W", "ignore", "-m", "unittest", "discover", "-s", "tests")
run("make_icon.py")
run("build_exe.py")
run("build_installer.py")

out = os.path.join(HERE, "release")
shutil.rmtree(out, ignore_errors=True)
os.makedirs(out)
setup = os.path.join(out, "ChatBridge-Setup.exe")
shutil.copyfile(os.path.join("dist", "ChatBridge-Setup.exe"), setup)
ext = os.path.join(out, f"ChatBridge-Capture-extension-{version}.zip")
with zipfile.ZipFile(ext, "w", zipfile.ZIP_DEFLATED) as z:
    for d, _, files in os.walk("extension"):
        for f in files:
            z.write(os.path.join(d, f), os.path.join("ChatBridge-Capture", os.path.relpath(os.path.join(d, f), "extension")))
with open(os.path.join(out, "SHA256SUMS.txt"), "w") as f:
    for p in (setup, ext):
        f.write(f"{hashlib.sha256(open(p, 'rb').read()).hexdigest()}  {os.path.basename(p)}\n")
with open(os.path.join(out, f"RELEASE_NOTES_v{version}.md"), "w", encoding="utf-8") as f:
    f.write(notes)
print(f"\nReady in release/ for version {version}:")
for name in sorted(os.listdir(out)):
    print(f"  {name}  ({os.path.getsize(os.path.join(out, name)) / 1e6:.1f} MB)")
