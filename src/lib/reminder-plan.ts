import { addDays, isSameDay, parseISODate, upcomingRenewals } from './dates';
import { cycleLabel, type Translate } from './i18n';
import { formatMoney } from './money';
import type { Settings, Subscription } from './types';

/** iOS keeps at most 64 pending local notifications per app. */
export const MAX_SCHEDULED = 60;

export type Planned = { date: Date; title: string; body: string; subId: string };

function whenLabel(t: Translate, days: number): string {
  if (days === 0) return t('notifWhenToday');
  if (days === 1) return t('notifWhenTomorrow');
  return t('notifWhenDays', { n: days });
}

export function planReminders(
  subs: Subscription[],
  settings: Settings,
  isPremium: boolean,
  t: Translate,
  locale: string,
  now = new Date(),
): Planned[] {
  const planned: Planned[] = [];
  // Free users get one reminder per renewal at the default hour.
  const hour = isPremium ? settings.reminderHour : 9;

  for (const sub of subs) {
    if (sub.status !== 'active' || sub.reminderDays.length === 0) continue;
    const days = isPremium ? sub.reminderDays : sub.reminderDays.slice(0, 1);
    const amount = formatMoney(sub.price, settings.currency, locale);
    const cycle = cycleLabel(t, sub.cycle.unit, sub.cycle.every);
    const trialEnd = sub.isTrial ? parseISODate(sub.startDate) : null;

    for (const renewal of upcomingRenewals(sub, 3, addDays(now, 0))) {
      const isTrialEnd = trialEnd !== null && isSameDay(renewal, trialEnd);
      for (const d of days) {
        const fire = addDays(renewal, -d);
        fire.setHours(hour, 0, 0, 0);
        if (fire.getTime() <= now.getTime()) continue;
        const when = whenLabel(t, d);
        planned.push({
          date: fire,
          subId: sub.id,
          title: isTrialEnd
            ? t('notifTrialTitle', { name: sub.name, when })
            : t('notifTitle', { name: sub.name, when }),
          body: isTrialEnd ? t('notifTrialBody', { amount }) : t('notifBody', { amount, cycle }),
        });
      }
    }
  }

  return planned.sort((a, b) => a.date.getTime() - b.date.getTime()).slice(0, MAX_SCHEDULED);
}
