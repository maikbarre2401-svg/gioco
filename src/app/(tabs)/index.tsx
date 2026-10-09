import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { router } from 'expo-router';
import { useMemo, useState } from 'react';
import { ScrollView, StyleSheet, View } from 'react-native';
import Animated, { FadeIn, FadeInDown, FadeOut, LinearTransition } from 'react-native-reanimated';

import { ProgressBar } from '@/components/Charts';
import { MaikMark } from '@/components/MaikLogo';
import { Screen } from '@/components/Screen';
import { ServiceLogo } from '@/components/ServiceLogo';
import { SubscriptionRow, useRenewalText } from '@/components/SubscriptionRow';
import { openAdd } from '@/components/TabBar';
import { AppText, Button, Card, Chip, Input, Segmented, Tap } from '@/components/ui';
import { categoryInfo } from '@/lib/catalog';
import { daysUntil, nextRenewal, today } from '@/lib/dates';
import { categoryLabel } from '@/lib/i18n';
import { effectivePrice, monthlyCost, savedSinceCancel } from '@/lib/money';
import { withAlpha } from '@/lib/theme';
import type { CategoryId, Subscription } from '@/lib/types';
import { useApp } from '@/state/app';

type Sort = 'date' | 'price' | 'name';

export default function HomeScreen() {
  const { subscriptions, settings, palette, t, money, locale, isPremium, canAddMore, loadSample } = useApp();
  const renewalText = useRenewalText();
  const [period, setPeriod] = useState<'month' | 'year'>('month');
  const [sort, setSort] = useState<Sort>('date');
  const [query, setQuery] = useState('');
  const [category, setCategory] = useState<CategoryId | 'all'>('all');

  const { showMyShare, family } = settings;
  const active = useMemo(() => subscriptions.filter((s) => s.status === 'active'), [subscriptions]);
  const inactive = useMemo(() => subscriptions.filter((s) => s.status !== 'active'), [subscriptions]);

  const monthTotal = active.reduce((a, s) => a + monthlyCost(s, showMyShare, family), 0);
  const saved = inactive.reduce((a, s) => a + savedSinceCancel(s, showMyShare, family), 0);
  const budget = settings.monthlyBudget;

  const withNext = useMemo(
    () =>
      active
        .map((s) => ({ sub: s, next: nextRenewal(s)! }))
        .sort((a, b) => a.next.getTime() - b.next.getTime()),
    [active],
  );
  const upcoming = withNext.filter((x) => daysUntil(x.next) <= 14).slice(0, 8);
  const nextUp = withNext[0];

  const presentCategories = useMemo(() => {
    const ids = new Set(subscriptions.map((s) => s.category));
    return [...ids];
  }, [subscriptions]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    let list = active.filter(
      (s) => (category === 'all' || s.category === category) && (!q || s.name.toLowerCase().includes(q)),
    );
    const nextOf = (s: Subscription) => nextRenewal(s)?.getTime() ?? Infinity;
    list = [...list].sort((a, b) => {
      if (sort === 'price') return monthlyCost(b) - monthlyCost(a);
      if (sort === 'name') return a.name.localeCompare(b.name, locale);
      return nextOf(a) - nextOf(b);
    });
    return list;
  }, [active, category, query, sort, locale]);

  const filteredInactive = inactive.filter(
    (s) => (category === 'all' || s.category === category) && (!query || s.name.toLowerCase().includes(query.trim().toLowerCase())),
  );

  const dateLabel = today().toLocaleDateString(locale, { weekday: 'long', day: 'numeric', month: 'long' });
  const heroValue = period === 'month' ? monthTotal : monthTotal * 12;

  return (
    <Screen>
      {/* Header */}
      <View style={styles.header}>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
          <MaikMark size={40} />
          <View>
            <AppText variant="heading">{t('hello')}</AppText>
            <AppText variant="caption" tone="secondary" style={{ textTransform: 'capitalize' }}>
              {dateLabel}
            </AppText>
          </View>
        </View>
        {!isPremium && (
          <Tap
            onPress={() => router.push('/premium')}
            style={[styles.proPill, { backgroundColor: palette.accentSoft }]}
            accessibilityRole="button"
            accessibilityLabel={t('upgrade')}>
            <Ionicons name="sparkles" size={14} color={palette.accent} />
            <AppText variant="caption" tone="accent" style={{ fontWeight: '800' }}>
              PRO
            </AppText>
          </Tap>
        )}
      </View>

      {subscriptions.length === 0 ? (
        <EmptyState onAdd={() => openAdd(canAddMore)} onSample={loadSample} />
      ) : (
        <>
          {/* Hero total */}
          <Animated.View entering={FadeInDown.duration(400)}>
            <LinearGradient
              colors={[palette.accent, withAlpha(palette.accent, 0.78)]}
              start={{ x: 0, y: 0 }}
              end={{ x: 1, y: 1 }}
              style={styles.hero}>
              <View style={styles.heroTop}>
                <AppText variant="label" tone="onAccent" style={{ opacity: 0.85 }}>
                  {period === 'month' ? t('monthlyTotal') : t('yearlyTotal')}
                </AppText>
                <View style={styles.periodSwitch}>
                  {(['month', 'year'] as const).map((p) => (
                    <Tap
                      key={p}
                      hapticKind="select"
                      onPress={() => setPeriod(p)}
                      style={[styles.periodBtn, period === p && { backgroundColor: 'rgba(255,255,255,0.25)' }]}>
                      <AppText variant="tiny" tone="onAccent">
                        {p === 'month' ? t('perMonth') : t('perYear')}
                      </AppText>
                    </Tap>
                  ))}
                </View>
              </View>
              <Animated.View key={period} entering={FadeIn.duration(250)}>
                <AppText variant="display" tone="onAccent" adjustsFontSizeToFit numberOfLines={1}>
                  {money(heroValue)}
                </AppText>
              </Animated.View>
              <View style={styles.heroStats}>
                <HeroStat label={period === 'month' ? t('perYear') : t('perMonth')} value={money(period === 'month' ? monthTotal * 12 : monthTotal)} />
                <HeroStat label={t('perDay')} value={money(monthTotal / 30.436875)} />
                <HeroStat label={t('activeLabel')} value={String(active.length)} />
              </View>
              {budget ? (
                <View style={{ gap: 8, marginTop: 4 }}>
                  <ProgressBar ratio={monthTotal / budget} color={monthTotal > budget ? '#FFD1D6' : '#FFFFFF'} track="rgba(255,255,255,0.25)" />
                  <AppText variant="caption" tone="onAccent" style={{ opacity: 0.9 }}>
                    {t('budget')} {money(budget, true)} ·{' '}
                    {monthTotal > budget
                      ? t('budgetOver', { amount: money(monthTotal - budget) })
                      : t('budgetLeft', { amount: money(budget - monthTotal) })}
                  </AppText>
                </View>
              ) : null}
            </LinearGradient>
          </Animated.View>

          {/* Next renewal */}
          {nextUp && (
            <Animated.View entering={FadeInDown.delay(80).duration(400)}>
              <Tap onPress={() => router.push(`/subscription/${nextUp.sub.id}`)}>
                <Card style={styles.nextCard}>
                  <ServiceLogo name={nextUp.sub.name} color={nextUp.sub.color} domain={nextUp.sub.domain} serviceId={nextUp.sub.serviceId} size={56} />
                  <View style={{ flex: 1, gap: 2 }}>
                    <AppText variant="label" tone="secondary">
                      {t('nextUp')}
                    </AppText>
                    <AppText variant="heading" numberOfLines={1}>
                      {nextUp.sub.name}
                    </AppText>
                    <AppText variant="caption" tone="secondary">
                      {money(effectivePrice(nextUp.sub, showMyShare, family))} ·{' '}
                      {nextUp.next.toLocaleDateString(locale, { weekday: 'short', day: 'numeric', month: 'short' })}
                    </AppText>
                  </View>
                  <View style={[styles.countdown, { backgroundColor: daysUntil(nextUp.next) <= 3 ? palette.danger + '1F' : palette.accentSoft }]}>
                    {daysUntil(nextUp.next) === 0 ? (
                      <AppText variant="bodyBold" tone="danger">
                        {t('today')}
                      </AppText>
                    ) : (
                      <>
                        <AppText variant="title" style={{ color: daysUntil(nextUp.next) <= 3 ? palette.danger : palette.accent }}>
                          {daysUntil(nextUp.next)}
                        </AppText>
                        <AppText variant="tiny" tone="secondary">
                          {daysUntil(nextUp.next) === 1 ? t('dayWord') : t('daysWord')}
                        </AppText>
                      </>
                    )}
                  </View>
                </Card>
              </Tap>
            </Animated.View>
          )}

          {/* Upcoming strip */}
          {upcoming.length > 1 && (
            <View style={{ gap: 12 }}>
              <AppText variant="heading">{t('upcoming')}</AppText>
              <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 10, paddingRight: 8 }}>
                {upcoming.map(({ sub, next }, i) => (
                  <Animated.View key={sub.id} entering={FadeInDown.delay(100 + i * 40)}>
                    <Tap onPress={() => router.push(`/subscription/${sub.id}`)} style={[styles.upcomingCard, { backgroundColor: palette.card, borderColor: palette.border }]}>
                      <ServiceLogo name={sub.name} color={sub.color} domain={sub.domain} serviceId={sub.serviceId} size={36} />
                      <AppText variant="caption" style={{ fontWeight: '700' }} numberOfLines={1}>
                        {sub.name}
                      </AppText>
                      <AppText variant="bodyBold">{money(effectivePrice(sub, showMyShare, family))}</AppText>
                      <AppText variant="tiny" style={{ color: daysUntil(next) <= 3 ? palette.danger : palette.textSecondary }}>
                        {renewalText(daysUntil(next))}
                      </AppText>
                    </Tap>
                  </Animated.View>
                ))}
              </ScrollView>
            </View>
          )}

          {/* Saved */}
          {saved > 0.5 && (
            <Card style={styles.savedCard}>
              <View style={[styles.savedIcon, { backgroundColor: palette.success + '22' }]}>
                <Ionicons name="leaf" size={20} color={palette.success} />
              </View>
              <View style={{ flex: 1 }}>
                <AppText variant="heading" tone="success">
                  {money(saved)} {t('savedTitle').toLowerCase()}
                </AppText>
                <AppText variant="caption" tone="secondary">
                  {t('savedBody')}
                </AppText>
              </View>
            </Card>
          )}

          {!isPremium && (
            <Tap onPress={() => router.push('/premium')}>
              <Card style={[styles.premiumCard, { borderColor: palette.accent + '55' }]}>
                <View style={[styles.savedIcon, { backgroundColor: palette.accentSoft }]}>
                  <Ionicons name="sparkles" size={20} color={palette.accent} />
                </View>
                <View style={{ flex: 1 }}>
                  <AppText variant="bodyBold">{t('premiumBannerTitle')}</AppText>
                  <AppText variant="caption" tone="secondary">
                    {t('premiumBannerBody')}
                  </AppText>
                </View>
                <Ionicons name="chevron-forward" size={18} color={palette.textTertiary} />
              </Card>
            </Tap>
          )}

          {/* List */}
          <View style={{ gap: 12 }}>
            <AppText variant="heading">{t('allSubscriptions')}</AppText>
            <View>
              <Input value={query} onChangeText={setQuery} placeholder={t('searchPlaceholder')} returnKeyType="search" style={{ paddingLeft: 44 }} />
              <Ionicons name="search" size={18} color={palette.textTertiary} style={styles.searchIcon} />
            </View>
            <Segmented
              value={sort}
              onChange={setSort}
              options={[
                { value: 'date', label: t('sortDate') },
                { value: 'price', label: t('sortPrice') },
                { value: 'name', label: t('sortName') },
              ]}
            />
            {presentCategories.length > 1 && (
              <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 8 }}>
                <Chip label={t('filterAll')} selected={category === 'all'} onPress={() => setCategory('all')} />
                {presentCategories.map((c) => (
                  <Chip
                    key={c}
                    label={categoryLabel(t, c)}
                    icon={categoryInfo(c).icon as any}
                    color={categoryInfo(c).color}
                    selected={category === c}
                    onPress={() => setCategory(category === c ? 'all' : c)}
                  />
                ))}
              </ScrollView>
            )}
            {filtered.map((s, i) => (
              <Animated.View key={s.id} entering={FadeInDown.delay(Math.min(i, 8) * 30)} exiting={FadeOut.duration(200)} layout={LinearTransition.springify().damping(18)}>
                <SubscriptionRow sub={s} />
              </Animated.View>
            ))}
            {filtered.length === 0 && filteredInactive.length === 0 && (
              <AppText variant="body" tone="secondary" style={{ textAlign: 'center', paddingVertical: 24 }}>
                {t('noResults')}
              </AppText>
            )}
          </View>

          {filteredInactive.length > 0 && (
            <View style={{ gap: 12 }}>
              <AppText variant="heading" tone="secondary">
                {t('inactiveSection')}
              </AppText>
              {filteredInactive.map((s) => (
                <Animated.View key={s.id} exiting={FadeOut.duration(200)} layout={LinearTransition.springify().damping(18)}>
                  <SubscriptionRow sub={s} />
                </Animated.View>
              ))}
            </View>
          )}
        </>
      )}
    </Screen>
  );
}

function HeroStat({ label, value }: { label: string; value: string }) {
  return (
    <View style={{ flex: 1 }}>
      <AppText variant="bodyBold" tone="onAccent" numberOfLines={1} adjustsFontSizeToFit>
        {value}
      </AppText>
      <AppText variant="tiny" tone="onAccent" style={{ opacity: 0.75 }} numberOfLines={1}>
        {label}
      </AppText>
    </View>
  );
}

function EmptyState({ onAdd, onSample }: { onAdd: () => void; onSample: () => void }) {
  const { t, palette } = useApp();
  return (
    <Animated.View entering={FadeInDown.duration(500)}>
      <Card style={styles.empty}>
        <View style={[styles.emptyIcon, { backgroundColor: palette.accentSoft }]}>
          <Ionicons name="albums" size={40} color={palette.accent} />
        </View>
        <AppText variant="title" style={{ textAlign: 'center' }}>
          {t('emptyTitle')}
        </AppText>
        <AppText variant="body" tone="secondary" style={{ textAlign: 'center', lineHeight: 22 }}>
          {t('emptyBody')}
        </AppText>
        <Button title={t('emptyCta')} icon="add" onPress={onAdd} style={{ alignSelf: 'stretch' }} />
        <Button title={t('loadSample')} variant="ghost" onPress={onSample} style={{ alignSelf: 'stretch' }} />
      </Card>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  proPill: { flexDirection: 'row', alignItems: 'center', gap: 5, paddingHorizontal: 12, paddingVertical: 8, borderRadius: 14 },
  hero: { borderRadius: 32, padding: 22, gap: 14, overflow: 'hidden' },
  heroTop: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  periodSwitch: { flexDirection: 'row', backgroundColor: 'rgba(255,255,255,0.15)', borderRadius: 12, padding: 3 },
  periodBtn: { paddingHorizontal: 10, paddingVertical: 5, borderRadius: 9 },
  heroStats: { flexDirection: 'row', gap: 12, paddingTop: 12, borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: 'rgba(255,255,255,0.3)' },
  nextCard: { flexDirection: 'row', alignItems: 'center', gap: 14 },
  countdown: { alignItems: 'center', justifyContent: 'center', borderRadius: 18, paddingHorizontal: 14, paddingVertical: 8, minWidth: 64 },
  upcomingCard: { width: 120, padding: 14, borderRadius: 20, gap: 6, borderWidth: StyleSheet.hairlineWidth },
  savedCard: { flexDirection: 'row', alignItems: 'center', gap: 14 },
  savedIcon: { width: 44, height: 44, borderRadius: 14, alignItems: 'center', justifyContent: 'center' },
  premiumCard: { flexDirection: 'row', alignItems: 'center', gap: 14, borderWidth: 1 },
  searchIcon: { position: 'absolute', left: 16, top: 17 },
  empty: { alignItems: 'center', gap: 16, paddingVertical: 36, paddingHorizontal: 24 },
  emptyIcon: { width: 88, height: 88, borderRadius: 28, alignItems: 'center', justifyContent: 'center' },
});
