/**
 * In the browser there are no notifications. Inside the Android wrapper (/android) reminders are
 * handed to Android's AlarmManager through window.MaikAndroid, so they fire even with the app closed.
 */
import { androidBridge } from './android-bridge';
import type { Translate } from './i18n';
import { planReminders } from './reminder-plan';
import type { Settings, Subscription } from './types';

export const notificationsSupported = Boolean(androidBridge);

type Callbacks = { __maikPerm?: (granted: boolean) => void; __maikOpen?: (subId: string) => void };
const w = (typeof window !== 'undefined' ? window : {}) as Callbacks;

export async function getPermission(): Promise<boolean> {
  return androidBridge?.notificationsAllowed() ?? false;
}

export function requestPermission(_t: Translate): Promise<boolean> {
  const bridge = androidBridge;
  if (!bridge) return Promise.resolve(false);
  if (bridge.notificationsAllowed()) return Promise.resolve(true);
  return new Promise((resolve) => {
    const timer = setTimeout(() => resolve(bridge.notificationsAllowed()), 30_000);
    w.__maikPerm = (granted) => {
      clearTimeout(timer);
      w.__maikPerm = undefined;
      resolve(granted);
    };
    bridge.requestNotifications();
  });
}

export async function rescheduleAll(
  subs: Subscription[],
  settings: Settings,
  isPremium: boolean,
  t: Translate,
  locale: string,
): Promise<number> {
  if (!androidBridge) return 0;
  const planned = settings.notificationsEnabled ? planReminders(subs, settings, isPremium, t, locale) : [];
  androidBridge.schedule(
    JSON.stringify(planned.map((p) => ({ at: p.date.getTime(), title: p.title, body: p.body, subId: p.subId }))),
  );
  return planned.length;
}

export async function sendTestNotification(t: Translate): Promise<boolean> {
  if (!androidBridge || !(await requestPermission(t))) return false;
  androidBridge.test(t('testTitle'), t('testBody'));
  return true;
}

/** The Android wrapper calls window.__maikOpen(subId) when a reminder is tapped. */
export function addOpenListener(onOpen: (subId: string) => void): () => void {
  w.__maikOpen = onOpen;
  return () => {
    if (w.__maikOpen === onOpen) w.__maikOpen = undefined;
  };
}
