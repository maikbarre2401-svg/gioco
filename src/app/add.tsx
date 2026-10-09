import { Ionicons } from '@expo/vector-icons';
import { router, useLocalSearchParams } from 'expo-router';
import { useMemo, useState } from 'react';
import { KeyboardAvoidingView, Platform, ScrollView, StyleSheet, View } from 'react-native';
import Animated, { FadeIn, FadeInDown, FadeInRight } from 'react-native-reanimated';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { DateField } from '@/components/DatePicker';
import { ServiceLogo } from '@/components/ServiceLogo';
import { useToast } from '@/components/Toast';
import { AppText, Button, Chip, Field, haptic, IconButton, Input, PremiumBadge, Segmented, Tap, Toggle } from '@/components/ui';
import { newId } from '@/lib/backup';
import { CATALOG, CATEGORIES, COLOR_SWATCHES, POPULAR_IDS, type CatalogService } from '@/lib/catalog';
import { toISODate, today } from '@/lib/dates';
import { categoryLabel, cycleLabel, reminderLabel } from '@/lib/i18n';
import { parsePrice } from '@/lib/money';
import { requestPermission } from '@/lib/notifications';
import { FREE_LIMIT } from '@/lib/purchases-types';
import { MaxWidth } from '@/lib/theme';
import type { CategoryId, Cycle, CycleUnit, Subscription } from '@/lib/types';
import { useApp } from '@/state/app';

const PRESET_CYCLES: Cycle[] = [
  { unit: 'week', every: 1 },
  { unit: 'month', every: 1 },
  { unit: 'month', every: 3 },
  { unit: 'month', every: 6 },
  { unit: 'year', every: 1 },
];
const REMINDER_OPTIONS = [0, 1, 3, 7, 14];

export default function AddScreen() {
  const { id, serviceId } = useLocalSearchParams<{ id?: string; serviceId?: string }>();
  const { subscriptions } = useApp();
  const editing = id ? subscriptions.find((s) => s.id === id) : undefined;
  const preset = serviceId ? CATALOG.find((s) => s.id === serviceId) : undefined;
  const [picked, setPicked] = useState<CatalogService | 'custom' | null>(editing ? 'custom' : preset ?? null);
  const [customName, setCustomName] = useState('');

  if (!picked)
    return (
      <ServicePicker
        onPick={(s, query) => {
          setCustomName(s === 'custom' ? query ?? '' : '');
          setPicked(s);
        }}
      />
    );
  return (
    <SubscriptionForm
      key={typeof picked === 'string' ? picked : picked.id}
      service={picked === 'custom' ? undefined : picked}
      editing={editing}
      initialName={customName}
      onBack={editing ? undefined : () => setPicked(null)}
    />
  );
}

function Header({ title, onBack }: { title: string; onBack?: () => void }) {
  const { t } = useApp();
  return (
    <View style={styles.header}>
      {onBack ? <IconButton icon="chevron-back" label={t('goBack')} onPress={onBack} /> : <View style={{ width: 40 }} />}
      <AppText variant="heading">{title}</AppText>
      <IconButton icon="close" label={t('cancel')} onPress={() => router.back()} />
    </View>
  );
}

function ServicePicker({ onPick }: { onPick: (s: CatalogService | 'custom', query?: string) => void }) {
  const { palette, t } = useApp();
  const insets = useSafeAreaInsets();
  const [query, setQuery] = useState('');

  const q = query.trim().toLowerCase();
  const results = useMemo(
    () => (q ? CATALOG.filter((s) => s.name.toLowerCase().includes(q) || categoryLabel(t, s.category).toLowerCase().includes(q)) : []),
    [q, t],
  );
  const popular = POPULAR_IDS.map((id) => CATALOG.find((s) => s.id === id)!).filter(Boolean);

  return (
    <View style={{ flex: 1, backgroundColor: palette.background, paddingTop: Platform.OS === 'android' ? insets.top : 8 }}>
      <View style={styles.centered}>
        <Header title={t('addTitle')} />
        <View style={{ paddingHorizontal: 16, paddingBottom: 8 }}>
          <View>
            <Input value={query} onChangeText={setQuery} placeholder={t('searchPlaceholder')} autoFocus={Platform.OS !== 'web'} style={{ paddingLeft: 44 }} />
            <Ionicons name="search" size={18} color={palette.textTertiary} style={{ position: 'absolute', left: 16, top: 17 }} />
          </View>
        </View>
      </View>
      <ScrollView contentContainerStyle={[styles.pickerContent, { paddingBottom: insets.bottom + 32 }]} keyboardShouldPersistTaps="handled">
        <View style={styles.centeredInner}>
          <Tap onPress={() => onPick('custom', query.trim())} style={[styles.customCard, { backgroundColor: palette.card, borderColor: palette.border }]}>
            <View style={[styles.customIcon, { backgroundColor: palette.accentSoft }]}>
              <Ionicons name="create" size={22} color={palette.accent} />
            </View>
            <View style={{ flex: 1 }}>
              <AppText variant="bodyBold">
                {q ? `${t('custom')}: “${query.trim()}”` : t('custom')}
              </AppText>
              <AppText variant="caption" tone="secondary">
                {t('customBody')}
              </AppText>
            </View>
            <Ionicons name="chevron-forward" size={18} color={palette.textTertiary} />
          </Tap>

          {q ? (
            <ServiceGrid services={results} onPick={onPick} />
          ) : (
            <>
              <AppText variant="label" tone="secondary">
                {t('popular')}
              </AppText>
              <ServiceGrid services={popular} onPick={onPick} />
              {CATEGORIES.filter((c) => CATALOG.some((s) => s.category === c.id)).map((c) => (
                <View key={c.id} style={{ gap: 12 }}>
                  <AppText variant="label" tone="secondary">
                    {categoryLabel(t, c.id)}
                  </AppText>
                  <ServiceGrid services={CATALOG.filter((s) => s.category === c.id)} onPick={onPick} />
                </View>
              ))}
            </>
          )}
        </View>
      </ScrollView>
    </View>
  );
}

function ServiceGrid({ services, onPick }: { services: CatalogService[]; onPick: (s: CatalogService) => void }) {
  const { money } = useApp();
  return (
    <View style={styles.grid}>
      {services.map((s, i) => (
        <Animated.View key={s.id} entering={FadeIn.delay(Math.min(i, 12) * 15)} style={styles.gridItem}>
          <Tap onPress={() => onPick(s)} style={styles.gridTap} accessibilityRole="button" accessibilityLabel={s.name}>
            <ServiceLogo name={s.name} color={s.color} domain={s.domain} serviceId={s.id} size={56} />
            <AppText variant="tiny" numberOfLines={1} style={{ textAlign: 'center' }}>
              {s.name}
            </AppText>
            <AppText variant="tiny" tone="tertiary" numberOfLines={1}>
              {money(s.price)}
            </AppText>
          </Tap>
        </Animated.View>
      ))}
    </View>
  );
}

function sameCycle(a: Cycle, b: Cycle) {
  return a.unit === b.unit && a.every === b.every;
}

function SubscriptionForm({
  service,
  editing,
  initialName,
  onBack,
}: {
  service?: CatalogService;
  editing?: Subscription;
  initialName?: string;
  onBack?: () => void;
}) {
  const { palette, t, money, settings, isPremium, canAddMore, addSubscription, updateSubscription, locale } = useApp();
  const toast = useToast();
  const insets = useSafeAreaInsets();

  const [name, setName] = useState(editing?.name ?? service?.name ?? initialName ?? '');
  const [priceText, setPriceText] = useState(
    editing ? String(editing.price).replace('.', locale.startsWith('it') ? ',' : '.') : service ? String(service.price).replace('.', locale.startsWith('it') ? ',' : '.') : '',
  );
  const [cycle, setCycle] = useState<Cycle>(editing?.cycle ?? service?.cycle ?? { unit: 'month', every: 1 });
  const [customCycle, setCustomCycle] = useState(!PRESET_CYCLES.some((c) => sameCycle(c, editing?.cycle ?? service?.cycle ?? PRESET_CYCLES[1])));
  const [startDate, setStartDate] = useState(editing?.startDate ?? toISODate(today()));
  const [isTrial, setIsTrial] = useState(editing?.isTrial ?? false);
  const [reminders, setReminders] = useState<number[]>(editing?.reminderDays ?? settings.defaultReminderDays);
  const [category, setCategory] = useState<CategoryId>(editing?.category ?? service?.category ?? 'other');
  const [color, setColor] = useState(editing?.color ?? service?.color ?? palette.accent);
  const [sharedWith, setSharedWith] = useState<string[]>(editing?.sharedWith ?? []);
  const [paymentMethod, setPaymentMethod] = useState(editing?.paymentMethod ?? '');
  const [notes, setNotes] = useState(editing?.notes ?? '');
  const [url, setUrl] = useState(editing?.url ?? service?.url ?? (service?.domain ? `https://${service.domain}` : ''));
  const [showMore, setShowMore] = useState(Boolean(editing));
  const [submitted, setSubmitted] = useState(false);

  const price = parsePrice(priceText);
  const nameError = submitted && !name.trim() ? t('invalidName') : undefined;
  const priceError = submitted && !(price >= 0) ? t('invalidPrice') : undefined;

  const toggleReminder = (d: number) => {
    if (!isPremium) {
      setReminders(reminders.includes(d) ? [] : [d]);
      return;
    }
    setReminders((r) => (r.includes(d) ? r.filter((x) => x !== d) : [...r, d].sort((a, b) => a - b)));
  };

  const save = async () => {
    setSubmitted(true);
    if (!name.trim() || !(price >= 0)) {
      haptic('warning');
      return;
    }
    if (!editing && !canAddMore) {
      router.replace({ pathname: '/premium', params: { reason: 'limit' } });
      return;
    }
    const data = {
      name: name.trim(),
      price: Math.round(price * 100) / 100,
      cycle: { unit: cycle.unit, every: Math.max(1, Math.min(99, cycle.every)) },
      startDate,
      isTrial,
      reminderDays: reminders,
      category,
      color,
      sharedWith: isPremium ? sharedWith : [],
      paymentMethod: paymentMethod.trim() || undefined,
      notes: notes.trim() || undefined,
      url: url.trim() || undefined,
    };
    if (editing) {
      updateSubscription(editing.id, data);
    } else {
      addSubscription({
        ...data,
        id: newId(),
        serviceId: service?.id,
        domain: service?.domain,
        status: 'active',
        createdAt: new Date().toISOString(),
        priceHistory: [],
      });
      if (settings.notificationsEnabled && reminders.length > 0) requestPermission(t).catch(() => {});
    }
    haptic('success');
    toast({ message: `${name.trim()} · ${money(data.price)} ✓` });
    router.back();
  };

  return (
    <KeyboardAvoidingView
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      style={{ flex: 1, backgroundColor: palette.background, paddingTop: Platform.OS === 'android' ? insets.top : 8 }}>
      <View style={styles.centered}>
        <Header title={editing ? t('editTitle') : t('addTitle')} onBack={onBack} />
      </View>
      <ScrollView contentContainerStyle={[styles.formContent, { paddingBottom: 140 + insets.bottom }]} keyboardShouldPersistTaps="handled">
        <Animated.View entering={FadeInRight.duration(250)} style={styles.centeredInner}>
          {/* Identity */}
          <View style={styles.identity}>
            <ServiceLogo name={name || '?'} color={color} domain={editing?.domain ?? service?.domain} serviceId={editing?.serviceId ?? service?.id} size={72} />
            <View style={{ flex: 1 }}>
              <Field label={t('name')} error={nameError}>
                <Input value={name} onChangeText={setName} placeholder={t('namePlaceholder')} autoFocus={!service && !editing && Platform.OS !== 'web'} maxLength={60} />
              </Field>
            </View>
          </View>

          {/* Price */}
          <Field label={t('price')} error={priceError} hint={service && !editing ? t('suggestedPrice') : undefined}>
            <View>
              <Input
                large
                value={priceText}
                onChangeText={setPriceText}
                placeholder="0,00"
                keyboardType="decimal-pad"
                accessibilityLabel={t('price')}
                style={{ paddingRight: 70 }}
              />
              <AppText variant="heading" tone="tertiary" style={styles.currency}>
                {settings.currency}
              </AppText>
            </View>
          </Field>

          {/* Frequency */}
          <Field label={t('frequency')}>
            <View style={styles.wrap}>
              {PRESET_CYCLES.map((c) => (
                <Chip
                  key={`${c.unit}${c.every}`}
                  label={cycleLabel(t, c.unit, c.every)}
                  selected={!customCycle && sameCycle(c, cycle)}
                  onPress={() => {
                    setCustomCycle(false);
                    setCycle(c);
                  }}
                />
              ))}
              <Chip label={t('cycleCustom')} selected={customCycle} onPress={() => setCustomCycle(true)} />
            </View>
            {customCycle && (
              <Animated.View entering={FadeInDown} style={styles.customCycle}>
                <AppText variant="bodyBold">{t('every')}</AppText>
                <IconButton icon="remove" label="-" size={36} onPress={() => setCycle((c) => ({ ...c, every: Math.max(1, c.every - 1) }))} />
                <AppText variant="heading" style={{ minWidth: 28, textAlign: 'center' }}>
                  {cycle.every}
                </AppText>
                <IconButton icon="add" label="+" size={36} onPress={() => setCycle((c) => ({ ...c, every: Math.min(99, c.every + 1) }))} />
              </Animated.View>
            )}
            {customCycle && (
              <Segmented<CycleUnit>
                value={cycle.unit}
                onChange={(unit) => setCycle((c) => ({ ...c, unit }))}
                options={(['day', 'week', 'month', 'year'] as CycleUnit[]).map((u) => ({ value: u, label: t(`unit_${u}`) }))}
              />
            )}
          </Field>

          {/* Date + trial */}
          <Field label={isTrial ? t('trialEnd') : t('firstPayment')}>
            <DateField value={startDate} onChange={setStartDate} />
          </Field>
          <View style={[styles.toggleRow, { backgroundColor: palette.card, borderColor: palette.border }]}>
            <Ionicons name="gift-outline" size={20} color={palette.warning} />
            <View style={{ flex: 1 }}>
              <AppText variant="bodyBold">{t('freeTrial')}</AppText>
              <AppText variant="caption" tone="secondary">
                {t('freeTrialBody')}
              </AppText>
            </View>
            <Toggle value={isTrial} onValueChange={setIsTrial} />
          </View>

          {/* Reminders */}
          <Field label={t('reminders')}>
            <View style={styles.wrap}>
              <Chip label={t('reminderNone')} selected={reminders.length === 0} onPress={() => setReminders([])} />
              {REMINDER_OPTIONS.map((d) => (
                <Chip key={d} label={reminderLabel(t, d)} selected={reminders.includes(d)} onPress={() => toggleReminder(d)} />
              ))}
            </View>
            {!isPremium && (
              <Tap onPress={() => router.push('/premium')} style={styles.inlinePro}>
                <PremiumBadge />
                <AppText variant="caption" tone="secondary">
                  {t('featRemindersBody')}
                </AppText>
              </Tap>
            )}
          </Field>

          <Tap onPress={() => setShowMore((v) => !v)} style={styles.moreBtn} hapticKind="select">
            <AppText variant="bodyBold" tone="accent">
              {showMore ? t('less') : t('more')}
            </AppText>
            <Ionicons name={showMore ? 'chevron-up' : 'chevron-down'} size={18} color={palette.accent} />
          </Tap>

          {showMore && (
            <Animated.View entering={FadeInDown.duration(250)} style={{ gap: 22 }}>
              <Field label={t('category')}>
                <View style={styles.wrap}>
                  {CATEGORIES.map((c) => (
                    <Chip key={c.id} label={categoryLabel(t, c.id)} icon={c.icon as any} color={c.color} selected={category === c.id} onPress={() => setCategory(c.id)} />
                  ))}
                </View>
              </Field>

              <Field label={t('color')}>
                <View style={styles.wrap}>
                  {[...new Set([service?.color, ...COLOR_SWATCHES].filter(Boolean) as string[])].map((c) => (
                    <Tap
                      key={c}
                      hapticKind="select"
                      onPress={() => setColor(c)}
                      accessibilityLabel={c}
                      style={[styles.swatch, { backgroundColor: c, borderColor: color === c ? palette.text : 'transparent' }]}>
                      {color === c && <Ionicons name="checkmark" size={18} color="#fff" />}
                    </Tap>
                  ))}
                </View>
              </Field>

              <Field label={t('sharedWithFamily')}>
                {isPremium ? (
                  settings.family.length > 0 ? (
                    <View style={styles.wrap}>
                      {settings.family.map((m) => (
                        <Chip
                          key={m.id}
                          label={m.name}
                          color={m.color}
                          icon="person"
                          selected={sharedWith.includes(m.id)}
                          onPress={() => setSharedWith((s) => (s.includes(m.id) ? s.filter((x) => x !== m.id) : [...s, m.id]))}
                        />
                      ))}
                      {sharedWith.length > 0 && price > 0 && (
                        <AppText variant="caption" tone="secondary" style={{ alignSelf: 'center' }}>
                          {t('myShare')}: {money(price / (sharedWith.length + 1))}
                        </AppText>
                      )}
                    </View>
                  ) : (
                    <Button title={t('addMember')} icon="person-add" variant="secondary" onPress={() => router.push('/family')} />
                  )
                ) : (
                  <Tap onPress={() => router.push('/premium')} style={styles.inlinePro}>
                    <PremiumBadge />
                    <AppText variant="caption" tone="secondary">
                      {t('featFamilyBody')}
                    </AppText>
                  </Tap>
                )}
              </Field>

              <Field label={t('paymentMethod')}>
                <Input value={paymentMethod} onChangeText={setPaymentMethod} placeholder={t('paymentPlaceholder')} maxLength={40} />
              </Field>
              <Field label={t('website')}>
                <Input value={url} onChangeText={setUrl} placeholder="https://" autoCapitalize="none" keyboardType="url" autoCorrect={false} />
              </Field>
              <Field label={t('notes')}>
                <Input value={notes} onChangeText={setNotes} placeholder={t('notesPlaceholder')} multiline style={{ height: 96, paddingTop: 14, textAlignVertical: 'top' }} maxLength={500} />
              </Field>
            </Animated.View>
          )}
        </Animated.View>
      </ScrollView>

      <View style={[styles.footer, { paddingBottom: insets.bottom + 12, backgroundColor: palette.background, borderTopColor: palette.border }]}>
        <View style={styles.centeredInner}>
          {!editing && !canAddMore && (
            <AppText variant="caption" tone="danger" style={{ textAlign: 'center' }}>
              {t('limitReached', { n: FREE_LIMIT })}
            </AppText>
          )}
          <Button title={editing ? t('saveChanges') : t('save')} icon="checkmark" onPress={save} />
        </View>
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, paddingVertical: 10 },
  centered: { width: '100%', maxWidth: MaxWidth, alignSelf: 'center' },
  centeredInner: { width: '100%', maxWidth: MaxWidth, alignSelf: 'center', gap: 22 },
  pickerContent: { paddingHorizontal: 16, paddingTop: 8 },
  customCard: { flexDirection: 'row', alignItems: 'center', gap: 14, padding: 14, borderRadius: 22, borderWidth: StyleSheet.hairlineWidth },
  customIcon: { width: 48, height: 48, borderRadius: 15, alignItems: 'center', justifyContent: 'center' },
  grid: { flexDirection: 'row', flexWrap: 'wrap', marginHorizontal: -4 },
  gridItem: { width: '25%', padding: 4 },
  gridTap: { alignItems: 'center', gap: 6, paddingVertical: 8 },
  formContent: { paddingHorizontal: 16, paddingTop: 8 },
  identity: { flexDirection: 'row', alignItems: 'flex-end', gap: 14 },
  currency: { position: 'absolute', right: 18, top: 26 },
  wrap: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  customCycle: { flexDirection: 'row', alignItems: 'center', gap: 10, marginTop: 6 },
  toggleRow: { flexDirection: 'row', alignItems: 'center', gap: 12, padding: 14, borderRadius: 18, borderWidth: StyleSheet.hairlineWidth },
  inlinePro: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  moreBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, paddingVertical: 6 },
  swatch: { width: 40, height: 40, borderRadius: 14, borderWidth: 3, alignItems: 'center', justifyContent: 'center' },
  footer: { position: 'absolute', left: 0, right: 0, bottom: 0, paddingHorizontal: 16, paddingTop: 12, borderTopWidth: StyleSheet.hairlineWidth },
});
