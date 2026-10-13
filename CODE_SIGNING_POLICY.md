# Code signing policy

ChatBridge has applied for free code signing from the [SignPath Foundation](https://signpath.org). Until the application is
approved, releases are **not** signed. Once approved, releases will be signed with a certificate issued by SignPath Foundation, and
this page will carry the line: *Free code signing provided by [SignPath.io](https://signpath.io), certificate by SignPath Foundation.*

## What is signed
Only the program `ChatBridge.exe` and the installer `ChatBridge-Setup.exe`, built from the source code in this repository by the
public GitHub Actions workflow ([`.github/workflows/release.yml`](.github/workflows/release.yml)) when a version tag is pushed.
Nothing is ever signed from a developer's own computer. Every file carries the product name "ChatBridge" and the same version
number as the release.

## How releases are made
1. A version tag (for example `v1.3.0`) is pushed to the `main` branch.
2. GitHub Actions runs the test suite, then builds the program and installer from that exact commit.
3. Every signing request is approved manually by the approver below before a release is published.

## Team and roles
ChatBridge is maintained by one person, who holds all roles:

| Role | Who |
|---|---|
| Author (changes the source code) | [besmir25](https://github.com/besmir25) |
| Reviewer (reviews changes from other people) | [besmir25](https://github.com/besmir25) |
| Approver (approves each signing request) | [besmir25](https://github.com/besmir25) |

Changes proposed by other people (pull requests) are reviewed before they are merged. Multi-factor authentication is required for
the maintainer's GitHub and SignPath accounts.

## Privacy
ChatBridge keeps your conversations on your computer. It does not send information to other networked systems, with one
exception that you can switch off in Settings: a once-a-day check that asks GitHub for the newest version number. See
[PRIVACY.md](PRIVACY.md).

## What the program does to your system
Installing copies the program into your user folder and adds a Start menu entry and an uninstaller (Settings → Apps). The
program can paste into other apps on your behalf, but it never presses Enter or sends anything for you. It does not change
system or security settings.

## Reporting a problem
Open an [issue](../../issues), or see [SECURITY.md](SECURITY.md) for security reports.
