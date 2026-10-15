<sub>[English](README.md) · [Español](README.es.md) · [Português](README.pt-BR.md) · [Français](README.fr.md) · [Deutsch](README.de.md) · **简体中文** · [日本語](README.ja.md)</sub>

# ChatBridge

**把一段对话（或整个代码项目）从一个 AI 应用带到另一个，无需从头再来。**

![许可证：MIT](https://img.shields.io/badge/license-MIT-2dd4bf) ![平台：Windows 10/11](https://img.shields.io/badge/platform-Windows%2010%2F11-60a5fa) ![本地运行](https://img.shields.io/badge/data-stays%20on%20your%20PC-34d399)

> 这是翻译版本，以英文版（[README.md](README.md)）为准。应用也提供简体中文界面：会根据 Windows 的语言自动选择，也可在 **Settings → Language** 中更改。这里的按钮名称保留英文，在应用中你会看到中文。

你在一个 AI 里开始了一段对话，想在另一个 AI 里继续，或者把项目交给新的模型。过去这意味着复制粘贴、丢失上下文、把一切重新解释一遍。ChatBridge 用三个简单的步骤帮你完成。

![简短演示：选择对话、勾选想要的部分、选择去向，然后自动粘贴](docs/demo.gif)

*动画使用的是示例对话，不是真实对话。*

## 使用方法

1. **选择一段对话**：ChatBridge 会在左侧列出它在你电脑上找到的对话（也可以从文件添加，或粘贴文本）。点击其中一个即可打开。
2. **选择在哪里继续**：在右侧选择你的某个 AI 应用（显示其真实图标）、**a website**（ChatGPT、Claude.ai、Gemini 等）、**a file**，或者只是复制。
3. **点击大按钮**：应用打开，对话被放到位。**你自己阅读并按 Enter 发送。**

## 功能

- **找到你的 AI 应用**：Claude、ChatGPT、Copilot、Antigravity、Ollama 等本地模型，等等。刚装了新应用？打开 *More options* 并点击 **Look again**。
- **网站和文件**：从简短列表中选一个网站，对话会被复制（并保存为文件，以防网站无法接受很长的粘贴）；也可以保存为 Markdown、文本或可重新导入的文件。
- **易于浏览**：名称易读，按日期分组，搜索可以查到对话内部的内容。
- **找到你的聊天记录**：保存在这台电脑上的（Claude Code、Codex、Gemini CLI、LM Studio、Jan），并支持导入 ChatGPT 和 Claude 的导出、粘贴的文本和 Markdown。
- **一键保存网页聊天**：使用随附的浏览器扩展（ChatGPT、Claude.ai、Gemini）。
- **只带走聊天的一部分**：长对话会以分节笔记本的形式打开，你可以勾选、重命名并单独发送各节，并附上其余部分的简短大纲；还可以粘贴到你已经打开的聊天中。
- **带走整个项目**：代码、Markdown、YAML 和其他配置文件，带有文件夹树、实时大小指示，可选择*完整文件*、*大文件的提纲*或*仅结构*。
- **帮你把关**：密码、密钥、电子邮件和你的 Windows 用户名会被自动隐藏，非常长的对话只在需要时才会被缩短。
- **历史记录**和**拖放**；会记住你上次使用的去向。
- **默认浅色**，在 Settings 中可选深色和代码风格字体。

![带上一个项目文件夹](docs/screenshots/project.png)

> 截图使用示例数据和占位图标。在你的电脑上，ChatBridge 会显示从 Windows 获取的每个应用的真实图标。

## 安装

从 [Releases](../../releases) 页面下载 **`ChatBridge-Setup.exe`** 并运行。它只为你的 Windows 账户安装，不需要管理员权限，并会安装一个卸载程序，可在 *Settings → Apps* 中找到。

### 如果 Windows 提示“Windows 已保护你的电脑”
ChatBridge 是新软件，尚未进行代码签名，所以对任何 Windows SmartScreen 见得不多的程序，它都会弹出蓝色或红色的提示框。这并不表示有问题。要继续，请点击**更多信息**，然后点击**仍要运行**。每个版本都附有 SHA-256 校验值（`SHA256SUMS.txt`），方便你先验证下载文件。我们已申请免费代码签名（见[代码签名政策](CODE_SIGNING_POLICY.md)），获批后该提示将会消失。

**系统要求：** Windows 10 或 11，并安装 Microsoft Edge WebView2 运行时（Windows 11 已内置）。

## 浏览器扩展（可选）

1. 打开 `edge://extensions`（或 `chrome://extensions`）并开启**开发者模式**。
2. 点击**加载已解压的扩展程序**，选择 `extension` 文件夹（ChatBridge → Settings → *Open extension folder* 可直接打开）。
3. 在 ChatBridge → Settings → **Browser capture** 中点击 **Copy code**，然后粘贴到扩展的选项页面。

之后 ChatGPT、Claude.ai 和 Gemini 上会出现 *Save to ChatBridge* 按钮。扩展只与你自己电脑上的 ChatBridge 通信，并且只在你点击按钮之后才会通信。

## 隐私与安全

- 一切都留在你的电脑上：没有账号、没有统计分析、没有服务器。见 [PRIVACY.md](PRIVACY.md)。
- 唯一的网络请求是可选的、每天一次的新版本检查（可以关闭）。
- ChatBridge **从不按 Enter**，也从不替你发送消息。
- 项目文件夹：`.env` 文件、密钥文件以及任何看起来包含密钥或密码的文件都会被自动排除。

## 从源码构建

Windows 上的 Python 3.9+：

```bash
pip install pywebview pyinstaller pillow
python chatbridge_app.py                      # 运行
python -m unittest discover -s tests -v       # 测试
python make_release.py                        # 先测试，再把应用和安装程序构建到 release/
```

## 许可证

[MIT](LICENSE)。ChatBridge 是独立项目，与任何 AI 公司没有隶属或背书关系。产品名称是其各自所有者的商标。
