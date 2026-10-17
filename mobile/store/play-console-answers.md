# Google Play Console: answers to the forms

Written for the app as it is in this repository. Re-check each answer if the app changes (especially permissions and anything that goes online).

## App access
All functionality is available without logging in. No special access instructions needed.

## Ads
No, the app contains no ads.

## Content rating (IARC questionnaire)
Category: **Utility, Productivity, Communication or Other** (not a game, not social media, no user-to-user messaging).
Answer **No** to violence, sexual content, language, controlled substances, gambling, user-generated content shared with others, location sharing and purchases. Expected rating: **Everyone / PEGI 3**.
(The app moves text the user already has to apps the user chooses; it hosts no content.)

## Target audience
**18 and over** is the safe choice (the app is for people who use AI chat tools; it is not designed for children). Do not select "appeals to children".

## News app / COVID / government / financial / health
No to all.

## Data safety
- **Does your app collect or share any of the required user data types?** → **No.**
  Nothing leaves the device by the app: no network permission, no analytics or advertising SDK, no servers, no crash reporter.
- **Is all of the user data collected by your app encrypted in transit?** → Not applicable (nothing is collected or transmitted).
- **Do you provide a way for users to request that their data be deleted?** → Not applicable. Data stays on the device; deleting a conversation or uninstalling the app removes it.
- **Privacy policy URL:** https://github.com/besmir25/ChatBridge/blob/main/PRIVACY.md (the "The Android app" section applies)

Note on "sharing": when the user presses the big button, the app hands text to an app, website or share sheet **the user picked**. Google's definition of "sharing" excludes user-initiated transfers to a service the user chose, so this does not count as the app sharing data. If Google's reviewers ask, point to that wording and to the privacy policy.

## Permissions the app declares
None (no `uses-permission` entries). The manifest has a `<queries>` list of 8 AI app package names (ChatGPT, Claude, Gemini, Copilot, Perplexity, Grok, DeepSeek, Le Chat) so it can show which are installed.
This is **not** the `QUERY_ALL_PACKAGES` permission, so no special declaration is required.

## Sensitive APIs
Accessibility service: no. SMS/call log: no. Background location: no. Photos/videos: no. Foreground services: no. Full-screen intents: no. Exact alarms: no.
Clipboard: the app writes to the clipboard when the user presses a button, and reads it only when the user taps "Paste what I copied".

## Target API level
Targets Android 16 (API 36), which Google requires for new apps from August 31, 2026. Minimum Android 7.0 (API 24).

## App signing
Use **Play App Signing** (the default). Upload the `.aab` signed with your upload key (kept outside the repo; see KEEP-THIS-SAFE.txt next to the key). Google keeps the real signing key.

## Release steps
1. `powershell -ExecutionPolicy Bypass -File mobile\build-release.ps1` creates `ChatBridge-<version>.aab`.
2. Play Console → Testing → **Internal testing** → Create release → upload the `.aab` → add yourself as a tester → install from the opt-in link and try it on a real phone.
3. Fill in the forms above, the store listing (`listing.md`), the graphics, then promote to **Production**.
4. New personal developer accounts (created after Nov 2023) must first run a **closed test with 12+ testers for 14 days** before Production access is granted. Start this early; ask friends to join the test.
