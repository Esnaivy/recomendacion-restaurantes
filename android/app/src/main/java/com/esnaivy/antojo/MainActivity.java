package com.esnaivy.antojo;

import android.Manifest;
import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Bundle;
import android.webkit.GeolocationPermissions;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;

public class MainActivity extends Activity {
    private WebView webView;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        webView = new WebView(this);
        setContentView(webView);

        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setGeolocationEnabled(true);
        settings.setGeolocationDatabasePath(getFilesDir().getPath());

        webView.setWebViewClient(new WebViewClient() {
            @Override
            public void onPageFinished(WebView view, String url) {
                cargarCatalogoRemoto();
            }

            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                if (!request.isForMainFrame()) {
                    return false;
                }
                Uri uri = request.getUrl();
                if (uri != null && "geo".equals(uri.getScheme())) {
                    startActivity(new Intent(Intent.ACTION_VIEW, uri));
                    return true;
                }
                return false;
            }
        });

        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public void onGeolocationPermissionsShowPrompt(String origin, GeolocationPermissions.Callback callback) {
                boolean granted = checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED
                        || checkSelfPermission(Manifest.permission.ACCESS_COARSE_LOCATION) == PackageManager.PERMISSION_GRANTED;
                callback.invoke(origin, granted, false);
            }
        });

        if (checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{
                    Manifest.permission.ACCESS_FINE_LOCATION,
                    Manifest.permission.ACCESS_COARSE_LOCATION
            }, 1);
        }

        webView.loadUrl("file:///android_asset/www/index.html");
    }

    private void cargarCatalogoRemoto() {
        new Thread(() -> {
            HttpURLConnection conexion = null;
            try {
                InputStream configStream = getAssets().open("www/firebase_public.json");
                String configTexto = leer(configStream);
                JSONObject config = new JSONObject(configTexto);
                String destino = "https://firestore.googleapis.com/v1/projects/"
                        + config.getString("projectId")
                        + "/databases/" + config.getString("databaseId")
                        + "/documents:runQuery?key=" + config.getString("apiKey");
                conexion = (HttpURLConnection) new URL(destino).openConnection();
                conexion.setConnectTimeout(8000);
                conexion.setReadTimeout(8000);
                conexion.setRequestMethod("POST");
                conexion.setRequestProperty("Content-Type", "application/json");
                byte[] pedido = "{\"structuredQuery\":{\"from\":[{\"collectionId\":\"restaurantes\"}],\"limit\":300}}".getBytes(StandardCharsets.UTF_8);
                conexion.setDoOutput(true);
                conexion.getOutputStream().write(pedido);
                String cuerpo = leer(conexion.getInputStream());
                String llamada = "usarCatalogoDesdeFirestore(" + JSONObject.quote(cuerpo) + ");";
                runOnUiThread(() -> webView.evaluateJavascript(llamada, null));
            } catch (Exception ignored) {
                // El catálogo incluido en la app sigue disponible sin red.
            } finally {
                if (conexion != null) conexion.disconnect();
            }
        }).start();
    }

    private static String leer(InputStream input) throws Exception {
        BufferedReader lector = new BufferedReader(new InputStreamReader(input, StandardCharsets.UTF_8));
        StringBuilder texto = new StringBuilder();
        String linea;
        while ((linea = lector.readLine()) != null) texto.append(linea);
        lector.close();
        return texto.toString();
    }

    @Override
    public void onBackPressed() {
        if (webView != null && webView.canGoBack()) {
            webView.goBack();
            return;
        }
        super.onBackPressed();
    }
}
