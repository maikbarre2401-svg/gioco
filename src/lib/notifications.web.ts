import type { Translate } from './i18n';
import type { Settings, Subscription } from './types';

export const notificationsSupported = false;

export async function getPermission(): Promise<boolean> {
  return false;
}

export async function requestPermission(_t: Translate): Promise<boolean> {
  return false;
}

export async function rescheduleAll(
  _subs: Subscription[],
  _settings: Settings,
  _isPremium: boolean,
  _t: Translate,
  _locale: string,
): Promise<number> {
  return 0;
}

export async function sendTestNotification(_t: Translate): Promise<boolean> {
  return false;
}

export function addOpenListener(_onOpen: (subId: string) => void): () => void {
  return () => {};
}
