# Code signing policy

ChatBridge releases are intended to be signed with a certificate provided by the
[SignPath Foundation](https://signpath.org) (free for open-source projects), once approved.

## What is signed
Only the installer (`ChatBridge-Setup.exe`) and the application it contains, built from the source code in this repository by
the public GitHub Actions workflow (`.github/workflows/release.yml`). Nothing is signed from a developer's own computer.

## Roles
- **Author, reviewer and approver:** [besmir25](https://github.com/besmir25), the sole maintainer. A release is created only
  when the maintainer pushes a version tag, and every release is built from the `main` branch after the tests pass.

## Privacy
ChatBridge keeps your conversations on your computer. The only network request it makes is an optional once-a-day check for a
newer version, which you can turn off. See [PRIVACY.md](PRIVACY.md).

## Verifying a download
Each release lists a SHA-256 checksum for every file (`SHA256SUMS.txt`).

## Reporting a problem
Open an [issue](../../issues) or see [SECURITY.md](SECURITY.md) for security reports.
