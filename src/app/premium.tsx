import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { router, useLocalSearchParams } from 'expo-router';
import { useEffect, useState } from 'react';
import { ScrollView, StyleSheet, View } from 'react-native';
import Animated, { FadeInDown, ZoomIn } from 'react-native-reanimated';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { LOGO_COLORS, MaikMark } from '@/components/MaikLogo';
import { useToast } from '@/components/Toast';
import { AppText, Button, haptic, IconButton, Tap, type IconName } from '@/components/ui';
import { notify } from '@/lib/confirm';
import { getPlans, purchase, purchasesConfigured, restore, type Plan } from '@/lib/purchases';
import { DEMO_PLANS, FREE_LIMIT } from '@/lib/purchases-types';
import { MaxWidth } from '@/lib/theme';
import { useApp } from '@/state/app';

export default function PremiumScreen() {
  const { reason } = useLocalSearchParams<{ reason?: string }>();
  const { palette, t, isPremium, setPremium } = useApp();
  const toast = useToast();
  const insets = useSafeAreaInsets();
  const [plans, setPlans] = useState<Plan[]>(DEMO_PLANS);
  const [selected, setSelected] = useState('yearly');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    getPlans().then((p) => {
      setPlans(p);
      setSelected(p.find((x) => x.kind === 'yearly')?.id ?? p[0]?.id ?? 'yearly');
    });
  }, []);

  const features: { icon: IconName; title: string; body: string }[] = [
    { icon: 'infinite', title: t('featUnlimited'), body: t('featUnlimitedBody', { n: FREE_LIMIT }) },
    { icon: 'notifications', title: t('featReminders'), body: t('featRemindersBody') },
    { icon: 'people', title: t('featFamily'), body: t('featFamilyBody') },
    { icon: 'stats-chart', title: t('featStats'), body: t('featStatsBody') },
    { icon: 'color-palette', title: t('featThemes'), body: t('featThemesBody') },
    { icon: 'download', title: t('featBackup'), body: t('featBackupBody') },
  ];

  const buy = async () => {
    setBusy(true);
    const res = await purchase(selected);
    setBusy(false);
    if (res.ok && res.premium) {
      setPremium(true);
      haptic('success');
      toast({ message: t('premiumActive') });
      router.back();
    } else if (!res.ok && !res.cancelled) {
      notify(t('purchaseError'), res.message);
    }
  };

  const doRestore = async () => {
    setBusy(true);
    const res = await restore();
    setBusy(false);
    if (res) {
      setPremium(true);
      toast({ message: t('premiumActive') });
      router.back();
    } else if (res === false) {
      notify(t('purchaseError'));
    }
  };

  const planTitle = (p: Plan) => (p.kind === 'monthly' ? t('planMonthly') : p.kind === 'yearly' ? t('planYearly') : t('planLifetime'));

  return (
    <View style={{ flex: 1, backgroundColor: palette.background }}>
      <ScrollView contentContainerStyle={{ paddingBottom: insets.bottom + 200 }}>
        <LinearGradient colors={[LOGO_COLORS.from, LOGO_COLORS.to]} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={[styles.hero, { paddingTop: insets.top + 16 }]}>
          <View style={styles.close}>
            <IconButton icon="close" label={t('cancel')} onPress={() => router.back()} background="rgba(255,255,255,0.2)" tint="#fff" />
          </View>
          <Animated.View entering={ZoomIn.springify().damping(12)}>
            <MaikMark size={92} />
          </Animated.View>
          <AppText variant="hero" style={{ color: '#fff', textAlign: 'center' }}>
            {t('premiumTitle')}
          </AppText>
          <AppText variant="body" style={{ color: 'rgba(255,255,255,0.85)', textAlign: 'center' }}>
            {reason === 'limit' ? t('limitReached', { n: FREE_LIMIT }) : t('premiumSubtitle')}
          </AppText>
        </LinearGradient>

        <View style={styles.body}>
          {features.map((f, i) => (
            <Animated.View key={f.title} entering={FadeInDown.delay(80 + i * 50)} style={styles.feature}>
              <View style={[styles.featureIcon, { backgroundColor: palette.accentSoft }]}>
                <Ionicons name={f.icon} size={20} color={palette.accent} />
              </View>
              <View style={{ flex: 1 }}>
                <AppText variant="bodyBold">{f.title}</AppText>
                <AppText variant="caption" tone="secondary">
                  {f.body}
                </AppText>
              </View>
            </Animated.View>
          ))}

          {isPremium ? (
            <View style={[styles.activeBox, { backgroundColor: palette.accentSoft }]}>
              <Ionicons name="checkmark-circle" size={28} color={palette.accent} />
              <AppText variant="heading" tone="accent">
                {t('premiumActive')}
              </AppText>
            </View>
          ) : (
            <View style={{ gap: 10, marginTop: 8 }}>
              {plans.map((p) => {
                const sel = p.id === selected;
                return (
                  <Tap
                    key={p.id}
                    hapticKind="select"
                    onPress={() => setSelected(p.id)}
                    accessibilityRole="radio"
                    accessibilityState={{ selected: sel }}
                    style={[styles.plan, { backgroundColor: palette.card, borderColor: sel ? palette.accent : palette.border }]}>
                    <Ionicons name={sel ? 'radio-button-on' : 'radio-button-off'} size={22} color={sel ? palette.accent : palette.textTertiary} />
                    <View style={{ flex: 1 }}>
                      <AppText variant="bodyBold">{planTitle(p)}</AppText>
                      {p.pricePerMonth && p.kind === 'yearly' ? (
                        <AppText variant="caption" tone="secondary">
                          {p.pricePerMonth} / {t('perMonth')}
                        </AppText>
                      ) : null}
                    </View>
                    {p.kind === 'yearly' && (
                      <View style={[styles.best, { backgroundColor: palette.accent }]}>
                        <AppText variant="tiny" tone="onAccent">
                          {t('bestValue')}
                        </AppText>
                      </View>
                    )}
                    <AppText variant="heading">{p.priceString}</AppText>
                  </Tap>
                );
              })}
            </View>
          )}

          {!purchasesConfigured && (
            <AppText variant="caption" tone="tertiary" style={{ textAlign: 'center' }}>
              {t('demoMode')}
            </AppText>
          )}
        </View>
      </ScrollView>

      {!isPremium && (
        <View style={[styles.footer, { paddingBottom: insets.bottom + 12, backgroundColor: palette.background, borderTopColor: palette.border }]}>
          <View style={styles.inner}>
            <Button title={t('subscribe')} icon="sparkles" onPress={buy} loading={busy} />
            <Tap onPress={doRestore} hapticKind={false} style={{ alignSelf: 'center', padding: 6 }}>
              <AppText variant="caption" tone="accent" style={{ fontWeight: '700' }}>
                {t('restore')}
              </AppText>
            </Tap>
            <AppText variant="tiny" tone="tertiary" style={{ textAlign: 'center' }}>
              {t('legal')}
            </AppText>
          </View>
        </View>
      )}
      {isPremium && !purchasesConfigured && (
        <View style={[styles.footer, { paddingBottom: insets.bottom + 12, backgroundColor: palette.background, borderTopColor: palette.border }]}>
          <View style={styles.inner}>
            <Button title={t('demoDisable')} variant="secondary" onPress={() => setPremium(false)} />
          </View>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  hero: { alignItems: 'center', gap: 12, paddingHorizontal: 24, paddingBottom: 32, borderBottomLeftRadius: 36, borderBottomRightRadius: 36 },
  close: { alignSelf: 'flex-end' },
  body: { padding: 20, gap: 14, width: '100%', maxWidth: MaxWidth, alignSelf: 'center' },
  feature: { flexDirection: 'row', alignItems: 'center', gap: 14 },
  featureIcon: { width: 42, height: 42, borderRadius: 13, alignItems: 'center', justifyContent: 'center' },
  plan: { flexDirection: 'row', alignItems: 'center', gap: 12, padding: 16, borderRadius: 20, borderWidth: 2 },
  best: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 8 },
  activeBox: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 10, padding: 20, borderRadius: 20, marginTop: 8 },
  footer: { position: 'absolute', left: 0, right: 0, bottom: 0, paddingHorizontal: 20, paddingTop: 12, borderTopWidth: StyleSheet.hairlineWidth },
  inner: { width: '100%', maxWidth: MaxWidth, alignSelf: 'center', gap: 6 },
});
