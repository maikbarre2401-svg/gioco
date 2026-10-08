package it.zeph.compagno;

import android.app.Activity;
import android.content.Intent;
import android.os.Bundle;
import android.provider.Settings;
import android.widget.Toast;

/**
 * «Condividi → Zeph» da qualsiasi app (messaggi, articoli, note…):
 * Zeph legge il testo ad alta voce. Non ha schermata: passa il testo e si chiude.
 */
public class ShareActivity extends Activity {
    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        Intent in = getIntent();
        CharSequence text = in != null ? in.getCharSequenceExtra(Intent.EXTRA_TEXT) : null;
        if (text == null || text.toString().trim().isEmpty()) {
            Toast.makeText(this, "Non c'è niente da leggere", Toast.LENGTH_SHORT).show();
        } else if (!Settings.canDrawOverlays(this)) {
            Toast.makeText(this, "Prima apri Zeph e dagli il permesso di apparire sopra le app", Toast.LENGTH_LONG).show();
        } else {
            String t = text.toString().trim();
            if (t.length() > 3800) t = t.substring(0, 3800); // limite della sintesi vocale
            startForegroundService(new Intent(this, ZephService.class)
                .setAction(ZephService.ACTION_READ)
                .putExtra(ZephService.EXTRA_TEXT, t));
        }
        finish();
    }
}
