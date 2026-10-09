import * as Notifications from 'expo-notifications';
import { Platform } from 'react-native';

import type { Translate } from './i18n';
import { planReminders } from './reminder-plan';
import type { Settings, Subscription } from './types';

export const notificationsSupported = true;

const CHANNEL_ID = 'renewals';

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
