"""Pull each installed app's real icon from Windows (the same one the Start menu shows) as a PNG."""
import base64
import json
import os
import re
import subprocess
import tempfile

_PS = r'''
Add-Type -AssemblyName System.Drawing
Add-Type -ReferencedAssemblies System.Drawing -TypeDefinition @"
using System; using System.Drawing; using System.Drawing.Imaging; using System.Runtime.InteropServices;
public static class IconGrab {
  [StructLayout(LayoutKind.Sequential)] struct SIZE { public int cx, cy; }
  [StructLayout(LayoutKind.Sequential)] struct BITMAP { public int bmType, bmWidth, bmHeight, bmWidthBytes; public short bmPlanes, bmBitsPixel; public IntPtr bmBits; }
  [ComImport, Guid("bcc18b79-ba16-442f-80c4-8a59c30c463b"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
  interface IShellItemImageFactory { [PreserveSig] int GetImage(SIZE size, int flags, out IntPtr hbm); }
  [DllImport("shell32.dll", CharSet = CharSet.Unicode, PreserveSig = false)]
  static extern void SHCreateItemFromParsingName(string path, IntPtr pbc, ref Guid riid, [MarshalAs(UnmanagedType.Interface)] out IShellItemImageFactory ppv);
  [DllImport("gdi32.dll")] static extern int GetObject(IntPtr h, int cb, ref BITMAP bmp);
  [DllImport("gdi32.dll")] static extern bool DeleteObject(IntPtr h);
  public static bool Save(string parsingName, string outPath, int px) {
    try {
      Guid iid = new Guid("bcc18b79-ba16-442f-80c4-8a59c30c463b");
      IShellItemImageFactory f; SHCreateItemFromParsingName(parsingName, IntPtr.Zero, ref iid, out f);
      IntPtr hbm; SIZE s = new SIZE(); s.cx = px; s.cy = px;
      if (f.GetImage(s, 0x4, out hbm) != 0 || hbm == IntPtr.Zero) return false;   // 0x4 = icon only, no thumbnail
      BITMAP b = new BITMAP(); GetObject(hbm, Marshal.SizeOf(typeof(BITMAP)), ref b);
      using (Bitmap bmp = new Bitmap(b.bmWidth, b.bmHeight, b.bmWidthBytes, PixelFormat.Format32bppArgb, b.bmBits)) {
        Bitmap copy = new Bitmap(bmp);
        copy.RotateFlip(RotateFlipType.RotateNoneFlipY);   // shell DIBs are bottom-up
        copy.Save(outPath, ImageFormat.Png); copy.Dispose();
      }
      DeleteObject(hbm); return true;
    } catch { return false; }
  }
}
"@
$jobs = Get-Content -Raw -Encoding UTF8 $env:CB_JOBS | ConvertFrom-Json
foreach ($j in $jobs) { [void][IconGrab]::Save($j.parse, $j.out, 96) }
'''


def _safe(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "app"


def fetch_icons(items, cache_dir):
    """items: [{'key': name, 'parse': 'shell:AppsFolder\\<AppID>' or a file path}] -> {key: data-URI or None}."""
    os.makedirs(cache_dir, exist_ok=True)
    jobs, result = [], {}
    for it in items:
        out = os.path.join(cache_dir, _safe(it["key"]) + ".png")
        result[it["key"]] = out
        if not os.path.isfile(out) and it.get("parse"):
            jobs.append({"parse": it["parse"], "out": out})
    if jobs:
        fd, jf = tempfile.mkstemp(suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(jobs, f)
        try:
            subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", _PS],
                           env={**os.environ, "CB_JOBS": jf}, capture_output=True, timeout=60,
                           creationflags=0x08000000)
        except (OSError, subprocess.SubprocessError):
            pass
        finally:
            os.remove(jf)
    uris = {}
    for key, path in result.items():
        try:
            with open(path, "rb") as f:
                uris[key] = "data:image/png;base64," + base64.b64encode(f.read()).decode()
        except OSError:
            uris[key] = None
    return uris
