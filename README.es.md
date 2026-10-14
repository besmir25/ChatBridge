<sub>[English](README.md) · **Español** · [Português](README.pt-BR.md) · [Français](README.fr.md) · [Deutsch](README.de.md) · [简体中文](README.zh-CN.md) · [日本語](README.ja.md)</sub>

# ChatBridge

**Lleva una conversación (o un proyecto de código completo) de una app de IA a otra, sin empezar de cero.**

![Licencia: MIT](https://img.shields.io/badge/license-MIT-2dd4bf) ![Plataforma: Windows 10/11](https://img.shields.io/badge/platform-Windows%2010%2F11-60a5fa) ![Funciona en local](https://img.shields.io/badge/data-stays%20on%20your%20PC-34d399)

> Esta es una traducción. La versión en inglés ([README.md](README.md)) es la de referencia. La aplicación está disponible solo en inglés por ahora, por eso los nombres de los botones aparecen en inglés.

Empezaste una conversación en una IA y quieres seguir en otra, o pasarle un proyecto a un modelo nuevo. Hoy eso significa copiar y pegar, perder contexto y volver a explicarlo todo. ChatBridge lo hace en tres pasos sencillos.

![Un recorrido corto: elige una conversación, marca las partes que quieres, elige el destino y se pega](docs/demo.gif)

*La animación usa conversaciones de ejemplo, no reales.*

## Cómo funciona

1. **Elige una conversación**: ChatBridge muestra a la izquierda las conversaciones que encontró en tu PC (puedes añadir más desde un archivo o pegando texto). Haz clic en una para abrirla.
2. **Elige dónde continuarla**: a la derecha, una de tus apps de IA (con su icono real), **a website** (ChatGPT, Claude.ai, Gemini y otras), **a file**, o simplemente copiarla.
3. **Pulsa el botón grande**: la app se abre y la conversación se coloca en su sitio. **Tú la lees y pulsas Enter.**

## Características

- **Encuentra tus apps de IA**: Claude, ChatGPT, Copilot, Antigravity, modelos locales como Ollama y más. ¿Instalaste algo nuevo? Abre *More options* y pulsa **Look again**.
- **Sitios web y archivos**: elige un sitio de una lista corta y la conversación se copia (y se guarda como archivo por si el sitio no admite un pegado largo); o guárdala como Markdown, texto o un archivo que puedes volver a importar.
- **Fácil de explorar**: nombres legibles, agrupados por fecha, con una búsqueda que mira dentro de las conversaciones.
- **Encuentra tus chats**: los guardados en este PC (Claude Code, Codex, Gemini CLI, LM Studio, Jan) e importa exportaciones de ChatGPT y Claude, texto pegado y markdown.
- **Guarda chats web con un clic** con la extensión de navegador incluida (ChatGPT, Claude.ai, Gemini).
- **Mueve solo una parte de un chat**: una conversación larga se abre como un cuaderno de secciones que puedes marcar, renombrar y enviar por separado, con un breve esquema del resto; se puede pegar en un chat que ya tengas abierto.
- **Mueve proyectos completos**: código, markdown, YAML y otros archivos de configuración, con árbol de carpetas, medidor de tamaño en vivo y la opción de *archivos completos*, *resúmenes de archivos grandes* o *solo la estructura*.
- **Cuida de ti**: contraseñas, claves, correos y tu nombre de usuario de Windows se ocultan automáticamente, y las conversaciones muy largas solo se acortan cuando hace falta.
- **Historial** y **arrastrar y soltar**; se recuerda el último destino que usaste.
- **Claro por defecto**, con colores oscuros y una fuente de estilo código en Settings.

![Llevar una carpeta de proyecto](docs/screenshots/project.png)

> Las capturas usan datos de ejemplo e iconos de relleno. En tu PC, ChatBridge muestra el icono real de cada app, tomado de Windows.

## Instalación

Descarga **`ChatBridge-Setup.exe`** desde la página de [Releases](../../releases) y ejecútalo. Se instala solo para tu cuenta de Windows y no necesita permisos de administrador. También instala un desinstalador al que accedes desde *Settings → Apps*.

### Si Windows dice «Windows protegió su PC»
ChatBridge es nuevo y todavía no está firmado digitalmente, por eso Windows SmartScreen muestra un aviso azul o rojo para cualquier programa que no ha visto muchas veces. No significa que algo vaya mal. Para continuar, haz clic en **Más información** y luego en **Ejecutar de todas formas**. Cada versión incluye una suma SHA-256 (`SHA256SUMS.txt`) por si quieres verificar la descarga antes. Se ha solicitado la firma de código gratuita (consulta la [política de firma de código](CODE_SIGNING_POLICY.md)), que eliminará el aviso.

**Requisitos:** Windows 10 u 11 con el runtime Microsoft Edge WebView2 (ya incluido en Windows 11).

## Extensión de navegador (opcional)

1. Abre `edge://extensions` (o `chrome://extensions`) y activa el **Modo de desarrollador**.
2. Haz clic en **Cargar descomprimida** y elige la carpeta `extension` (ChatBridge → Settings → *Open extension folder* la abre).
3. En ChatBridge → Settings → **Browser capture**, haz clic en **Copy code** y pégalo en la página de opciones de la extensión.

Aparecerá un botón *Save to ChatBridge* en ChatGPT, Claude.ai y Gemini. La extensión solo se comunica con ChatBridge en tu propio PC, y solo después de que pulses el botón.

## Privacidad y seguridad

- Todo se queda en tu PC: sin cuenta, sin analíticas, sin servidores. Consulta [PRIVACY.md](PRIVACY.md).
- La única petición de red es una comprobación opcional, una vez al día, de si hay una versión nueva (puedes desactivarla).
- ChatBridge **nunca pulsa Enter** ni envía ningún mensaje por ti.
- Carpetas de proyecto: los archivos `.env`, los archivos de claves y cualquier archivo que parezca contener una clave o contraseña se excluyen automáticamente.

## Compilar desde el código fuente

Python 3.9+ en Windows:

```bash
pip install pywebview pyinstaller pillow
python chatbridge_app.py                      # ejecutarlo
python -m unittest discover -s tests -v       # pruebas
python make_release.py                        # pruebas, luego compila la app y el instalador en release/
```

## Licencia

[MIT](LICENSE). ChatBridge es un proyecto independiente y no está afiliado ni respaldado por ninguna empresa de IA. Los nombres de productos son marcas de sus propietarios.
