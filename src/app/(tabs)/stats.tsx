import { Ionicons } from '@expo/vector-icons';
import { router } from 'expo-router';
import { useState } from 'react';
import { StyleSheet, View } from 'react-native';
import Animated, { FadeInDown } from 'react-native-reanimated';

import { BarChart, DonutChart, ProgressBar } from '@/components/Charts';
import { Screen } from '@/components/Screen';
import { ServiceLogo } from '@/components/ServiceLogo';
import { AppText, Card, PremiumBadge, Segmented, Tap } from '@/components/ui';
import { categoryInfo } from '@/lib/catalog';
import { addMonths, chargesBetween, endOfMonth, isInTrial, startOfMonth, today } from '@/lib/dates';
import { categoryLabel } from '@/lib/i18n';
import { effectivePrice, monthlyCost } from '@/lib/money';
import type { CategoryId } from '@/lib/types';
import { useApp } from '@/state/app';

export default function StatsScreen() {
  const { subscriptions, palette, t, money, locale, settings, isPremium } = useApp();
  const [range, setRange] = useState<'next' | 'last'>('next');
  const { showMyShare, family } = settings;

  const active = subscriptions.filter((s) => s.status === 'active');
  const monthTotal = active.reduce((a, s) => a + monthlyCost(s, showMyShare, family), 0);

  const categoryTotals = new Map<CategoryId, number>();
  for (const s of active) categoryTotals.set(s.category, (categoryTotals.get(s.category) ?? 0) + monthlyCost(s, showMyShare, family));
  const byCategory = [...categoryTotals.entries()]
    .map(([id, value]) => ({ key: id, value, color: categoryInfo(id).color }))
    .sort((a, b) => b.value - a.value);

  const base = startOfMonth(today());
  const months = Array.from({ length: 12 }, (_, i) => {
    const m = addMonths(base, range === 'next' ? i : i - 11, 1);
    const value = subscriptions.reduce(
      (a, s) => a + chargesBetween(s, startOfMonth(m), endOfMonth(m)).length * effectivePrice(s, showMyShare, family),
      0,
    );
    return { label: m.toLocaleDateString(locale, { month: 'narrow' }), value };
  });

  const top = [...active].sort((a, b) => monthlyCost(b) - monthlyCost(a)).slice(0, 5);
  const trials = active.filter((s) => isInTrial(s));

  const insights: string[] = [];
  if (top[0] && monthTotal > 0) {
    insights.push(t('insightTop', { name: top[0].name, pct: Math.round((monthlyCost(top[0], showMyShare, family) / monthTotal) * 100) }));
  }
  const monthlyBig = active.filter((s) => s.cycle.unit === 'month' && s.cycle.every === 1 && s.price >= 9).sort((a, b) => b.price - a.price)[0];
  if (monthlyBig) insights.push(t('insightYearly', { name: monthlyBig.name }));
  if (trials.length) insights.push(t('insightTrials', { n: trials.length }));
  if (settings.monthlyBudget && monthTotal > settings.monthlyBudget) {
    insights.push(t('insightBudget', { amount: money(monthTotal - settings.monthlyBudget) }));
  }

  if (active.length === 0) {
    return (
      <Screen>
        <AppText variant="title">{t('statsTitle')}</AppText>
        <Card style={{ alignItems: 'center', gap: 12, paddingVertical: 40 }}>
          <Ionicons name="pie-chart-outline" size={48} color={palette.textTertiary} />
          <AppText variant="body" tone="secondary" style={{ textAlign: 'center' }}>
            {t('statsEmpty')}
          </AppText>
        </Card>
      </Screen>
    );
  }

  const showLocked = range === 'last' && !isPremium;

  return (
    <Screen>
      <AppText variant="title">{t('statsTitle')}</AppText>

      <View style={styles.grid}>
        <Kpi label={t('monthlyTotal')} value={money(monthTotal)} big />
        <Kpi label={t('yearlyTotal')} value={money(monthTotal * 12)} big />
        <Kpi label={t('dailyCost')} value={money(monthTotal / 30.436875)} />
        <Kpi label={t('average')} value={money(monthTotal / active.length)} />
      </View>

      <Animated.View entering={FadeInDown.duration(400)}>
        <Card>
          <AppText variant="heading" style={{ marginBottom: 16 }}>
            {t('byCategory')}
          </AppText>
          <View style={styles.donutWrap}>
            <DonutChart data={byCategory} centerTitle={money(monthTotal, true)} centerSubtitle={t('perMonth')} />
          </View>
          <View style={{ gap: 12, marginTop: 20 }}>
            {byCategory.map((c) => {
              const info = categoryInfo(c.key as CategoryId);
              const pct = monthTotal ? c.value / monthTotal : 0;
              return (
                <View key={c.key} style={{ gap: 6 }}>
                  <View style={styles.legendRow}>
                    <View style={[styles.legendIcon, { backgroundColor: info.color + '22' }]}>
                      <Ionicons name={info.icon as any} size={15} color={info.color} />
                    </View>
                    <AppText variant="body" style={{ flex: 1, fontWeight: '600' }}>
                      {categoryLabel(t, info.id)}
                    </AppText>
                    <AppText variant="caption" tone="secondary">
                      {Math.round(pct * 100)}%
                    </AppText>
                    <AppText variant="bodyBold" style={{ minWidth: 80, textAlign: 'right' }}>
                      {money(c.value)}
                    </AppText>
                  </View>
                  <ProgressBar ratio={pct} color={info.color} track={palette.cardAlt} />
                </View>
              );
            })}
          </View>
        </Card>
      </Animated.View>

      <Animated.View entering={FadeInDown.delay(80).duration(400)}>
        <Card>
          <View style={styles.trendHeader}>
            <AppText variant="heading">{t('trend')}</AppText>
            {!isPremium && <PremiumBadge />}
          </View>
          <Segmented
            value={range}
            onChange={setRange}
            options={[
              { value: 'next', label: t('next12') },
              { value: 'last', label: t('last12') },
            ]}
          />
          <View style={{ marginTop: 16 }}>
            {showLocked ? (
              <Tap onPress={() => router.push('/premium')} style={[styles.locked, { backgroundColor: palette.accentSoft }]}>
                <Ionicons name="lock-closed" size={26} color={palette.accent} />
                <AppText variant="bodyBold" tone="accent">
                  {t('fullStatsPremium')}
                </AppText>
              </Tap>
            ) : (
              <>
                <BarChart data={months} highlightIndex={range === 'next' ? 0 : 11} format={(v) => money(v, true)} />
                <AppText variant="caption" tone="secondary" style={{ marginTop: 12 }}>
                  Σ {money(months.reduce((a, m) => a + m.value, 0))}
                </AppText>
              </>
            )}
          </View>
        </Card>
      </Animated.View>

      <Animated.View entering={FadeInDown.delay(160).duration(400)}>
        <Card>
          <AppText variant="heading" style={{ marginBottom: 8 }}>
            {t('mostExpensive')}
          </AppText>
          {top.map((s, i) => (
            <Tap
              key={s.id}
              onPress={() => router.push(`/subscription/${s.id}`)}
              scaleTo={0.99}
              style={[styles.topRow, i < top.length - 1 && { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: palette.border }]}>
              <AppText variant="bodyBold" tone="tertiary" style={{ width: 18 }}>
                {i + 1}
              </AppText>
              <ServiceLogo name={s.name} color={s.color} domain={s.domain} serviceId={s.serviceId} size={38} />
              <AppText variant="body" style={{ flex: 1, fontWeight: '600' }} numberOfLines={1}>
                {s.name}
              </AppText>
              <View style={{ alignItems: 'flex-end' }}>
                <AppText variant="bodyBold">{money(monthlyCost(s, showMyShare, family))}</AppText>
                <AppText variant="tiny" tone="tertiary">
                  {t('perMonth')}
                </AppText>
              </View>
            </Tap>
          ))}
        </Card>
      </Animated.View>

      {insights.length > 0 && (
        <Card>
          <View style={styles.trendHeader}>
            <AppText variant="heading">{t('insights')}</AppText>
            {!isPremium && <PremiumBadge />}
          </View>
          {(isPremium ? insights : insights.slice(0, 1)).map((text, i) => (
            <View key={i} style={styles.insight}>
              <Ionicons name="bulb" size={18} color={palette.warning} />
              <AppText variant="body" style={{ flex: 1, lineHeight: 21 }}>
                {text}
              </AppText>
            </View>
          ))}
          {!isPremium && insights.length > 1 && (
            <Tap onPress={() => router.push('/premium')} style={styles.insight}>
              <Ionicons name="lock-closed" size={18} color={palette.accent} />
              <AppText variant="bodyBold" tone="accent">
                +{insights.length - 1} · {t('fullStatsPremium')}
              </AppText>
            </Tap>
          )}
        </Card>
      )}
    </Screen>
  );
}

function Kpi({ label, value, big }: { label: string; value: string; big?: boolean }) {
  const { palette } = useApp();
  return (
    <View style={[styles.kpi, { backgroundColor: palette.card, borderColor: palette.border }]}>
      <AppText variant="caption" tone="secondary" numberOfLines={1}>
        {label}
      </AppText>
      <AppText variant={big ? 'title' : 'heading'} style={big ? { fontSize: 24 } : undefined} numberOfLines={1} adjustsFontSizeToFit>
        {value}
      </AppText>
    </View>
  );
}

const styles = StyleSheet.create({
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: 10 },
  kpi: { flexBasis: '47%', flexGrow: 1, padding: 16, borderRadius: 22, gap: 4, borderWidth: StyleSheet.hairlineWidth },
  donutWrap: { alignItems: 'center' },
  legendRow: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  legendIcon: { width: 28, height: 28, borderRadius: 9, alignItems: 'center', justifyContent: 'center' },
  trendHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 },
  locked: { height: 170, borderRadius: 20, alignItems: 'center', justifyContent: 'center', gap: 10 },
  topRow: { flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 12 },
  insight: { flexDirection: 'row', gap: 10, alignItems: 'flex-start', paddingVertical: 8 },
});
