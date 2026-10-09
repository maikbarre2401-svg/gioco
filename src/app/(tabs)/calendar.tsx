import { router } from 'expo-router';
import { useMemo, useState } from 'react';
import { StyleSheet, View } from 'react-native';
import Animated, { FadeInDown } from 'react-native-reanimated';

import { MonthGrid, MonthHeader } from '@/components/DatePicker';
import { Screen } from '@/components/Screen';
import { ServiceLogo } from '@/components/ServiceLogo';
import { AppText, Card, Tap } from '@/components/ui';
import { chargesBetween, endOfMonth, isSameDay, startOfMonth, toISODate, today } from '@/lib/dates';
import { cycleLabel } from '@/lib/i18n';
import { effectivePrice } from '@/lib/money';
import type { Subscription } from '@/lib/types';
import { useApp } from '@/state/app';

export default function CalendarScreen() {
  const { subscriptions, palette, t, money, locale, settings } = useApp();
  const [month, setMonth] = useState(startOfMonth(today()));
  const [selected, setSelected] = useState<Date>(today());

  const { marks, byDay, total } = useMemo(() => {
    const marks: Record<string, string[]> = {};
    const byDay: Record<string, Subscription[]> = {};
    let total = 0;
    for (const s of subscriptions) {
      if (s.status !== 'active' && !s.statusDate) continue;
      for (const d of chargesBetween(s, startOfMonth(month), endOfMonth(month))) {
        const key = toISODate(d);
        (marks[key] ??= []).push(s.color);
        (byDay[key] ??= []).push(s);
        total += effectivePrice(s, settings.showMyShare, settings.family);
      }
    }
    return { marks, byDay, total };
  }, [subscriptions, month, settings.showMyShare, settings.family]);

  const dayList = byDay[toISODate(selected)] ?? [];
  const monthDays = Object.keys(byDay).sort();

  return (
    <Screen>
      <AppText variant="title">{t('calendarTitle')}</AppText>
      <Card>
        <MonthHeader month={month} onChange={setMonth} />
        <MonthGrid month={month} selected={selected} onSelect={setSelected} marks={marks} />
        <View style={[styles.totalRow, { borderTopColor: palette.border }]}>
          <AppText variant="body" tone="secondary">
            {t('monthTotal')}
          </AppText>
          <AppText variant="heading">{money(total)}</AppText>
        </View>
      </Card>

      <View style={{ gap: 10 }}>
        <AppText variant="heading" style={{ textTransform: 'capitalize' }}>
          {isSameDay(selected, today()) ? t('today') : selected.toLocaleDateString(locale, { weekday: 'long', day: 'numeric', month: 'long' })}
        </AppText>
        {dayList.length === 0 ? (
          <AppText variant="body" tone="secondary">
            {t('nothingThisDay')}
          </AppText>
        ) : (
          dayList.map((s, i) => <DayItem key={s.id} sub={s} index={i} />)
        )}
      </View>

      {monthDays.length > 0 && (
        <View style={{ gap: 10 }}>
          <AppText variant="heading">{t('renewalsCount', { n: monthDays.reduce((a, k) => a + byDay[k].length, 0) })}</AppText>
          <Card padded={false}>
            {monthDays.map((key, i) => {
              const d = new Date(Number(key.slice(0, 4)), Number(key.slice(5, 7)) - 1, Number(key.slice(8, 10)));
              const subs = byDay[key];
              return (
                <Tap
                  key={key}
                  onPress={() => setSelected(d)}
                  scaleTo={0.99}
                  hapticKind="select"
                  style={[styles.monthRow, i < monthDays.length - 1 && { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: palette.border }]}>
                  <View style={[styles.dayBadge, { backgroundColor: isSameDay(d, selected) ? palette.accent : palette.cardAlt }]}>
                    <AppText variant="bodyBold" style={{ color: isSameDay(d, selected) ? palette.onAccent : palette.text }}>
                      {d.getDate()}
                    </AppText>
                  </View>
                  <View style={styles.logos}>
                    {subs.slice(0, 4).map((s, j) => (
                      <View key={s.id} style={{ marginLeft: j === 0 ? 0 : -10 }}>
                        <ServiceLogo name={s.name} color={s.color} domain={s.domain} serviceId={s.serviceId} size={30} />
                      </View>
                    ))}
                  </View>
                  <AppText variant="caption" tone="secondary" style={{ flex: 1 }} numberOfLines={1}>
                    {subs.map((s) => s.name).join(', ')}
                  </AppText>
                  <AppText variant="bodyBold">
                    {money(subs.reduce((a, s) => a + effectivePrice(s, settings.showMyShare, settings.family), 0))}
                  </AppText>
                </Tap>
              );
            })}
          </Card>
        </View>
      )}
    </Screen>
  );
}

function DayItem({ sub, index }: { sub: Subscription; index: number }) {
  const { palette, t, money, settings } = useApp();
  return (
    <Animated.View entering={FadeInDown.delay(index * 40)}>
      <Tap onPress={() => router.push(`/subscription/${sub.id}`)} style={[styles.dayItem, { backgroundColor: palette.card, borderColor: palette.border }]}>
        <ServiceLogo name={sub.name} color={sub.color} domain={sub.domain} serviceId={sub.serviceId} size={44} />
        <View style={{ flex: 1 }}>
          <AppText variant="bodyBold">{sub.name}</AppText>
          <AppText variant="caption" tone="secondary">
            {cycleLabel(t, sub.cycle.unit, sub.cycle.every)}
          </AppText>
        </View>
        <AppText variant="heading">{money(effectivePrice(sub, settings.showMyShare, settings.family))}</AppText>
      </Tap>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  totalRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', borderTopWidth: StyleSheet.hairlineWidth, marginTop: 12, paddingTop: 14 },
  dayItem: { flexDirection: 'row', alignItems: 'center', gap: 14, padding: 14, borderRadius: 20, borderWidth: StyleSheet.hairlineWidth },
  monthRow: { flexDirection: 'row', alignItems: 'center', gap: 12, paddingHorizontal: 16, paddingVertical: 12 },
  dayBadge: { width: 38, height: 38, borderRadius: 12, alignItems: 'center', justifyContent: 'center' },
  logos: { flexDirection: 'row' },
});
