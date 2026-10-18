package it.zeph.compagno;

import android.app.PendingIntent;
import android.content.Intent;
import android.graphics.drawable.Icon;
import android.os.Build;
import android.provider.Settings;
import android.service.quicksettings.Tile;
import android.service.quicksettings.TileService;

/** Il pulsante «Zeph» nelle Impostazioni rapide: accende e spegne Zeph al volo (o apre l'assistente, in modalità assistente). */
public class ZephTileService extends TileService {

    @Override
    public void onStartListening() {
        super.onStartListening();
        refresh(ZephService.running);
    }

    @Override
    public void onClick() {
        super.onClick();
        if (Prefs.assistantMode(this)) {
            // modalità assistente: il riquadro apre l'assistente vocale
            Intent a = new Intent(this, AssistActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            if (Build.VERSION.SDK_INT >= 34) {
                startActivityAndCollapse(PendingIntent.getActivity(this, 1, a, PendingIntent.FLAG_IMMUTABLE));
            } else {
                startActivityAndCollapseCompat(a);
            }
            return;
        }
        if (!Settings.canDrawOverlays(this)) {
            // manca il permesso: apri l'app per chiederlo
            Intent open = new Intent(this, MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            if (Build.VERSION.SDK_INT >= 34) {
                startActivityAndCollapse(PendingIntent.getActivity(this, 0, open, PendingIntent.FLAG_IMMUTABLE));
            } else {
                startActivityAndCollapseCompat(open);
            }
            return;
        }
        boolean on = ZephService.running;
        Intent i = new Intent(this, ZephService.class).setAction(on ? ZephService.ACTION_STOP : ZephService.ACTION_START);
        if (on) startService(i);
        else startForegroundService(i);
        refresh(!on);
    }

    @SuppressWarnings("deprecation")
    private void startActivityAndCollapseCompat(Intent open) {
        startActivityAndCollapse(open);
    }

    private void refresh(boolean on) {
        Tile t = getQsTile();
        if (t == null) return;
        boolean assist = Prefs.assistantMode(this);
        t.setIcon(Icon.createWithResource(this, R.drawable.ic_stat_zeph));
        t.setLabel(Prefs.petName(this));
        if (Build.VERSION.SDK_INT >= 29) t.setSubtitle(assist ? "Assistente" : on ? "Sullo schermo" : "Spento");
        t.setState(assist || on ? Tile.STATE_ACTIVE : Tile.STATE_INACTIVE);
        t.updateTile();
    }
}
