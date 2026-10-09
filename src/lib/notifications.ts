import * as Notifications from 'expo-notifications';
import { Platform } from 'react-native';

import { addDays, isSameDay, parseISODate, upcomingRenewals } from './dates';
import { cycleLabel, type Translate } from './i18n';
import { formatMoney } from './money';
import type { Settings, Subscription } from './types';

export const notificationsSupported = true;

const CHANNEL_ID = 'renewals';
/** iOS keeps at most 64 pending local notifications per app. */
const MAX_SCHEDULED = 60;

Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowBanner: true,
    shouldShowList: true,
    shouldPlaySound: true,
    shouldSetBadge: false,
  }),
});

async function ensureChannel(t: Translate) {
  if (Platform.OS !== 'android') return;
  await Notifications.setNotificationChannelAsync(CHANNEL_ID, {
    name: t('channelName'),
    importance: Notifications.AndroidImportance.HIGH,
  });
}

export async function getPermission(): Promise<boolean> {
  const current = await Notifications.getPermissionsAsync();
  return current.granted;
}

export async function requestPermission(t: Translate): Promise<boolean> {
  await ensureChannel(t);
  const current = await Notifications.getPermissionsAsync();
  if (current.granted) return true;
  if (!current.canAskAgain) return false;
  const res = await Notifications.requestPermissionsAsync();
  return res.granted;
}

type Planned = { date: Date; title: string; body: string; subId: string };

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

export async function rescheduleAll(
  subs: Subscription[],
  settings: Settings,
  isPremium: boolean,
  t: Translate,
  locale: string,
): Promise<number> {
  await Notifications.cancelAllScheduledNotificationsAsync();
  if (!settings.notificationsEnabled) return 0;
  if (!(await getPermission())) return 0;
  await ensureChannel(t);

  const planned = planReminders(subs, settings, isPremium, t, locale);
  for (const p of planned) {
    await Notifications.scheduleNotificationAsync({
      content: { title: p.title, body: p.body, data: { subId: p.subId, url: `/subscription/${p.subId}` } },
      trigger: {
        type: Notifications.SchedulableTriggerInputTypes.DATE,
        date: p.date,
        channelId: CHANNEL_ID,
      },
    });
  }
  return planned.length;
}

export async function sendTestNotification(t: Translate): Promise<boolean> {
  if (!(await requestPermission(t))) return false;
  await Notifications.scheduleNotificationAsync({
    content: { title: t('testTitle'), body: t('testBody') },
    trigger: {
      type: Notifications.SchedulableTriggerInputTypes.TIME_INTERVAL,
      seconds: 2,
      channelId: CHANNEL_ID,
    },
  });
  return true;
}

/** Calls `onOpen` with the subscription id when the user taps a reminder. */
export function addOpenListener(onOpen: (subId: string) => void): () => void {
  const sub = Notifications.addNotificationResponseReceivedListener((response) => {
    const id = response.notification.request.content.data?.subId;
    if (typeof id === 'string') onOpen(id);
  });
  return () => sub.remove();
}
