<sub>[English](README.md) · [Español](README.es.md) · [Português](README.pt-BR.md) · [Français](README.fr.md) · [Deutsch](README.de.md) · [简体中文](README.zh-CN.md) · **日本語**</sub>

# ChatBridge

**会話（またはコードプロジェクト全体）を、最初からやり直さずに、ある AI アプリから別の AI アプリへ引き継げます。**

![ライセンス: MIT](https://img.shields.io/badge/license-MIT-2dd4bf) ![プラットフォーム: Windows 10/11](https://img.shields.io/badge/platform-Windows%2010%2F11-60a5fa) ![ローカルで動作](https://img.shields.io/badge/data-stays%20on%20your%20PC-34d399)

> これは翻訳版です。正式な内容は英語版（[README.md](README.md)）です。アプリも日本語で使えます。Windows の言語に合わせて自動で選ばれ、**Settings → Language** で変更もできます。ここではボタン名を英語のまま記載していますが、アプリ内では日本語で表示されます。

ある AI で始めた会話を別の AI で続けたい、あるいはプロジェクトを新しいモデルに渡したい。これまではコピー＆ペーストをして、文脈を失い、最初から説明し直す必要がありました。ChatBridge なら、3 つの簡単なステップで済みます。

![短いデモ: 会話を選び、必要な部分にチェックを入れ、送り先を選ぶと、貼り付けられます](docs/demo.gif)

*アニメーションはサンプルの会話であり、実際の会話ではありません。*

## 使い方

1. **会話を選ぶ**: ChatBridge が PC 上で見つけた会話を左側に一覧表示します（ファイルやテキストの貼り付けで追加もできます）。開きたい会話をクリックします。
2. **続ける場所を選ぶ**: 右側で、お使いの AI アプリ（本物のアイコン付き）、**a website**（ChatGPT、Claude.ai、Gemini など）、**a file**、またはコピーのみを選びます。
3. **大きなボタンを押す**: アプリが開き、会話がセットされます。**内容を確認して、Enter は自分で押します。**

## 機能

- **AI アプリを自動で検出**: Claude、ChatGPT、Copilot、Antigravity、Ollama などのローカルモデルなど。新しくインストールした場合は、*More options* を開いて **Look again** を押してください。
- **ウェブサイトとファイル**: 短い一覧からサイトを選ぶと会話がコピーされます（長い貼り付けを受け付けないサイトのために、ファイルとしても保存されます）。Markdown、テキスト、再インポート可能なファイルとして保存することもできます。
- **見やすい一覧**: 読みやすい名前、日付ごとのグループ分け、会話の中身まで調べる検索。
- **チャットを自動で検出**: この PC に保存されているもの（Claude Code、Codex、Gemini CLI、LM Studio、Jan）に加え、ChatGPT と Claude のエクスポート、貼り付けたテキスト、Markdown を取り込めます。
- **ウェブのチャットをワンクリックで保存**: 付属のブラウザ拡張機能を使います（ChatGPT、Claude.ai、Gemini）。
- **チャットの一部だけを移す**: 長い会話はセクションごとのノートとして開き、チェック、名前の変更、個別の送信ができます。残りの部分の短いアウトライン付きで、すでに開いているチャットに貼り付けることもできます。
- **プロジェクト全体を移す**: コード、Markdown、YAML などの設定ファイルを、フォルダツリー、リアルタイムのサイズ表示、*ファイル全体*・*大きなファイルの概要*・*構造のみ*の選択とともに扱えます。
- **あなたを守る**: パスワード、キー、メールアドレス、Windows のユーザー名は自動的に隠され、非常に長い会話は必要なときだけ短縮されます。
- **履歴**と**ドラッグ＆ドロップ**。最後に使った送り先も記憶されます。
- **既定は明るい配色**。Settings で暗い配色とコード風フォントを選べます。

![プロジェクトフォルダを引き継ぐ](docs/screenshots/project.png)

> スクリーンショットはサンプルデータと仮のアイコンを使用しています。お使いの PC では、ChatBridge が Windows から取得した各アプリ本来のアイコンを表示します。

## インストール

[Releases](../../releases) ページから **`ChatBridge-Setup.exe`** をダウンロードして実行してください。お使いの Windows アカウント用にのみインストールされ、管理者権限は不要です。アンインストーラーも追加され、*Settings → Apps* から開けます。

### 「Windows によって PC が保護されました」と表示されたら
ChatBridge は新しいソフトで、まだコード署名されていないため、Windows SmartScreen は見慣れないプログラムすべてに青または赤の画面を表示します。何か問題があるという意味ではありません。続けるには、**詳細情報**をクリックし、**実行**をクリックします。各リリースには SHA-256 チェックサム（`SHA256SUMS.txt`）が付いており、先にダウンロードを確認できます。無料のコード署名を申請済みで（[コード署名ポリシー](CODE_SIGNING_POLICY.md)を参照）、承認されればこの警告は表示されなくなります。

**動作環境:** Windows 10 または 11、および Microsoft Edge WebView2 ランタイム（Windows 11 には標準で含まれています）。

## ブラウザ拡張機能（任意）

1. `edge://extensions`（または `chrome://extensions`）を開き、**デベロッパー モード**をオンにします。
2. **パッケージ化されていない拡張機能を読み込む**をクリックし、`extension` フォルダを選びます（ChatBridge → Settings → *Open extension folder* で開けます）。
3. ChatBridge → Settings → **Browser capture** で **Copy code** をクリックし、拡張機能のオプションページに貼り付けます。

ChatGPT、Claude.ai、Gemini に *Save to ChatBridge* ボタンが表示されます。拡張機能はあなた自身の PC 上の ChatBridge とだけ通信し、ボタンをクリックした後にのみ通信します。

## プライバシーと安全性

- すべてあなたの PC 内にとどまります。アカウント、アクセス解析、サーバーはありません。[PRIVACY.md](PRIVACY.md) を参照してください。
- 唯一のネットワーク通信は、新しいバージョンがあるかを 1 日 1 回確認する任意のチェックです（オフにできます）。
- ChatBridge は **Enter を押さず**、あなたの代わりにメッセージを送信することもありません。
- プロジェクトフォルダ: `.env` ファイル、キーファイル、キーやパスワードを含むと思われるファイルは自動的に除外されます。

## ソースからビルドする

Windows 上の Python 3.9 以降:

```bash
pip install pywebview pyinstaller pillow
python chatbridge_app.py                      # 実行
python -m unittest discover -s tests -v       # テスト
python make_release.py                        # テスト後、アプリとインストーラーを release/ にビルド
```

## ライセンス

[MIT](LICENSE)。ChatBridge は独立したプロジェクトであり、いかなる AI 企業とも提携しておらず、承認も受けていません。製品名はそれぞれの所有者の商標です。
