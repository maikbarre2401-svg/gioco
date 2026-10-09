import AsyncStorage from '@react-native-async-storage/async-storage';
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { useColorScheme } from 'react-native';

import { sampleSubscriptions } from '@/lib/backup';
import { toISODate, today } from '@/lib/dates';
import { localeFor, makeTranslator, resolveLanguage, type Lang, type Translate } from '@/lib/i18n';
import { formatMoney } from '@/lib/money';
import { rescheduleAll } from '@/lib/notifications';
import { initPurchases } from '@/lib/purchases';
import { FREE_LIMIT } from '@/lib/purchases-types';
import { DEFAULT_ACCENT, makePalette, type Palette } from '@/lib/theme';
import type { Settings, Subscription } from '@/lib/types';

const KEYS = {
  subs: 'maik.subs.v1',
  settings: 'maik.settings.v1',
  premium: 'maik.premium.v1',
};

export const DEFAULT_SETTINGS: Settings = {
  theme: 'system',
  accent: DEFAULT_ACCENT,
  language: 'system',
  currency: 'EUR',
  monthlyBudget: null,
  notificationsEnabled: true,
  reminderHour: 9,
  defaultReminderDays: [3],
  biometricLock: false,
  showLogos: true,
  showMyShare: false,
  onboarded: false,
  family: [],
};

type AppState = {
  hydrated: boolean;
  subscriptions: Subscription[];
  settings: Settings;
  isPremium: boolean;
  /** True when premium comes from a real store purchase rather than demo mode. */
  storePremium: boolean | null;
  palette: Palette;
  isDark: boolean;
  lang: Lang;
  locale: string;
  t: Translate;
  money: (value: number, compact?: boolean) => string;
  canAddMore: boolean;
  addSubscription: (sub: Subscription) => void;
  updateSubscription: (id: string, patch: Partial<Subscription>) => void;
  removeSubscription: (id: string) => Subscription | undefined;
  restoreSubscription: (sub: Subscription, index?: number) => void;
  replaceAll: (subs: Subscription[]) => void;
  updateSettings: (patch: Partial<Settings>) => void;
  setPremium: (value: boolean) => void;
  loadSample: () => void;
  resetAll: () => Promise<void>;
};

const AppContext = createContext<AppState | null>(null);

async function readJSON<T>(key: string, fallback: T): Promise<T> {
  try {
    const raw = await AsyncStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}

export function AppProvider({ children }: { children: ReactNode }) {
  const systemScheme = useColorScheme();
  const [hydrated, setHydrated] = useState(false);
  const [subscriptions, setSubscriptions] = useState<Subscription[]>([]);
  const [settings, setSettings] = useState<Settings>(DEFAULT_SETTINGS);
  const [localPremium, setLocalPremium] = useState(false);
  const [storePremium, setStorePremium] = useState<boolean | null>(null);

  useEffect(() => {
    (async () => {
      const [subs, stored, premium] = await Promise.all([
        readJSON<Subscription[]>(KEYS.subs, []),
        readJSON<Partial<Settings>>(KEYS.settings, {}),
        readJSON<boolean>(KEYS.premium, false),
      ]);
      setSubscriptions(Array.isArray(subs) ? subs : []);
      setSettings({ ...DEFAULT_SETTINGS, ...stored });
      setLocalPremium(Boolean(premium));
      setHydrated(true);
      setStorePremium(await initPurchases());
    })();
  }, []);

  useEffect(() => {
    if (hydrated) AsyncStorage.setItem(KEYS.subs, JSON.stringify(subscriptions)).catch(() => {});
  }, [subscriptions, hydrated]);

  useEffect(() => {
    if (hydrated) AsyncStorage.setItem(KEYS.settings, JSON.stringify(settings)).catch(() => {});
  }, [settings, hydrated]);

  useEffect(() => {
    if (hydrated) AsyncStorage.setItem(KEYS.premium, JSON.stringify(localPremium)).catch(() => {});
  }, [localPremium, hydrated]);

  // With RevenueCat configured the store is the source of truth; otherwise demo mode.
  const isPremium = storePremium ?? localPremium;

  const isDark = settings.theme === 'system' ? systemScheme === 'dark' : settings.theme === 'dark';
  const accent = isPremium ? settings.accent : DEFAULT_ACCENT;
  const palette = useMemo(() => makePalette(isDark, accent), [isDark, accent]);
  const lang = resolveLanguage(settings.language);
  const locale = localeFor(lang);
  const t = useMemo(() => makeTranslator(lang), [lang]);
  const money = useCallback(
    (value: number, compact = false) => formatMoney(value, settings.currency, locale, compact),
    [settings.currency, locale],
  );

  // Keep scheduled reminders in sync with the data.
  const rescheduleTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => {
    if (!hydrated) return;
    if (rescheduleTimer.current) clearTimeout(rescheduleTimer.current);
    rescheduleTimer.current = setTimeout(() => {
      rescheduleAll(subscriptions, settings, isPremium, t, locale).catch(() => {});
    }, 600);
  }, [hydrated, subscriptions, settings, isPremium, t, locale]);

  const activeCount = subscriptions.filter((s) => s.status !== 'cancelled').length;
  const canAddMore = isPremium || activeCount < FREE_LIMIT;

  const addSubscription = useCallback((sub: Subscription) => {
    setSubscriptions((list) => [sub, ...list]);
  }, []);

  const updateSubscription = useCallback((id: string, patch: Partial<Subscription>) => {
    setSubscriptions((list) =>
      list.map((s) => {
        if (s.id !== id) return s;
        const next = { ...s, ...patch };
        if (patch.price !== undefined && patch.price !== s.price) {
          next.priceHistory = [...s.priceHistory, { date: toISODate(today()), price: s.price }].slice(-20);
        }
        return next;
      }),
    );
  }, []);

  const removeSubscription = useCallback(
    (id: string) => {
      const removed = subscriptions.find((s) => s.id === id);
      setSubscriptions((list) => list.filter((s) => s.id !== id));
      return removed;
    },
    [subscriptions],
  );

  const restoreSubscription = useCallback((sub: Subscription, index = 0) => {
    setSubscriptions((list) => {
      if (list.some((s) => s.id === sub.id)) return list;
      const next = [...list];
      next.splice(Math.min(index, next.length), 0, sub);
      return next;
    });
  }, []);

  const replaceAll = useCallback((subs: Subscription[]) => setSubscriptions(subs), []);

  const updateSettings = useCallback((patch: Partial<Settings>) => {
    setSettings((s) => ({ ...s, ...patch }));
  }, []);

  const setPremium = useCallback((value: boolean) => {
    setLocalPremium(value);
    setStorePremium((store) => (store === null ? null : value));
  }, []);

  const loadSample = useCallback(() => setSubscriptions(sampleSubscriptions()), []);

  const resetAll = useCallback(async () => {
    await AsyncStorage.multiRemove([KEYS.subs, KEYS.settings]);
    setSubscriptions([]);
    setSettings({ ...DEFAULT_SETTINGS, onboarded: true });
  }, []);

  const value: AppState = {
    hydrated,
    subscriptions,
    settings,
    isPremium,
    storePremium,
    palette,
    isDark,
    lang,
    locale,
    t,
    money,
    canAddMore,
    addSubscription,
    updateSubscription,
    removeSubscription,
    restoreSubscription,
    replaceAll,
    updateSettings,
    setPremium,
    loadSample,
    resetAll,
  };

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp(): AppState {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error('useApp must be used inside AppProvider');
  return ctx;
}
