import * as LocalAuthentication from 'expo-local-authentication';
import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react';
import { AppState, Platform, StyleSheet, View } from 'react-native';

import { useApp } from '@/state/app';

import { MaikMark } from './MaikLogo';
import { AppText, Button } from './ui';

/** Hides the app behind Face ID / fingerprint when the lock is enabled. */
export function LockGate({ children }: { children: ReactNode }) {
  const { settings, palette, t } = useApp();
  const enabled = settings.biometricLock && Platform.OS !== 'web';
  const [unlocked, setUnlocked] = useState(!enabled);
  const busy = useRef(false);

  const authenticate = useCallback(async () => {
    if (busy.current) return;
    busy.current = true;
    try {
      const res = await LocalAuthentication.authenticateAsync({ promptMessage: t('unlock') });
      if (res.success) setUnlocked(true);
    } finally {
      busy.current = false;
    }
  }, [t]);

  useEffect(() => {
    if (!enabled) return;
    // When the lock was just turned on in settings the user is already authenticated.
    if (!unlocked) authenticate();
    const sub = AppState.addEventListener('change', (state) => {
      if (state === 'background') setUnlocked(false);
      if (state === 'active') authenticate();
    });
    return () => sub.remove();
    // Only re-run when the lock is turned on or off.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled]);

  if (!enabled || unlocked) return <>{children}</>;

  return (
    <View style={[styles.lock, { backgroundColor: palette.background }]}>
      <MaikMark size={84} />
      <AppText variant="heading">{t('locked')}</AppText>
      <Button title={t('unlock')} icon="lock-open" onPress={authenticate} style={{ alignSelf: 'stretch' }} />
    </View>
  );
}

const styles = StyleSheet.create({
  lock: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 20, padding: 32 },
});
