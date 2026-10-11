# Releasing a new version

## Version numbers
ChatBridge uses three numbers, `MAJOR.MINOR.PATCH` (for example `1.2.3`):

| Change | Bump | Example |
|---|---|---|
| Bug fix, small tweak, new app profile | the last number | 1.0.0 → 1.0.1 |
| New feature that doesn't break anything | the middle number | 1.0.1 → 1.1.0 |
| Something that changes how people use it, or breaks old data | the first number | 1.1.0 → 2.0.0 |

Add `-beta1` for a trial release (`1.2.0-beta1`). GitHub marks it as a pre-release and the in-app update check still finds it.

## The normal way: tag it and GitHub does the rest
1. As you work, add a line for each change under **Unreleased** at the top of `CHANGELOG.md`. Write it for users, not developers.
2. When you're ready: `python bump_version.py 1.1.0`. It sets the version in the app and turns *Unreleased* into the `1.1.0` section.
3. Commit, tag, push:
   ```bash
   git commit -am "Release 1.1.0"
   git tag v1.1.0
   git push origin main v1.1.0
   ```
   (In GitHub Desktop: commit and push; then open the **History** tab, right-click the newest commit → **Create Tag…**, name it
   `v1.1.0`, and click **Push origin** again. Check the tag appears on GitHub under *Releases → Tags*.)
4. GitHub Actions runs the tests, builds the app, installer and extension, writes the checksums, and publishes the release with
   your changelog text. Watch it under the repository's **Actions** tab. It takes a few minutes.
5. The in-app update check then shows **Update available** to everyone on an older version, with your release notes, and shows
   **What's new** the first time they open the new version.

The workflow refuses to publish if the tag doesn't match the version inside the app, or if `CHANGELOG.md` has no section for it.

## The manual way (if Actions is unavailable)
`python make_release.py` builds everything into `release/` (including `RELEASE_NOTES_v1.1.0.md`). Then on GitHub:
*Releases → Draft a new release*, tag `v1.1.0`, paste the notes, attach the files.

## Planning what's next
Use the repository's **Issues** for ideas and bugs and **Milestones** to group them into a version (for example "1.1.0").
Label an issue `app-support` when an app doesn't work, which is usually a one-line fix to its profile.

## Signing
An unsigned installer shows Windows SmartScreen's "unknown publisher" warning. Options, cheapest first:
- **Open source:** apply to a free signing programme for open-source projects (such as SignPath Foundation). Needs a public
  repository with an OSI-approved licence and builds made by an automated process — the Release workflow above is that.
- **Microsoft Artifact Signing** (formerly Trusted Signing): about $10 a month, with an identity check. Individuals are limited
  to the US and Canada.
- **An OV code-signing certificate** from a certificate authority: roughly $150–300 a year.

Signing doesn't remove the warning instantly; Windows builds reputation for a publisher over time.
Check each provider's current terms before you buy or apply.
