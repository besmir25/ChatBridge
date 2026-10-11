# Releasing a new version

1. **Change the version** in `chatbridge_app.py` (`VERSION = "1.0.1"`). The installer and update check read it from there.
2. **Build everything**: `python make_release.py`. It runs the tests, builds the app and the installer, zips the browser
   extension, and writes checksums into `release/`.
3. **Try it**: run `release/ChatBridge-Setup.exe` on a PC (or install with `--silent --dir <folder>` to test), open the app,
   send a chat, then uninstall.
4. **Sign it** (see below) *before* publishing, then re-run the checksum step so `SHA256SUMS.txt` matches the signed file.
5. **Publish**: on GitHub, *Releases → Draft a new release*. Tag it `v1.0.1` (the leading `v` is expected), paste the
   release notes, and attach everything in `release/`. The in-app update check finds the newest *published* release.

## Signing
An unsigned installer shows Windows SmartScreen's "unknown publisher" warning. Options, cheapest first:
- **Open source:** apply to a free signing programme for open-source projects (such as SignPath Foundation). Needs a public
  repository with an OSI-approved licence.
- **Microsoft Artifact Signing** (formerly Trusted Signing): about $10 a month, with an identity check. Individuals are limited
  to the US and Canada.
- **An OV code-signing certificate** from a certificate authority: roughly $150–300 a year.

Signing doesn't remove the warning instantly; Windows builds reputation for a publisher over time.
Check each provider's current terms before you buy or apply.

## Release notes template
```
## What's new
- ...

## Install
Download ChatBridge-Setup.exe below. To check it, compare its SHA-256 with SHA256SUMS.txt.
The browser extension is a separate zip (unzip, then load it from edge://extensions).
```
