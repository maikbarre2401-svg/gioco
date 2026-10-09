import { Ionicons } from '@expo/vector-icons';
import { useState } from 'react';
import { Modal, Pressable, StyleSheet, View } from 'react-native';

import { addMonths, isSameDay, parseISODate, toISODate, today } from '@/lib/dates';
import { useApp } from '@/state/app';

import { AppText, Button, haptic, IconButton } from './ui';

function weekdayNames(locale: string): string[] {
  // 2024-01-01 was a Monday.
  return Array.from({ length: 7 }, (_, i) =>
    new Date(2024, 0, 1 + i).toLocaleDateString(locale, { weekday: 'narrow' }),
  );
}

export function MonthGrid({
  month,
  selected,
  onSelect,
  marks,
}: {
  month: Date;
  selected?: Date | null;
  onSelect: (d: Date) => void;
  /** Colors of dots to show under each day, keyed by YYYY-MM-DD. */
  marks?: Record<string, string[]>;
}) {
  const { palette, locale } = useApp();
  const first = new Date(month.getFullYear(), month.getMonth(), 1);
  const lead = (first.getDay() + 6) % 7;
  const days = new Date(month.getFullYear(), month.getMonth() + 1, 0).getDate();
  const cells: (Date | null)[] = [
    ...Array.from({ length: lead }, () => null),
    ...Array.from({ length: days }, (_, i) => new Date(month.getFullYear(), month.getMonth(), i + 1)),
  ];
  while (cells.length % 7) cells.push(null);
  const now = today();

  return (
    <View>
      <View style={styles.week}>
        {weekdayNames(locale).map((d, i) => (
          <AppText key={i} variant="tiny" tone="tertiary" style={styles.weekday}>
            {d.toUpperCase()}
          </AppText>
        ))}
      </View>
      <View style={styles.grid}>
        {cells.map((d, i) => {
          if (!d) return <View key={i} style={styles.cell} />;
          const isSel = selected ? isSameDay(d, selected) : false;
          const isToday = isSameDay(d, now);
          const dots = marks?.[toISODate(d)] ?? [];
          return (
            <Pressable
              key={i}
              style={styles.cell}
              accessibilityRole="button"
              accessibilityLabel={d.toLocaleDateString(locale, { day: 'numeric', month: 'long' })}
              accessibilityState={{ selected: isSel }}
              onPress={() => {
                haptic('select');
                onSelect(d);
              }}>
              <View
                style={[
                  styles.day,
                  isSel && { backgroundColor: palette.accent },
                  !isSel && isToday && { borderWidth: 1.5, borderColor: palette.accent },
                ]}>
                <AppText
                  variant="body"
                  style={{ fontWeight: isSel || isToday ? '800' : '500', color: isSel ? palette.onAccent : palette.text }}>
                  {d.getDate()}
                </AppText>
              </View>
              <View style={styles.dots}>
                {dots.slice(0, 3).map((c, j) => (
                  <View key={j} style={[styles.dot, { backgroundColor: c }]} />
                ))}
              </View>
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}

export function MonthHeader({ month, onChange }: { month: Date; onChange: (d: Date) => void }) {
  const { locale } = useApp();
  const label = month.toLocaleDateString(locale, { month: 'long', year: 'numeric' });
  return (
    <View style={styles.header}>
      <IconButton icon="chevron-back" label="‹" onPress={() => onChange(addMonths(month, -1, 1))} size={36} />
      <AppText variant="heading" style={{ textTransform: 'capitalize' }}>
        {label}
      </AppText>
      <IconButton icon="chevron-forward" label="›" onPress={() => onChange(addMonths(month, 1, 1))} size={36} />
    </View>
  );
}

/** Date field that opens a calendar sheet. */
export function DateField({ value, onChange }: { value: string; onChange: (iso: string) => void }) {
  const { palette, locale, t } = useApp();
  const [open, setOpen] = useState(false);
  const date = parseISODate(value);
  const [month, setMonth] = useState(new Date(date.getFullYear(), date.getMonth(), 1));
  const [draft, setDraft] = useState(date);

  const quick = [
    { label: t('today'), date: today() },
    { label: t('tomorrow'), date: new Date(today().getFullYear(), today().getMonth(), today().getDate() + 1) },
  ];

  return (
    <>
      <Pressable
        onPress={() => {
          setDraft(date);
          setMonth(new Date(date.getFullYear(), date.getMonth(), 1));
          setOpen(true);
        }}
        accessibilityRole="button"
        style={[styles.field, { backgroundColor: palette.card, borderColor: palette.border }]}>
        <Ionicons name="calendar-outline" size={19} color={palette.accent} />
        <AppText variant="body" style={{ flex: 1, fontWeight: '600' }}>
          {date.toLocaleDateString(locale, { weekday: 'short', day: 'numeric', month: 'long', year: 'numeric' })}
        </AppText>
        <Ionicons name="chevron-down" size={18} color={palette.textTertiary} />
      </Pressable>
      <Modal visible={open} transparent animationType="fade" onRequestClose={() => setOpen(false)}>
        <Pressable style={[styles.backdrop, { backgroundColor: palette.overlay }]} onPress={() => setOpen(false)}>
          <Pressable style={[styles.sheet, { backgroundColor: palette.card }]} onPress={() => {}}>
            <MonthHeader month={month} onChange={setMonth} />
            <MonthGrid month={month} selected={draft} onSelect={setDraft} />
            <View style={styles.quick}>
              {quick.map((q) => (
                <Pressable
                  key={q.label}
                  onPress={() => {
                    setDraft(q.date);
                    setMonth(new Date(q.date.getFullYear(), q.date.getMonth(), 1));
                  }}
                  style={[styles.quickBtn, { backgroundColor: palette.cardAlt }]}>
                  <AppText variant="caption" style={{ fontWeight: '700' }}>
                    {q.label}
                  </AppText>
                </Pressable>
              ))}
            </View>
            <Button
              title={t('done')}
              onPress={() => {
                onChange(toISODate(draft));
                setOpen(false);
              }}
            />
          </Pressable>
        </Pressable>
      </Modal>
    </>
  );
}

const styles = StyleSheet.create({
  week: { flexDirection: 'row', marginBottom: 6 },
  weekday: { flex: 1, textAlign: 'center' },
  grid: { flexDirection: 'row', flexWrap: 'wrap' },
  cell: { width: `${100 / 7}%`, alignItems: 'center', paddingVertical: 3 },
  day: { width: 38, height: 38, borderRadius: 19, alignItems: 'center', justifyContent: 'center' },
  dots: { flexDirection: 'row', gap: 2, height: 6, marginTop: 2 },
  dot: { width: 5, height: 5, borderRadius: 3 },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 },
  field: {
    height: 52,
    borderRadius: 16,
    borderWidth: 1,
    paddingHorizontal: 16,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  backdrop: { flex: 1, justifyContent: 'center', padding: 16 },
  sheet: { borderRadius: 28, padding: 20, gap: 14, width: '100%', maxWidth: 420, alignSelf: 'center' },
  quick: { flexDirection: 'row', gap: 8 },
  quickBtn: { paddingHorizontal: 14, paddingVertical: 8, borderRadius: 12 },
});
