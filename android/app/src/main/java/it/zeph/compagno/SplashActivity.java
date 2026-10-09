package it.zeph.compagno;

import android.animation.ValueAnimator;
import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.graphics.Canvas;
import android.graphics.DashPathEffect;
import android.graphics.LinearGradient;
import android.graphics.Paint;
import android.graphics.RadialGradient;
import android.graphics.Shader;
import android.graphics.Typeface;
import android.graphics.drawable.Drawable;
import android.os.Build;
import android.os.Bundle;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.View;
import android.view.animation.DecelerateInterpolator;
import android.view.animation.OvershootInterpolator;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.TextView;

/**
 * La schermata d'avvio: il logo di Zeph che si accende, il nome e, sotto,
 * «creator MaikGost». Dopo un paio di secondi (o con un tocco) si apre l'app.
 */
public class SplashActivity extends Activity {
    private static final long DURATION = 2600;
    private boolean opened;
    private ValueAnimator clock;

    private float dp(float v) {
        return TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, v, getResources().getDisplayMetrics());
    }

    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        getWindow().setStatusBarColor(0xFF0F1726);
        getWindow().setNavigationBarColor(0xFF0F1726);

        FrameLayout root = new FrameLayout(this);
        root.setBackgroundColor(0xFF0F1726);
        LogoView logo = new LogoView(this);
        root.addView(logo, new FrameLayout.LayoutParams(FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.MATCH_PARENT));

        // nome e motto, sotto il logo
        LinearLayout words = new LinearLayout(this);
        words.setOrientation(LinearLayout.VERTICAL);
        words.setGravity(Gravity.CENTER_HORIZONTAL);
        TextView title = new TextView(this);
        title.setText("ZEPH");
        title.setTextColor(0xFFEAF2FF);
        title.setTextSize(TypedValue.COMPLEX_UNIT_SP, 40);
        title.setTypeface(Typeface.create("sans-serif-light", Typeface.BOLD));
        title.setLetterSpacing(0.42f);
        title.setGravity(Gravity.CENTER);
        words.addView(title);
        TextView motto = new TextView(this);
        motto.setText("il tuo amico 3D");
        motto.setTextColor(0x995EEAD4);
        motto.setTextSize(TypedValue.COMPLEX_UNIT_SP, 14);
        motto.setLetterSpacing(0.18f);
        motto.setGravity(Gravity.CENTER);
        words.addView(motto);
        FrameLayout.LayoutParams wp = new FrameLayout.LayoutParams(FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.WRAP_CONTENT, Gravity.CENTER);
        wp.topMargin = Math.round(dp(150));
        root.addView(words, wp);

        // la firma in basso: «creator MaikGost»
        LinearLayout sign = new LinearLayout(this);
        sign.setOrientation(LinearLayout.VERTICAL);
        sign.setGravity(Gravity.CENTER_HORIZONTAL);
        TextView by = new TextView(this);
        by.setText("creator");
        by.setTextColor(0x88EAF2FF);
        by.setTextSize(TypedValue.COMPLEX_UNIT_SP, 12);
        by.setLetterSpacing(0.35f);
        by.setAllCaps(true);
        by.setGravity(Gravity.CENTER);
        sign.addView(by);
        TextView name = new TextView(this) {
            @Override protected void onSizeChanged(int w, int h, int ow, int oh) {
                super.onSizeChanged(w, h, ow, oh);
                // scritta sfumata turchese → azzurro → viola
                getPaint().setShader(new LinearGradient(0, 0, w, 0,
                    new int[]{0xFF5EEAD4, 0xFF38BDF8, 0xFFA78BFA}, null, Shader.TileMode.CLAMP));
            }
        };
        name.setText("MaikGost");
        name.setTextSize(TypedValue.COMPLEX_UNIT_SP, 26);
        name.setTypeface(Typeface.DEFAULT_BOLD);
        name.setLetterSpacing(0.06f);
        name.setGravity(Gravity.CENTER);
        name.setShadowLayer(dp(10), 0, 0, 0x6638BDF8);
        sign.addView(name, new LinearLayout.LayoutParams(LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT));
        FrameLayout.LayoutParams sp = new FrameLayout.LayoutParams(FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.WRAP_CONTENT,
            Gravity.BOTTOM | Gravity.CENTER_HORIZONTAL);
        sp.bottomMargin = Math.round(dp(64));
        root.addView(sign, sp);

        setContentView(root);
        root.setOnClickListener(v -> openApp()); // un tocco: si salta l'introduzione

        // entrate: il logo «esplode» con un rimbalzo, poi il nome, poi la firma
        logo.setScaleX(0.55f); logo.setScaleY(0.55f); logo.setAlpha(0f);
        logo.animate().scaleX(1f).scaleY(1f).alpha(1f).setDuration(700).setInterpolator(new OvershootInterpolator(1.6f)).start();
        words.setAlpha(0f); words.setTranslationY(dp(14));
        words.animate().alpha(1f).translationY(0).setStartDelay(420).setDuration(600).setInterpolator(new DecelerateInterpolator()).start();
        sign.setAlpha(0f); sign.setTranslationY(dp(24));
        sign.animate().alpha(1f).translationY(0).setStartDelay(900).setDuration(700).setInterpolator(new DecelerateInterpolator()).start();

        clock = ValueAnimator.ofFloat(0f, 1f);
        clock.setDuration(DURATION);
        clock.addUpdateListener(a -> logo.setProgress((float) a.getAnimatedValue(), a.getCurrentPlayTime()));
        clock.addListener(new android.animation.AnimatorListenerAdapter() {
            @Override public void onAnimationEnd(android.animation.Animator a) { openApp(); }
        });
        clock.start();
    }

    private void openApp() {
        if (opened) return;
        opened = true;
        if (clock != null) clock.cancel();
        startActivity(new Intent(this, MainActivity.class));
        if (Build.VERSION.SDK_INT >= 34) {
            overrideActivityTransition(OVERRIDE_TRANSITION_OPEN, android.R.anim.fade_in, android.R.anim.fade_out);
        } else {
            fadeLegacy();
        }
        finish();
    }

    @SuppressWarnings("deprecation")
    private void fadeLegacy() { overridePendingTransition(android.R.anim.fade_in, android.R.anim.fade_out); }

    /** Il logo: anelli che girano, un alone che pulsa, la faccia di Zeph e una barra di caricamento. */
    private final class LogoView extends View {
        private final Paint ring = new Paint(Paint.ANTI_ALIAS_FLAG);
        private final Paint dash = new Paint(Paint.ANTI_ALIAS_FLAG);
        private final Paint glow = new Paint(Paint.ANTI_ALIAS_FLAG);
        private final Paint bar = new Paint(Paint.ANTI_ALIAS_FLAG);
        private final Paint dot = new Paint(Paint.ANTI_ALIAS_FLAG);
        private final Drawable face;
        private float progress;
        private long ms;

        LogoView(Context c) {
            super(c);
            ring.setStyle(Paint.Style.STROKE);
            ring.setStrokeWidth(dp(3));
            ring.setColor(0xFF5EEAD4);
            dash.setStyle(Paint.Style.STROKE);
            dash.setStrokeWidth(dp(2));
            dash.setColor(0xAA38BDF8);
            dash.setPathEffect(new DashPathEffect(new float[]{dp(14), dp(9)}, 0));
            bar.setStrokeCap(Paint.Cap.ROUND);
            bar.setStrokeWidth(dp(3));
            dot.setColor(0xFF5EEAD4);
            face = c.getDrawable(R.drawable.ic_launcher_fg);
        }

        void setProgress(float p, long playMs) {
            progress = p;
            ms = playMs;
            invalidate();
        }

        @Override
        protected void onDraw(Canvas cv) {
            float cx = getWidth() / 2f, cy = getHeight() / 2f - dp(40);
            float r = dp(78);
            double t = ms / 1000.0;
            // alone che respira
            float pulse = (float) (0.85 + 0.15 * Math.sin(t * 3.2));
            glow.setShader(new RadialGradient(cx, cy, r * 2.1f * pulse, new int[]{0x6614B8A6, 0x2238BDF8, 0x00000000}, new float[]{0f, 0.55f, 1f}, Shader.TileMode.CLAMP));
            cv.drawCircle(cx, cy, r * 2.1f * pulse, glow);
            // anello pieno che si disegna man mano, e anello tratteggiato che gira al contrario
            float sweep = Math.min(1f, progress * 2.2f) * 360f;
            cv.save();
            cv.rotate((float) (t * 90), cx, cy);
            cv.drawArc(cx - r, cy - r, cx + r, cy + r, -90, sweep, false, ring);
            cv.restore();
            cv.save();
            cv.rotate((float) (-t * 60), cx, cy);
            float r2 = r + dp(14);
            cv.drawCircle(cx, cy, r2, dash);
            cv.restore();
            // tre puntini in orbita
            for (int k = 0; k < 3; k++) {
                double a = t * 2.1 + k * 2.094;
                dot.setAlpha(170 + (int) (85 * Math.sin(t * 4 + k)));
                cv.drawCircle(cx + (float) Math.cos(a) * r2, cy + (float) Math.sin(a) * r2, dp(3.2f), dot);
            }
            // la faccia di Zeph
            if (face != null) {
                int s = Math.round(r * 1.9f);
                face.setBounds(Math.round(cx - s / 2f), Math.round(cy - s / 2f), Math.round(cx + s / 2f), Math.round(cy + s / 2f));
                face.draw(cv);
            }
            // barra di caricamento sotto la firma
            float w = dp(120), y = getHeight() - dp(40);
            bar.setShader(null);
            bar.setColor(0x22FFFFFF);
            cv.drawLine(cx - w / 2, y, cx + w / 2, y, bar);
            bar.setShader(new LinearGradient(cx - w / 2, y, cx + w / 2, y, 0xFF5EEAD4, 0xFFA78BFA, Shader.TileMode.CLAMP));
            cv.drawLine(cx - w / 2, y, cx - w / 2 + w * progress, y, bar);
        }
    }
}
