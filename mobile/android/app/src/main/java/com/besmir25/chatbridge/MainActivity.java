package com.besmir25.chatbridge;

import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.webkit.JavascriptInterface;
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
        if (text == null || text.isEmpty()) {
            Uri uri = intent.getParcelableExtra(Intent.EXTRA_STREAM);
            if (uri != null) text = readText(uri);
        }
        if (text != null && !text.isEmpty()) pendingShare = text;
    }

    private String readText(Uri uri) {
        try (InputStream in = getContentResolver().openInputStream(uri)) {
            if (in == null) return null;
            ByteArrayOutputStream out = new ByteArrayOutputStream();
            byte[] buf = new byte[16384];
            int n;
            while ((n = in.read(buf)) > 0 && out.size() < MAX_BYTES) out.write(buf, 0, n);
            return new String(out.toByteArray(), StandardCharsets.UTF_8);
        } catch (Exception e) {
            return null;
        }
    }
}
