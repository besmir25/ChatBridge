<sub>[English](README.md) · [Español](README.es.md) · [Português](README.pt-BR.md) · **Français** · [Deutsch](README.de.md) · [简体中文](README.zh-CN.md) · [日本語](README.ja.md)</sub>

# ChatBridge

**Déplacez une conversation (ou tout un projet de code) d'une application d'IA à une autre, sans repartir de zéro.**

![Licence : MIT](https://img.shields.io/badge/license-MIT-2dd4bf) ![Plateforme : Windows 10/11](https://img.shields.io/badge/platform-Windows%2010%2F11-60a5fa) ![Fonctionne en local](https://img.shields.io/badge/data-stays%20on%20your%20PC-34d399)

> Ceci est une traduction. La version anglaise ([README.md](README.md)) fait foi. L'application existe aussi en français : elle choisit seule selon la langue de Windows, ou dans **Settings → Language**. Ici, les noms des boutons restent en anglais ; dans l'application, vous les verrez dans votre langue.

Vous avez commencé une conversation avec une IA et vous voulez la continuer dans une autre, ou confier un projet à un nouveau modèle. Aujourd'hui, cela veut dire copier-coller, perdre le contexte et tout réexpliquer. ChatBridge le fait en trois étapes simples.

![Un court aperçu : choisissez une conversation, cochez les parties voulues, choisissez la destination, et elle est collée](docs/demo.gif)

*L'animation utilise des conversations d'exemple, pas de vraies conversations.*

## Comment ça marche

1. **Choisissez une conversation** : ChatBridge liste à gauche les conversations trouvées sur votre PC (vous pouvez en ajouter depuis un fichier ou en collant du texte). Cliquez sur l'une d'elles pour l'ouvrir.
2. **Choisissez où la poursuivre** : à droite, l'une de vos applications d'IA (avec sa vraie icône), **a website** (ChatGPT, Claude.ai, Gemini et d'autres), **a file**, ou simplement la copier.
3. **Appuyez sur le gros bouton** : l'application s'ouvre et la conversation y est placée. **Vous la lisez et appuyez vous-même sur Entrée.**

## Fonctionnalités

- **Trouve vos applications d'IA** : Claude, ChatGPT, Copilot, Antigravity, modèles locaux comme Ollama, et plus. Vous venez d'en installer une ? Ouvrez *More options* et cliquez sur **Look again**.
- **Sites web et fichiers** : choisissez un site dans une courte liste et la conversation est copiée (et enregistrée en fichier au cas où le site n'accepterait pas un long collage) ; ou enregistrez-la en Markdown, en texte ou dans un fichier réimportable.
- **Facile à parcourir** : des noms lisibles, regroupés par date, avec une recherche qui fouille dans les conversations.
- **Trouve vos conversations** : celles stockées sur ce PC (Claude Code, Codex, Gemini CLI, LM Studio, Jan), et importe les exports de ChatGPT et Claude, le texte collé et le markdown.
- **Enregistre les conversations web en un clic** grâce à l'extension de navigateur incluse (ChatGPT, Claude.ai, Gemini).
- **Déplace seulement une partie d'une conversation** : une longue conversation s'ouvre comme un carnet de sections que vous pouvez cocher, renommer et envoyer séparément, avec un bref plan du reste ; elle peut être collée dans une conversation déjà ouverte.
- **Déplace des projets entiers** : code, markdown, YAML et autres fichiers de configuration, avec arborescence, jauge de taille en direct et le choix entre *fichiers complets*, *aperçus des gros fichiers* ou *structure seule*.
- **Veille sur vous** : mots de passe, clés, e-mails et votre nom d'utilisateur Windows sont masqués automatiquement, et les conversations très longues ne sont raccourcies que si nécessaire.
- **Historique** et **glisser-déposer** ; la dernière destination utilisée est mémorisée.
- **Thème clair par défaut**, avec des couleurs sombres et une police de style code dans Settings.

![Emporter un dossier de projet](docs/screenshots/project.png)

> Les captures utilisent des données d'exemple et des icônes de substitution. Sur votre PC, ChatBridge affiche la vraie icône de chaque application, récupérée depuis Windows.

## Installation

Téléchargez **`ChatBridge-Setup.exe`** depuis la page [Releases](../../releases) et lancez-le. Il s'installe uniquement pour votre compte Windows et ne demande aucun droit d'administrateur. Il installe aussi un désinstalleur accessible depuis *Settings → Apps*.

### Si Windows affiche « Windows a protégé votre ordinateur »
ChatBridge est récent et n'est pas encore signé numériquement ; Windows SmartScreen affiche donc un cadre bleu ou rouge pour tout programme qu'il n'a pas vu souvent. Cela ne signifie pas qu'il y a un problème. Pour continuer, cliquez sur **Informations complémentaires**, puis sur **Exécuter quand même**. Chaque version fournit une somme SHA-256 (`SHA256SUMS.txt`) pour vérifier le téléchargement au préalable. Une signature de code gratuite a été demandée (voir la [politique de signature de code](CODE_SIGNING_POLICY.md)), ce qui supprimera l'avertissement.

**Prérequis :** Windows 10 ou 11 avec le runtime Microsoft Edge WebView2 (déjà inclus dans Windows 11).

## Extension de navigateur (facultative)

1. Ouvrez `edge://extensions` (ou `chrome://extensions`) et activez le **Mode développeur**.
2. Cliquez sur **Charger l'extension non empaquetée** et choisissez le dossier `extension` (ChatBridge → Settings → *Open extension folder* l'ouvre).
3. Dans ChatBridge → Settings → **Browser capture**, cliquez sur **Copy code**, puis collez-le dans la page d'options de l'extension.

Un bouton *Save to ChatBridge* apparaît alors sur ChatGPT, Claude.ai et Gemini. L'extension ne communique qu'avec ChatBridge sur votre propre PC, et seulement après votre clic sur le bouton.

## Confidentialité et sécurité

- Tout reste sur votre PC : pas de compte, pas d'analyse d'usage, pas de serveurs. Voir [PRIVACY.md](PRIVACY.md).
- La seule requête réseau est une vérification facultative, une fois par jour, de la présence d'une version plus récente (désactivable).
- ChatBridge **n'appuie jamais sur Entrée** et n'envoie jamais de message à votre place.
- Dossiers de projet : les fichiers `.env`, les fichiers de clés et tout fichier qui semble contenir une clé ou un mot de passe sont exclus automatiquement.

## Compiler depuis les sources

Python 3.9+ sous Windows :

```bash
pip install pywebview pyinstaller pillow
python chatbridge_app.py                      # lancer l'application
python -m unittest discover -s tests -v       # tests
python make_release.py                        # tests, puis compile l'application et l'installateur dans release/
```

## Licence

[MIT](LICENSE). ChatBridge est un projet indépendant, non affilié à une entreprise d'IA ni approuvé par elle. Les noms de produits sont des marques de leurs propriétaires.
