<sub>[English](README.md) · [Español](README.es.md) · [Português](README.pt-BR.md) · [Français](README.fr.md) · **Deutsch** · [简体中文](README.zh-CN.md) · [日本語](README.ja.md)</sub>

# ChatBridge

**Nehmen Sie eine Unterhaltung (oder ein ganzes Code-Projekt) von einer KI-App in eine andere mit, ohne von vorn zu beginnen.**

![Lizenz: MIT](https://img.shields.io/badge/license-MIT-2dd4bf) ![Plattform: Windows 10/11](https://img.shields.io/badge/platform-Windows%2010%2F11-60a5fa) ![Läuft lokal](https://img.shields.io/badge/data-stays%20on%20your%20PC-34d399)

> Dies ist eine Übersetzung. Maßgeblich ist die englische Fassung ([README.md](README.md)). Die App gibt es vorerst nur auf Englisch, deshalb stehen die Namen der Schaltflächen auf Englisch.

Sie haben eine Unterhaltung mit einer KI begonnen und möchten sie in einer anderen fortsetzen, oder ein Projekt an ein neues Modell übergeben. Bisher hieß das: kopieren, einfügen, Kontext verlieren und alles neu erklären. ChatBridge erledigt das in drei einfachen Schritten.

![Ein kurzer Rundgang: Unterhaltung wählen, gewünschte Teile ankreuzen, Ziel wählen, und sie wird eingefügt](docs/demo.gif)

*Die Animation zeigt Beispielunterhaltungen, keine echten.*

## So funktioniert es

1. **Unterhaltung wählen**: ChatBridge listet links die Unterhaltungen auf, die es auf Ihrem PC gefunden hat (weitere lassen sich aus einer Datei oder per Einfügen von Text hinzufügen). Klicken Sie eine an, um sie zu öffnen.
2. **Ziel wählen**: rechts eine Ihrer KI-Apps (mit ihrem echten Symbol), **a website** (ChatGPT, Claude.ai, Gemini und weitere), **a file** oder einfach nur kopieren.
3. **Großen Knopf drücken**: Die App öffnet sich und die Unterhaltung wird eingefügt. **Sie lesen sie und drücken selbst Enter.**

## Funktionen

- **Findet Ihre KI-Apps**: Claude, ChatGPT, Copilot, Antigravity, lokale Modelle wie Ollama und mehr. Etwas Neues installiert? Öffnen Sie *More options* und klicken Sie auf **Look again**.
- **Websites und Dateien**: Wählen Sie eine Seite aus einer kurzen Liste, die Unterhaltung wird kopiert (und zusätzlich als Datei gespeichert, falls eine Seite lange Texte nicht annimmt); oder speichern Sie sie als Markdown, Text oder als wieder importierbare Datei.
- **Übersichtlich**: lesbare Namen, nach Datum gruppiert, mit einer Suche, die auch in die Unterhaltungen hineinschaut.
- **Findet Ihre Chats**: die auf diesem PC gespeicherten (Claude Code, Codex, Gemini CLI, LM Studio, Jan) und importiert ChatGPT- und Claude-Exporte, eingefügten Text und Markdown.
- **Web-Chats mit einem Klick speichern** mit der mitgelieferten Browser-Erweiterung (ChatGPT, Claude.ai, Gemini).
- **Nur einen Teil eines Chats übernehmen**: Eine lange Unterhaltung öffnet sich als Notizbuch aus Abschnitten, die Sie ankreuzen, umbenennen und einzeln senden können, mit einer kurzen Gliederung des Rests; sie lässt sich in einen bereits geöffneten Chat einfügen.
- **Ganze Projekte übernehmen**: Code, Markdown, YAML und andere Konfigurationsdateien, mit Ordnerbaum, Live-Größenanzeige und der Wahl zwischen *vollständigen Dateien*, *Gliederungen großer Dateien* oder *nur der Struktur*.
- **Passt auf Sie auf**: Passwörter, Schlüssel, E-Mail-Adressen und Ihr Windows-Benutzername werden automatisch ausgeblendet, und sehr lange Unterhaltungen werden nur gekürzt, wenn es nötig ist.
- **Verlauf** und **Drag and drop**; das zuletzt verwendete Ziel wird gemerkt.
- **Standardmäßig hell**, mit dunklen Farben und einer Code-Schrift unter Settings.

![Einen Projektordner mitnehmen](docs/screenshots/project.png)

> Die Screenshots verwenden Beispieldaten und Platzhalter-Symbole. Auf Ihrem PC zeigt ChatBridge das echte, von Windows übernommene Symbol jeder App.

## Installation

Laden Sie **`ChatBridge-Setup.exe`** von der Seite [Releases](../../releases) herunter und führen Sie die Datei aus. Sie wird nur für Ihr Windows-Konto installiert und braucht keine Administratorrechte. Außerdem wird ein Deinstallationsprogramm eingerichtet, erreichbar über *Settings → Apps*.

### Wenn Windows „Der Computer wurde durch Windows geschützt“ meldet
ChatBridge ist neu und noch nicht digital signiert, daher zeigt Windows SmartScreen bei jedem Programm, das es noch nicht oft gesehen hat, ein blaues oder rotes Fenster. Das heißt nicht, dass etwas nicht stimmt. Klicken Sie zum Fortfahren auf **Weitere Informationen** und dann auf **Trotzdem ausführen**. Jede Version enthält eine SHA-256-Prüfsumme (`SHA256SUMS.txt`), falls Sie den Download vorher prüfen möchten. Kostenlose Codesignierung wurde beantragt (siehe [Richtlinie zur Codesignierung](CODE_SIGNING_POLICY.md)); danach verschwindet die Warnung.

**Voraussetzungen:** Windows 10 oder 11 mit der Microsoft-Edge-WebView2-Laufzeit (unter Windows 11 bereits enthalten).

## Browser-Erweiterung (optional)

1. Öffnen Sie `edge://extensions` (oder `chrome://extensions`) und aktivieren Sie den **Entwicklermodus**.
2. Klicken Sie auf **Entpackte Erweiterung laden** und wählen Sie den Ordner `extension` (ChatBridge → Settings → *Open extension folder* öffnet ihn).
3. Klicken Sie in ChatBridge → Settings → **Browser capture** auf **Copy code** und fügen Sie den Code auf der Optionsseite der Erweiterung ein.

Danach erscheint auf ChatGPT, Claude.ai und Gemini die Schaltfläche *Save to ChatBridge*. Die Erweiterung spricht nur mit ChatBridge auf Ihrem eigenen PC, und erst nachdem Sie die Schaltfläche geklickt haben.

## Datenschutz und Sicherheit

- Alles bleibt auf Ihrem PC: kein Konto, keine Analyse, keine Server. Siehe [PRIVACY.md](PRIVACY.md).
- Die einzige Netzwerkanfrage ist eine optionale tägliche Prüfung auf eine neuere Version (abschaltbar).
- ChatBridge **drückt nie Enter** und sendet nie eine Nachricht für Sie.
- Projektordner: `.env`-Dateien, Schlüsseldateien und alle Dateien, die wie ein Schlüssel oder Passwort aussehen, werden automatisch ausgelassen.

## Aus dem Quellcode bauen

Python 3.9+ unter Windows:

```bash
pip install pywebview pyinstaller pillow
python chatbridge_app.py                      # starten
python -m unittest discover -s tests -v       # Tests
python make_release.py                        # Tests, dann App und Installer nach release/ bauen
```

## Lizenz

[MIT](LICENSE). ChatBridge ist ein unabhängiges Projekt und weder mit KI-Unternehmen verbunden noch von ihnen unterstützt. Produktnamen sind Marken ihrer jeweiligen Inhaber.
