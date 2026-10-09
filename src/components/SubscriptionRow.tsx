import { router } from 'expo-router';
import { StyleSheet, View } from 'react-native';

import { daysUntil, isInTrial, nextRenewal, parseISODate } from '@/lib/dates';
import { cycleLabel } from '@/lib/i18n';
import { effectivePrice } from '@/lib/money';
import type { Subscription } from '@/lib/types';
import { useApp } from '@/state/app';

import { ServiceLogo } from './ServiceLogo';
import { AppText, Tap } from './ui';

export function useRenewalText() {
  const { t } = useApp();
  return (days: number) => (days <= 0 ? t('today') : days === 1 ? t('tomorrow') : t('inDays', { n: days }));
}

export function SubscriptionRow({ sub }: { sub: Subscription }) {
  const { palette, t, money, settings, locale } = useApp();
  const renewalText = useRenewalText();
  const next = nextRenewal(sub);
  const days = next ? daysUntil(next) : null;
  const trial = isInTrial(sub);
  const price = effectivePrice(sub, settings.showMyShare, settings.family);
  const lastPrice = sub.priceHistory[sub.priceHistory.length - 1]?.price;
  const priceUp = lastPrice !== undefined && lastPrice < sub.price;
  const urgent = days !== null && days <= 3;

  let status: string;
  if (sub.status === 'paused') status = t('paused');
  else if (sub.status === 'cancelled') status = t('cancelled');
  else status = days !== null ? renewalText(days) : '';

  const dateText = next ? next.toLocaleDateString(locale, { day: 'numeric', month: 'short' }) : sub.statusDate ? parseISODate(sub.statusDate).toLocaleDateString(locale, { day: 'numeric', month: 'short' }) : '';

  return (
    <Tap
      onPress={() => router.push(`/subscription/${sub.id}`)}
      accessibilityRole="button"
      accessibilityLabel={`${sub.name}, ${money(price)}, ${status}`}
      style={[styles.row, { backgroundColor: palette.card, borderColor: palette.border, opacity: sub.status === 'active' ? 1 : 0.6 }]}>
      <ServiceLogo name={sub.name} color={sub.color} domain={sub.domain} serviceId={sub.serviceId} size={48} />
      <View style={styles.middle}>
        <AppText variant="bodyBold" numberOfLines={1}>
          {sub.name}
        </AppText>
        <View style={styles.metaRow}>
          {trial && <Pill text={t('trial')} color={palette.warning} />}
          {sub.sharedWith.length > 0 && <Pill text={t('shared')} color={palette.accent} />}
          {priceUp && <Pill text={`↑ ${t('priceUp')}`} color={palette.danger} />}
          <AppText variant="caption" tone="secondary" numberOfLines={1} style={{ flexShrink: 1 }}>
            {cycleLabel(t, sub.cycle.unit, sub.cycle.every)}
            {dateText ? ` · ${dateText}` : ''}
          </AppText>
        </View>
      </View>
      <View style={styles.right}>
        <AppText variant="bodyBold">{money(price)}</AppText>
        <AppText
          variant="caption"
          style={{ color: sub.status !== 'active' ? palette.textTertiary : urgent ? palette.danger : trial ? palette.warning : palette.textSecondary, fontWeight: urgent || trial ? '700' : '500' }}>
          {status}
        </AppText>
      </View>
    </Tap>
  );
}

export function Pill({ text, color }: { text: string; color: string }) {
  return (
    <View style={[styles.pill, { backgroundColor: color + '22' }]}>
      <AppText variant="tiny" style={{ color }}>
        {text}
      </AppText>
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 14,
    padding: 14,
    borderRadius: 22,
    borderWidth: StyleSheet.hairlineWidth,
  },
  middle: { flex: 1, gap: 4 },
  metaRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  right: { alignItems: 'flex-end', gap: 4 },
  pill: { paddingHorizontal: 6, paddingVertical: 2, borderRadius: 6 },
});
