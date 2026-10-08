package it.zeph.compagno;

import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.graphics.Color;
import android.graphics.drawable.GradientDrawable;
import android.os.Bundle;
import android.speech.RecognizerIntent;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.KeyEvent;
import android.view.inputmethod.EditorInfo;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

import java.util.ArrayList;

/** La finestrella per scrivere o PARLARE a Zeph (microfono del telefono). */
public class ChatActivity extends Activity {
    static final String EXTRA_MIC = "mic";
    private static final int REQ_MIC = 11;
    private EditText input;

    private int dp(float v) {
        return Math.round(TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, v, getResources().getDisplayMetrics()));
    }

    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setPadding(dp(18), dp(16), dp(18), dp(14));
        box.setBackgroundColor(0xFF101827);

        TextView title = new TextView(this);
        title.setText("Parla con " + Prefs.petName(this));
        title.setTextColor(0xFF5EEAD4);
        title.setTextSize(TypedValue.COMPLEX_UNIT_SP, 18);
        box.addView(title);

        TextView hint = new TextView(this);
        hint.setText("Raccontami la tua giornata, oppure prova: «apri whatsapp», «balla», «cosa sai di me?», «ricordami tra 5 minuti della pizza»");
        hint.setTextColor(0x99FFFFFF);
        hint.setTextSize(TypedValue.COMPLEX_UNIT_SP, 12);
        hint.setPadding(0, dp(4), 0, dp(10));
        box.addView(hint);

        input = new EditText(this);
        input.setHint("Scrivi qualcosa…");
        input.setTextColor(Color.WHITE);
        input.setHintTextColor(0x66FFFFFF);
        input.setSingleLine(true);
        input.setImeOptions(EditorInfo.IME_ACTION_SEND);
        input.setOnEditorActionListener((v, id, ev) -> {
            boolean enter = ev != null && ev.getKeyCode() == KeyEvent.KEYCODE_ENTER && ev.getAction() == KeyEvent.ACTION_DOWN;
            if (id == EditorInfo.IME_ACTION_SEND || enter) { send(input.getText().toString()); return true; }
            return false;
        });
        box.addView(input, new LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT));

        LinearLayout row = new LinearLayout(this);
        row.setOrientation(LinearLayout.HORIZONTAL);
        row.setGravity(Gravity.END);
        row.setPadding(0, dp(10), 0, 0);
        Button mic = button("🎤 Parla", 0xFF334155);
        mic.setOnClickListener(v -> listen());
        Button go = button("Invia", 0xFF14B8A6);
        go.setOnClickListener(v -> send(input.getText().toString()));
        row.addView(mic);
        LinearLayout.LayoutParams gp = new LinearLayout.LayoutParams(LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        gp.leftMargin = dp(10);
        row.addView(go, gp);
        box.addView(row);

        setContentView(box);
        if (getWindow() != null) {
            getWindow().setLayout(Math.min(dp(380), getResources().getDisplayMetrics().widthPixels - dp(24)),
                LinearLayout.LayoutParams.WRAP_CONTENT);
        }
        if (getIntent().getBooleanExtra(EXTRA_MIC, false) && b == null) listen();
    }

    private Button button(String text, int color) {
        Button btn = new Button(this);
        btn.setText(text);
        btn.setAllCaps(false);
        btn.setTextColor(Color.WHITE);
        GradientDrawable bg = new GradientDrawable();
        bg.setColor(color);
        bg.setCornerRadius(dp(10));
        btn.setBackground(bg);
        btn.setPadding(dp(18), 0, dp(18), 0);
        return btn;
    }

    private void listen() {
        Intent i = new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH)
            .putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            .putExtra(RecognizerIntent.EXTRA_LANGUAGE, "it-IT")
            .putExtra(RecognizerIntent.EXTRA_PROMPT, "Parla con Zeph…");
        try {
            startActivityForResult(i, REQ_MIC);
        } catch (ActivityNotFoundException e) {
            Toast.makeText(this, "Il riconoscimento vocale non è disponibile: installa l'app Google", Toast.LENGTH_LONG).show();
        }
    }

    @Override
    protected void onActivityResult(int req, int res, Intent data) {
        super.onActivityResult(req, res, data);
        if (req != REQ_MIC || res != RESULT_OK || data == null) return;
        ArrayList<String> said = data.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS);
        if (said != null && !said.isEmpty()) send(said.get(0));
    }

    private void send(String text) {
        text = text == null ? "" : text.trim();
        if (text.isEmpty()) return;
        Intent i = new Intent(this, ZephService.class)
            .setAction(ZephService.ACTION_CHAT)
            .putExtra(ZephService.EXTRA_TEXT, text);
        startForegroundService(i);
        finish();
    }
}
