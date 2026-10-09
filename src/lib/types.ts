export type CycleUnit = 'day' | 'week' | 'month' | 'year';

export type Cycle = {
  unit: CycleUnit;
  every: number;
};

export type CategoryId =
  | 'streaming'
  | 'music'
  | 'gaming'
  | 'work'
  | 'cloud'
  | 'sport'
  | 'news'
  | 'home'
  | 'food'
  | 'education'
  | 'transport'
  | 'other';

export type SubscriptionStatus = 'active' | 'paused' | 'cancelled';

export type Subscription = {
  id: string;
  name: string;
  /** Id of the catalog entry it was created from, if any. */
  serviceId?: string;
  /** Domain used to show the service logo. */
  domain?: string;
  color: string;
  category: CategoryId;
  price: number;
  cycle: Cycle;
  /** First (paid) charge date, YYYY-MM-DD. Renewals are computed from here. */
  startDate: string;
  /** When true the period before startDate is a free trial. */
  isTrial: boolean;
  status: SubscriptionStatus;
  /** YYYY-MM-DD when the subscription was cancelled or paused. */
  statusDate?: string;
  /** Days before renewal to send a reminder. Empty = no reminder. */
  reminderDays: number[];
  /** Family member ids sharing this subscription (you excluded). */
  sharedWith: string[];
  paymentMethod?: string;
  notes?: string;
  url?: string;
  createdAt: string;
  /** Previous prices, newest last, to track increases. */
  priceHistory: { date: string; price: number }[];
};

export type FamilyMember = {
  id: string;
  name: string;
  color: string;
};

export type ThemeMode = 'system' | 'light' | 'dark';
export type Language = 'system' | 'it' | 'en';

export type Settings = {
  theme: ThemeMode;
  accent: string;
  language: Language;
  currency: string;
  monthlyBudget: number | null;
  notificationsEnabled: boolean;
  /** Hour of day (0-23) reminders are delivered. */
  reminderHour: number;
  defaultReminderDays: number[];
  biometricLock: boolean;
  showLogos: boolean;
  /** Show only your share for subscriptions split with family. */
  showMyShare: boolean;
  onboarded: boolean;
  family: FamilyMember[];
};
