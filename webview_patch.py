"""Lets pywebview's bridge between the page and Python work without eval, so the page can keep its strict
Content-Security-Policy (script-src 'self', no 'unsafe-eval': CLAUDE.md rule 3).

pywebview builds the page's API functions with `new Function(...)` and hands results back through `eval(...)`. On Windows
(WebView2) its script is added before the page's policy takes effect, so that works. On macOS and Linux it is added after the
page has loaded, the policy blocks both, and the screen can't talk to the app at all. Two small replacements fix that:
  1. api.js: each API function is an ordinary closure instead of `new Function`.
  2. Results for the page are sent with run_js (no eval wrapper) instead of evaluate_js.
tests/test_chatbridge.py checks both still fit the installed pywebview, so an update that changes them is caught by the tests.
"""
import re

_API_FN = re.compile(r"var funcBody =[\s\S]*?nestedObject\[functionName\] = new Function\([\s\S]*?\);")
_CLOSURE = """nestedObject[functionName] = (function (name) {
        return function () {
          var __id = (Math.random() + '').substring(2);
          var promise = new Promise(function (resolve, reject) {
            window.pywebview._checkValue(name, resolve, reject, __id);
          });
          window.pywebview._jsApiCallback(name, Array.prototype.slice.call(arguments), __id);
          return promise;
        };
      })(funcName);"""
_RESULT_PREFIX = "window.pywebview._returnValuesCallbacks["


def without_eval(js):
    """pywebview's injected JavaScript, with its one `new Function` replaced by a closure."""
    out, n = _API_FN.subn(lambda m: _CLOSURE, js)
    if n != 1:
        raise RuntimeError("pywebview's api.js has changed; update webview_patch.py (and the pinned pywebview version).")
    return out


def apply():
    import webview.util as util
    from webview.window import Window
    if getattr(util, "_chatbridge_no_eval", False):
        return
    original_load = util.load_js_files

    def load_js_files(window, platform):
        js, finish = original_load(window, platform)
        return without_eval(js), finish
    util.load_js_files = load_js_files

    original_evaluate = Window.evaluate_js

    def evaluate_js(self, script, callback=None):
        if callback is None and isinstance(script, str) and script.startswith(_RESULT_PREFIX):
            return self.run_js(script)              # an answer for the page: nothing comes back, so no eval wrapper is needed
        return original_evaluate(self, script, callback)
    Window.evaluate_js = evaluate_js
    util._chatbridge_no_eval = True
