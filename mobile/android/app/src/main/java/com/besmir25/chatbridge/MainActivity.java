package com.besmir25.chatbridge;

import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.webkit.JavascriptInterface;
import androidx.core.view.WindowCompat;
import androidx.core.view.WindowInsetsControllerCompat;
import com.getcapacitor.BridgeActivity;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;

/**
 * Receives text (or a small text/json file) that another app shares to ChatBridge and hands it to the page.
 * The text is only ever kept in memory until the page asks for it, and it never leaves the phone.
 */
public class MainActivity extends BridgeActivity {
    private static final int MAX_BYTES = 5_000_000;
    private String pendingShare = null;

    @Override
    public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        grab(getIntent());
        getBridge().getWebView().addJavascriptInterface(new Object() {
            @JavascriptInterface
            public String takeShared() {
                String t = pendingShare;
                pendingShare = null;
                return t == null ? "" : t;
            }

            /** The page tells us whether it is showing its dark look, so the area behind the status and navigation bars matches it
             *  (Android 15+ draws apps edge to edge; on older web views a white strip would otherwise show) and the clock and icons stay readable. */
            @JavascriptInterface
            public void setTheme(final boolean dark) {
                runOnUiThread(() -> {
                    getWindow().getDecorView().setBackgroundColor(dark ? 0xFF0E1116 : 0xFFFBF8F4);
                    WindowInsetsControllerCompat controller = WindowCompat.getInsetsController(getWindow(), getWindow().getDecorView());
                    controller.setAppearanceLightStatusBars(!dark);
                    controller.setAppearanceLightNavigationBars(!dark);
                });
            }
        }, "ChatBridgeNative");
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        grab(intent);
        getBridge().getWebView().post(() ->
            getBridge().getWebView().evaluateJavascript("window.dispatchEvent(new Event('sharedtext'))", null));
    }

    private void grab(Intent intent) {
        if (intent == null || !Intent.ACTION_SEND.equals(intent.getAction())) return;
        String text = intent.getStringExtra(Intent.EXTRA_TEXT);
        if (text != null && text.length() > MAX_BYTES) text = text.substring(0, MAX_BYTES);
        if (text == null || text.isEmpty()) {
            Uri uri = intent.getParcelableExtra(Intent.EXTRA_STREAM);
            if (uri != null && "content".equals(uri.getScheme())) text = readText(uri);      // a file:// address would let the sender point us at our own files
        }
        if (text != null && !text.isEmpty()) pendingShare = text;
    }

    private String readText(Uri uri) {
        try (InputStream in = getContentResolver().openInputStream(uri)) {
            if (in == null) return null;
            ByteArrayOutputStream out = new ByteArrayOutputStream();
            byte[] buf = new byte[16384];
            int n;
            while (out.size() < MAX_BYTES && (n = in.read(buf, 0, Math.min(buf.length, MAX_BYTES - out.size()))) > 0) out.write(buf, 0, n);
            return new String(out.toByteArray(), StandardCharsets.UTF_8);
        } catch (Exception e) {
            return null;
        }
    }
}
