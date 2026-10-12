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

## Before every release: the test pass

Automated (must be green): `python -W ignore -m unittest discover -s tests`, then once with `CHATBRIDGE_GUI_TESTS=1`.

By hand, on the built app (`dist\ChatBridge\ChatBridge.exe`) — about 15 minutes:

1. **Starts and looks right.** Window opens, no blank area, list fills in, no flash of a dark page.
2. **Each desktop app you support**, once with the app *already open* and once *fully closed*:
   - whole conversation → the app opens, the text is pasted, **nothing is sent** (Enter is never pressed)
   - just part of a conversation (tick a section and a single message)
   - "Add it to the chat that's already open" with a chat open
3. **A website** (pick two from the list), **A file** (save, then open the saved file), **Just copy it** (paste into Notepad).
4. **Add from a file** with a ChatGPT export and a Claude export; **Paste text**; **Bring a code project** (check `.env` is left out).
5. **Browser extension** on ChatGPT, Claude.ai and Gemini: the Save button appears and the chat arrives. (These sites change their pages often.)
6. **Settings**: change theme, text size, text style; turn "hide private details" off and back on; Check now.
7. **Help → Copy a problem report**: paste it somewhere and confirm it has no conversation text.
8. **Install** the release installer over the previous version (settings and conversations are kept), then **uninstall**.
9. **Clean machine or second Windows account**: install, start, and check the empty-list message makes sense.
10. Look at the changelog entry: plain words, no jargon.

If any step fails, fix it first. Don't tag a release with a known broken step.

