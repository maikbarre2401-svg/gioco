import { Ionicons } from '@expo/vector-icons';
import { router, useLocalSearchParams } from 'expo-router';
import { Linking, StyleSheet, View } from 'react-native';
import Animated, { FadeInDown } from 'react-native-reanimated';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { Screen } from '@/components/Screen';
import { ServiceLogo } from '@/components/ServiceLogo';
import { Pill, useRenewalText } from '@/components/SubscriptionRow';
import { useToast } from '@/components/Toast';
import { AppText, Button, Card, IconButton, Row } from '@/components/ui';
import { categoryInfo } from '@/lib/catalog';
import { confirm } from '@/lib/confirm';
import { chargesBetween, daysUntil, isInTrial, parseISODate, toISODate, today, upcomingRenewals } from '@/lib/dates';
import { categoryLabel, cycleLabel, reminderLabel } from '@/lib/i18n';
import { chargesPerMonth, effectivePrice, monthlyCost, savedSinceCancel, spentSoFar } from '@/lib/money';
import { useApp } from '@/state/app';

export default function SubscriptionDetail() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { subscriptions, palette, t, money, locale, settings, updateSubscription, removeSubscription, restoreSubscription } = useApp();
  const toast = useToast();
  const insets = useSafeAreaInsets();
  const renewalText = useRenewalText();
  const sub = subscriptions.find((s) => s.id === id);

  if (!sub) {
    return (
      <View style={[styles.missing, { backgroundColor: palette.background }]}>
        <AppText variant="heading">{t('notFound')}</AppText>
        <Button title={t('goBack')} onPress={() => (router.canGoBack() ? router.back() : router.replace('/'))} />
      </View>
    );
  }

  const { showMyShare, family } = settings;
  const cat = categoryInfo(sub.category);
  const trial = isInTrial(sub);
  const renewals = upcomingRenewals(sub, 5);
  const past = chargesBetween(sub, parseISODate(sub.startDate), today()).reverse();
  const members = family.filter((m) => sub.sharedWith.includes(m.id));
  const myShare = sub.price / (members.length + 1);
  const fmtDate = (d: Date, opts: Intl.DateTimeFormatOptions = { day: 'numeric', month: 'long', year: 'numeric' }) => d.toLocaleDateString(locale, opts);

  const del = async () => {
    const ok = await confirm(t('deleteConfirmTitle', { name: sub.name }), t('deleteConfirmBody'), t('delete'), t('cancel'));
    if (!ok) return;
    const index = subscriptions.findIndex((s) => s.id === sub.id);
    const removed = removeSubscription(sub.id);
    router.back();
    if (removed) {
      toast({ message: t('deleted', { name: removed.name }), action: t('undo'), onAction: () => restoreSubscription(removed, index), duration: 6000 });
    }
  };

  const setStatus = (status: 'active' | 'paused' | 'cancelled') => {
    if (status === 'active') {
      // Resuming restarts the billing from today, keeping the same cycle.
      updateSubscription(sub.id, { status, statusDate: undefined, startDate: sub.status === 'active' ? sub.startDate : toISODate(today()) });
    } else {
      updateSubscription(sub.id, { status, statusDate: toISODate(today()) });
    }
  };

  return (
    <View style={{ flex: 1, backgroundColor: palette.background }}>
      <View style={[styles.topBar, { paddingTop: insets.top + 8 }]}>
        <IconButton icon="chevron-back" label={t('goBack')} onPress={() => (router.canGoBack() ? router.back() : router.replace('/'))} />
        <IconButton icon="create-outline" label={t('edit')} onPress={() => router.push({ pathname: '/add', params: { id: sub.id } })} />
      </View>
      <Screen tabBar={false} topInset={false}>
        <Animated.View entering={FadeInDown.duration(350)} style={styles.hero}>
          <ServiceLogo name={sub.name} color={sub.color} domain={sub.domain} serviceId={sub.serviceId} size={88} />
          <AppText variant="title" style={{ textAlign: 'center' }}>
            {sub.name}
          </AppText>
          <View style={styles.pills}>
            <Pill text={categoryLabel(t, sub.category)} color={cat.color} />
            {trial && <Pill text={t('trial')} color={palette.warning} />}
            {sub.status === 'paused' && <Pill text={t('paused')} color={palette.textSecondary} />}
            {sub.status === 'cancelled' && <Pill text={t('cancelled')} color={palette.danger} />}
            {members.length > 0 && <Pill text={`${t('shared')} · ${members.length + 1}`} color={palette.accent} />}
          </View>
          <AppText variant="display" style={{ marginTop: 6 }}>
            {money(sub.price)}
          </AppText>
          <AppText variant="body" tone="secondary">
            {cycleLabel(t, sub.cycle.unit, sub.cycle.every)}
          </AppText>
        </Animated.View>

        {trial && (
          <Card style={[styles.banner, { backgroundColor: palette.warning + '1A', borderColor: palette.warning + '44' }]}>
            <Ionicons name="gift" size={22} color={palette.warning} />
            <AppText variant="body" style={{ flex: 1, fontWeight: '600' }}>
              {t('trialEndsIn', { when: renewalText(daysUntil(parseISODate(sub.startDate))) })} · {fmtDate(parseISODate(sub.startDate), { day: 'numeric', month: 'long' })}
            </AppText>
          </Card>
        )}

        <View style={styles.statsGrid}>
          <Stat label={t('monthlyEquivalent')} value={money(sub.price * chargesPerMonth(sub.cycle))} />
          <Stat label={t('yearlyEquivalent')} value={money(sub.price * chargesPerMonth(sub.cycle) * 12)} />
          <Stat label={t('spentSoFar')} value={money(spentSoFar(sub))} />
          {members.length > 0 ? (
            <Stat label={t('myShare')} value={money(myShare)} accent />
          ) : sub.status === 'cancelled' ? (
            <Stat label={t('savedTitle')} value={money(savedSinceCancel(sub))} accent />
          ) : (
            <Stat label={t('perDay')} value={money(monthlyCost(sub) / 30.436875)} />
          )}
        </View>

        {renewals.length > 0 && (
          <Card>
            <AppText variant="heading" style={{ marginBottom: 6 }}>
              {t('nextRenewals')}
            </AppText>
            {renewals.map((d, i) => (
              <View key={i} style={[styles.renewalRow, i < renewals.length - 1 && { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: palette.border }]}>
                <View style={[styles.dateBadge, { backgroundColor: i === 0 ? palette.accent : palette.cardAlt }]}>
                  <AppText variant="bodyBold" style={{ color: i === 0 ? palette.onAccent : palette.text }}>
                    {d.getDate()}
                  </AppText>
                  <AppText variant="tiny" style={{ color: i === 0 ? palette.onAccent : palette.textSecondary, textTransform: 'uppercase' }}>
                    {d.toLocaleDateString(locale, { month: 'short' })}
                  </AppText>
                </View>
                <View style={{ flex: 1 }}>
                  <AppText variant="body" style={{ fontWeight: '600', textTransform: 'capitalize' }}>
                    {d.toLocaleDateString(locale, { weekday: 'long' })}
                  </AppText>
                  <AppText variant="caption" tone="secondary">
                    {renewalText(daysUntil(d))}
                  </AppText>
                </View>
                <AppText variant="bodyBold">{money(effectivePrice(sub, showMyShare, family))}</AppText>
              </View>
            ))}
          </Card>
        )}

        <Card>
          <AppText variant="heading" style={{ marginBottom: 2 }}>
            {t('details')}
          </AppText>
          <Row icon="calendar-outline" title={sub.isTrial ? t('trialEnd') : t('firstPayment')} value={fmtDate(parseISODate(sub.startDate))} />
          <Row
            icon="notifications-outline"
            title={t('reminders')}
            value={sub.reminderDays.length ? sub.reminderDays.map((d) => reminderLabel(t, d)).join(', ') : t('reminderNone')}
          />
          {sub.paymentMethod ? <Row icon="card-outline" title={t('paymentMethod')} value={sub.paymentMethod} /> : null}
          {members.length > 0 ? <Row icon="people-outline" title={t('sharedWithFamily')} value={members.map((m) => m.name).join(', ')} /> : null}
          {sub.notes ? <Row icon="document-text-outline" title={t('notes')} subtitle={sub.notes} /> : null}
          <Row icon="time-outline" title={t('paymentHistory')} value={String(past.length)} last />
        </Card>

        {sub.priceHistory.length > 0 && (
          <Card>
            <AppText variant="heading" style={{ marginBottom: 6 }}>
              {t('priceHistory')}
            </AppText>
            {[...sub.priceHistory].reverse().map((p, i) => (
              <Row key={i} title={fmtDate(parseISODate(p.date))} value={`${money(p.price)} → ${money(i === 0 ? sub.price : sub.priceHistory[sub.priceHistory.length - i].price)}`} last={i === sub.priceHistory.length - 1} />
            ))}
          </Card>
        )}

        {past.length > 0 && (
          <Card>
            <AppText variant="heading" style={{ marginBottom: 6 }}>
              {t('paymentHistory')}
            </AppText>
            {past.slice(0, 6).map((d, i) => (
              <Row key={i} icon="checkmark-circle" iconColor={palette.success} title={fmtDate(d)} value={money(sub.price)} last={i === Math.min(past.length, 6) - 1} />
            ))}
          </Card>
        )}

        <View style={{ gap: 10 }}>
          {sub.url ? (
            <Button title={t('openWebsite')} icon="open-outline" variant="secondary" onPress={() => Linking.openURL(sub.url!).catch(() => {})} />
          ) : null}
          {sub.status === 'active' ? (
            <>
              <Button title={t('pause')} icon="pause" variant="secondary" onPress={() => setStatus('paused')} />
              <Button title={t('markCancelled')} icon="close-circle-outline" variant="secondary" onPress={() => setStatus('cancelled')} />
            </>
          ) : (
            <Button title={t('resume')} icon="play" onPress={() => setStatus('active')} />
          )}
          <Button title={t('delete')} icon="trash-outline" variant="danger" onPress={del} />
        </View>
        <AppText variant="caption" tone="tertiary" style={{ textAlign: 'center' }}>
          {t('since', { date: fmtDate(new Date(sub.createdAt)) })}
        </AppText>
      </Screen>
    </View>
  );
}

function Stat({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  const { palette } = useApp();
  return (
    <View style={[styles.stat, { backgroundColor: accent ? palette.accentSoft : palette.card, borderColor: palette.border }]}>
      <AppText variant="caption" tone="secondary">
        {label}
      </AppText>
      <AppText variant="heading" tone={accent ? 'accent' : 'primary'} numberOfLines={1} adjustsFontSizeToFit>
        {value}
      </AppText>
    </View>
  );
}

const styles = StyleSheet.create({
  missing: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 16, padding: 24 },
  topBar: { flexDirection: 'row', justifyContent: 'space-between', paddingHorizontal: 16, paddingBottom: 4 },
  hero: { alignItems: 'center', gap: 8, paddingTop: 4 },
  pills: { flexDirection: 'row', gap: 6, flexWrap: 'wrap', justifyContent: 'center' },
  banner: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  statsGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 10 },
  stat: { flexBasis: '47%', flexGrow: 1, padding: 16, borderRadius: 20, gap: 4, borderWidth: StyleSheet.hairlineWidth },
  renewalRow: { flexDirection: 'row', alignItems: 'center', gap: 14, paddingVertical: 12 },
  dateBadge: { width: 48, height: 48, borderRadius: 14, alignItems: 'center', justifyContent: 'center' },
});
