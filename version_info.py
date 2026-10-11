"""Writes the Windows 'Details' tab info (product name, version, publisher) that PyInstaller stamps into an .exe."""
import re


def write_version_file(path, version, description):
    nums = [int(n) for n in re.findall(r"\d+", version)[:3]]
    nums += [0] * (3 - len(nums))
    tup = tuple(nums) + (0,)
    text = f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={tup}, prodvers={tup}, mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040904B0', [
      StringStruct('CompanyName', 'besmir25'),
      StringStruct('FileDescription', {description!r}),
      StringStruct('FileVersion', {version!r}),
      StringStruct('InternalName', 'ChatBridge'),
      StringStruct('LegalCopyright', 'Copyright (c) 2026 besmir25. MIT License.'),
      StringStruct('OriginalFilename', 'ChatBridge.exe'),
      StringStruct('ProductName', 'ChatBridge'),
      StringStruct('ProductVersion', {version!r})])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
