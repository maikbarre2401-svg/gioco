import { Ionicons } from '@expo/vector-icons';
import Constants from 'expo-constants';
import * as LocalAuthentication from 'expo-local-authentication';
import { router } from 'expo-router';
import { useState } from 'react';
import { Platform, ScrollView, Share, StyleSheet, View } from 'react-native';

import { MaikLogo } from '@/components/MaikLogo';
import { Screen } from '@/components/Screen';
import { useToast } from '@/components/Toast';
import { AppText, Card, Chip, Input, PremiumBadge, Row, Segmented, Tap, Toggle } from '@/components/ui';
import { buildBackup, buildCsv, parseBackup } from '@/lib/backup';
import { confirm, notify } from '@/lib/confirm';
import { pickTextFile, shareTextFile } from '@/lib/files';
import { cycleLabel, reminderLabel } from '@/lib/i18n';
import { CURRENCIES, monthlyCost, parsePrice } from '@/lib/money';
import { notificationsSupported, requestPermission, sendTestNotification } from '@/lib/notifications';
import { ACCENTS } from '@/lib/theme';
import type { Language, ThemeMode } from '@/lib/types';
import { useApp } from '@/state/app';

const HOURS = [7, 8, 9, 12, 18, 20, 21];

export default function SettingsScreen() {
  const app = useApp();
  const { settings, updateSettings, palette, t, isPremium, subscriptions, money, replaceAll, loadSample, resetAll } = app;
  const toast = useToast();
  const [budgetText, setBudgetText] = useState(settings.monthlyBudget ? String(settings.monthlyBudget) : '');

  const requirePremium = (fn: () => void) => () => (isPremium ? fn() : router.push('/premium'));

  const toggleNotifications = async (v: boolean) => {
    if (v && notificationsSupported) {
      const ok = await requestPermission(t);
      if (!ok) notify(t('notificationsDenied'));
    }
    updateSettings({ notificationsEnabled: v });
  };

  const toggleBiometric = async (v: boolean) => {
    if (v) {
      const available = Platform.OS !== 'web' && (await LocalAuthentication.hasHardwareAsync()) && (await LocalAuthentication.isEnrolledAsync());
      if (!available) {
        notify(t('biometricUnavailable'));
        return;
      }
      const res = await LocalAuthentication.authenticateAsync({ promptMessage: t('biometricLock') });
      if (!res.success) return;
    }
    updateSettings({ biometricLock: v });
  };

  const exportJson = () => shareTextFile(`maik-subs-backup-${new Date().toISOString().slice(0, 10)}.json`, buildBackup(subscriptions, settings.family), 'application/json').catch(() => {});

  const exportCsv = requirePremium(() => {
    shareTextFile('maik-subs.csv', buildCsv(subscriptions, (s) => monthlyCost(s)), 'text/csv').catch(() => {});
  });

  const importJson = async () => {
    const text = await pickTextFile().catch(() => null);
    if (!text) return;
    const data = parseBackup(text);
    if (!data) {
      notify(t('importError'));
      return;
    }
    // Merge by id: imported entries replace existing ones with the same id.
    const ids = new Set(data.subscriptions.map((s) => s.id));
    replaceAll([...data.subscriptions, ...subscriptions.filter((s) => !ids.has(s.id))]);
    const memberIds = new Set(settings.family.map((m) => m.id));
    updateSettings({ family: [...settings.family, ...data.family.filter((m) => !memberIds.has(m.id))] });
    toast({ message: t('importDone', { n: data.subscriptions.length }) });
  };

  const shareSummary = () => {
    const active = subscriptions.filter((s) => s.status === 'active');
    const total = active.reduce((a, s) => a + monthlyCost(s), 0);
    const lines = active
      .sort((a, b) => monthlyCost(b) - monthlyCost(a))
      .map((s) => `• ${s.name}: ${money(s.price)} (${cycleLabel(t, s.cycle.unit, s.cycle.every)})`);
    const message = [
      t('summaryHeader', { n: active.length }),
      '',
      ...lines,
      '',
      t('summaryTotal', { month: money(total), year: money(total * 12) }),
      '',
      `— ${t('appName')}`,
    ].join('\n');
    Share.share({ message }).catch(() => {});
  };

  const reset = async () => {
    if (await confirm(t('resetData'), t('resetConfirm'), t('delete'), t('cancel'))) await resetAll();
  };

  return (
    <Screen>
      <AppText variant="title">{t('settingsTitle')}</AppText>

      {/* Premium status */}
      <Tap onPress={() => router.push('/premium')}>
        <Card style={[styles.premium, { backgroundColor: isPremium ? palette.accentSoft : palette.card, borderColor: palette.accent + '44' }]}>
          <View style={[styles.premiumIcon, { backgroundColor: palette.accent }]}>
            <Ionicons name="sparkles" size={22} color={palette.onAccent} />
          </View>
          <View style={{ flex: 1 }}>
            <AppText variant="heading">{isPremium ? t('premiumActive') : t('upgrade')}</AppText>
            <AppText variant="caption" tone="secondary">
              {isPremium ? t('premiumSubtitle') : t('premiumBannerBody')}
            </AppText>
          </View>
          <Ionicons name="chevron-forward" size={18} color={palette.textTertiary} />
        </Card>
      </Tap>

      {/* Appearance */}
      <Section title={t('appearance')}>
        <Label text={t('theme')} />
        <Segmented<ThemeMode>
          value={settings.theme}
          onChange={(theme) => updateSettings({ theme })}
          options={[
            { value: 'system', label: t('themeSystem') },
            { value: 'light', label: t('themeLight') },
            { value: 'dark', label: t('themeDark') },
          ]}
        />
        <Label text={t('accentColor')} pro={!isPremium} />
        <View style={styles.swatches}>
          {ACCENTS.map((c) => (
            <Tap
              key={c}
              hapticKind="select"
              accessibilityLabel={c}
              onPress={requirePremium(() => updateSettings({ accent: c }))}
              style={[styles.swatch, { backgroundColor: c, borderColor: palette.accent === c ? palette.text : 'transparent' }]}>
              {palette.accent === c && <Ionicons name="checkmark" size={18} color="#fff" />}
            </Tap>
          ))}
        </View>
        <Label text={t('language')} />
        <Segmented<Language>
          value={settings.language}
          onChange={(language) => updateSettings({ language })}
          options={[
            { value: 'system', label: t('languageSystem') },
            { value: 'it', label: 'Italiano' },
            { value: 'en', label: 'English' },
          ]}
        />
      </Section>

      {/* Money */}
      <Section title={t('currency')}>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 8 }}>
          {CURRENCIES.map((c) => (
            <Chip key={c} label={c} selected={settings.currency === c} onPress={() => updateSettings({ currency: c })} />
          ))}
        </ScrollView>
        <Label text={t('monthlyBudget')} />
        <Input
          value={budgetText}
          onChangeText={setBudgetText}
          onBlur={() => {
            const v = parsePrice(budgetText);
            updateSettings({ monthlyBudget: v > 0 ? v : null });
            if (!(v > 0)) setBudgetText('');
          }}
          placeholder={t('budgetNone')}
          keyboardType="decimal-pad"
          returnKeyType="done"
        />
      </Section>

      {/* Notifications */}
      <Section title={t('notifications')}>
        <Row icon="notifications" title={t('notificationsEnabled')} right={<Toggle value={settings.notificationsEnabled} onValueChange={toggleNotifications} />} />
        {!notificationsSupported && (
          <AppText variant="caption" tone="secondary">
            {t('notificationsWeb')}
          </AppText>
        )}
        <Label text={t('defaultReminder')} />
        <View style={styles.wrap}>
          {[0, 1, 3, 7].map((d) => (
            <Chip
              key={d}
              label={reminderLabel(t, d)}
              selected={settings.defaultReminderDays.includes(d)}
              onPress={() => updateSettings({ defaultReminderDays: [d] })}
            />
          ))}
        </View>
        <Label text={t('reminderTime')} pro={!isPremium} />
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 8 }}>
          {HOURS.map((h) => (
            <Chip
              key={h}
              label={`${String(h).padStart(2, '0')}:00`}
              selected={(isPremium ? settings.reminderHour : 9) === h}
              onPress={requirePremium(() => updateSettings({ reminderHour: h }))}
            />
          ))}
        </ScrollView>
        {notificationsSupported && (
          <Row
            icon="paper-plane"
            title={t('testNotification')}
            last
            onPress={async () => {
              const ok = await sendTestNotification(t);
              toast({ message: ok ? t('testSent') : t('notificationsDenied') });
            }}
          />
        )}
      </Section>

      {/* Family */}
      <Section title={t('family')}>
        <Row
          icon="people"
          title={t('family')}
          subtitle={settings.family.length ? settings.family.map((m) => m.name).join(', ') : t('familyBody')}
          right={!isPremium ? <PremiumBadge /> : undefined}
          onPress={requirePremium(() => router.push('/family'))}
        />
        <Row
          icon="pie-chart"
          title={t('showMyShare')}
          last
          right={<Toggle value={isPremium && settings.showMyShare} onValueChange={(v) => (isPremium ? updateSettings({ showMyShare: v }) : router.push('/premium'))} />}
        />
      </Section>

      {/* Privacy */}
      <Section title={t('security')}>
        <Row icon="finger-print" title={t('biometricLock')} right={<Toggle value={settings.biometricLock} onValueChange={toggleBiometric} />} />
        <Row icon="image" title={t('showLogos')} subtitle={t('showLogosBody')} last right={<Toggle value={settings.showLogos} onValueChange={(v) => updateSettings({ showLogos: v })} />} />
      </Section>

      {/* Data */}
      <Section title={t('data')}>
        <Row icon="cloud-download" title={t('exportBackup')} onPress={exportJson} />
        <Row icon="cloud-upload" title={t('importBackup')} onPress={importJson} />
        <Row icon="grid" title={t('exportCsv')} right={!isPremium ? <PremiumBadge /> : undefined} onPress={exportCsv} />
        <Row icon="share-social" title={t('shareSummary')} onPress={shareSummary} />
        <Row icon="flask" title={t('loadSample')} onPress={loadSample} />
        <Row icon="trash" title={t('resetData')} danger last onPress={reset} />
      </Section>

      {/* About */}
      <Card style={styles.about}>
        <MaikLogo size={52} textColor={palette.text} subtitle={t('madeBy')} />
        <AppText variant="body" tone="secondary" style={{ textAlign: 'center', lineHeight: 21 }}>
          {t('privacyNote')}
        </AppText>
        <AppText variant="caption" tone="tertiary">
          {t('version')} {Constants.expoConfig?.version ?? '1.0.0'} · © {new Date().getFullYear()} Maik
        </AppText>
      </Card>
    </Screen>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <View style={{ gap: 10 }}>
      <AppText variant="label" tone="secondary" style={{ marginLeft: 4 }}>
        {title}
      </AppText>
      <Card style={{ gap: 10, paddingVertical: 8 }}>{children}</Card>
    </View>
  );
}

function Label({ text, pro }: { text: string; pro?: boolean }) {
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 8 }}>
      <AppText variant="bodyBold">{text}</AppText>
      {pro && <PremiumBadge />}
    </View>
  );
}

const styles = StyleSheet.create({
  premium: { flexDirection: 'row', alignItems: 'center', gap: 14, borderWidth: 1 },
  premiumIcon: { width: 48, height: 48, borderRadius: 16, alignItems: 'center', justifyContent: 'center' },
  swatches: { flexDirection: 'row', gap: 10, flexWrap: 'wrap' },
  swatch: { width: 42, height: 42, borderRadius: 14, borderWidth: 3, alignItems: 'center', justifyContent: 'center' },
  wrap: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  about: { alignItems: 'center', gap: 14, paddingVertical: 28 },
});
