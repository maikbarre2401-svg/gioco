import { CATEGORIES } from './catalog';
import { addDays, addMonths, toISODate, today } from './dates';
import type { CategoryId, CycleUnit, FamilyMember, Subscription } from './types';

export type Backup = {
  app: 'maik-subs';
  version: 1;
  exportedAt: string;
  subscriptions: Subscription[];
  family: FamilyMember[];
};

export function buildBackup(subscriptions: Subscription[], family: FamilyMember[]): string {
  const data: Backup = {
    app: 'maik-subs',
    version: 1,
    exportedAt: new Date().toISOString(),
    subscriptions,
    family,
  };
  return JSON.stringify(data, null, 2);
}

const UNITS: CycleUnit[] = ['day', 'week', 'month', 'year'];
const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

function sanitize(raw: unknown): Subscription | null {
  if (!raw || typeof raw !== 'object') return null;
  const r = raw as Record<string, any>;
  if (typeof r.name !== 'string' || !r.name.trim()) return null;
  const price = Number(r.price);
  if (!Number.isFinite(price) || price < 0) return null;
  if (typeof r.startDate !== 'string' || !DATE_RE.test(r.startDate)) return null;
  const unit: CycleUnit = UNITS.includes(r.cycle?.unit) ? r.cycle.unit : 'month';
  const every = Math.max(1, Math.round(Number(r.cycle?.every) || 1));
  const category: CategoryId = CATEGORIES.some((c) => c.id === r.category) ? r.category : 'other';
  return {
    id: typeof r.id === 'string' ? r.id : newId(),
    name: r.name.trim().slice(0, 60),
    serviceId: typeof r.serviceId === 'string' ? r.serviceId : undefined,
    domain: typeof r.domain === 'string' ? r.domain : undefined,
    color: typeof r.color === 'string' && /^#[0-9a-fA-F]{6}/.test(r.color) ? r.color : '#7C5CFF',
    category,
    price,
    cycle: { unit, every },
    startDate: r.startDate,
    isTrial: Boolean(r.isTrial),
    status: r.status === 'paused' || r.status === 'cancelled' ? r.status : 'active',
    statusDate: typeof r.statusDate === 'string' && DATE_RE.test(r.statusDate) ? r.statusDate : undefined,
    reminderDays: Array.isArray(r.reminderDays)
      ? r.reminderDays.map(Number).filter((n: number) => Number.isInteger(n) && n >= 0 && n <= 60)
      : [3],
    sharedWith: Array.isArray(r.sharedWith) ? r.sharedWith.filter((x: unknown) => typeof x === 'string') : [],
    paymentMethod: typeof r.paymentMethod === 'string' ? r.paymentMethod : undefined,
    notes: typeof r.notes === 'string' ? r.notes : undefined,
    url: typeof r.url === 'string' ? r.url : undefined,
    createdAt: typeof r.createdAt === 'string' ? r.createdAt : new Date().toISOString(),
    priceHistory: Array.isArray(r.priceHistory)
      ? r.priceHistory.filter((p: any) => p && typeof p.date === 'string' && Number.isFinite(Number(p.price)))
      : [],
  };
}

export function parseBackup(text: string): { subscriptions: Subscription[]; family: FamilyMember[] } | null {
  try {
    const data = JSON.parse(text);
    const list = Array.isArray(data) ? data : data?.subscriptions;
    if (!Array.isArray(list)) return null;
    const subscriptions = list.map(sanitize).filter((s): s is Subscription => s !== null);
    const family: FamilyMember[] = Array.isArray(data?.family)
      ? data.family
          .filter((m: any) => m && typeof m.id === 'string' && typeof m.name === 'string')
          .map((m: any) => ({ id: m.id, name: m.name.slice(0, 30), color: typeof m.color === 'string' ? m.color : '#7C5CFF' }))
      : [];
    return { subscriptions, family };
  } catch {
    return null;
  }
}

function csvCell(v: string | number | undefined): string {
  const s = v === undefined ? '' : String(v);
  return /[",;\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

export function buildCsv(subscriptions: Subscription[], monthly: (s: Subscription) => number): string {
  const header = ['name', 'category', 'price', 'cycle_unit', 'cycle_every', 'start_date', 'status', 'monthly_cost', 'payment_method', 'notes'];
  const rows = subscriptions.map((s) =>
    [s.name, s.category, s.price.toFixed(2), s.cycle.unit, s.cycle.every, s.startDate, s.status, monthly(s).toFixed(2), s.paymentMethod, s.notes]
      .map(csvCell)
      .join(','),
  );
  return [header.join(','), ...rows].join('\n');
}

export function newId(): string {
  return `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 8)}`;
}

/** A realistic set of subscriptions to explore the app. */
export function sampleSubscriptions(): Subscription[] {
  const now = today();
  const make = (
    name: string,
    serviceId: string | undefined,
    domain: string | undefined,
    color: string,
    category: CategoryId,
    price: number,
    unit: CycleUnit,
    start: Date,
    extra: Partial<Subscription> = {},
  ): Subscription => ({
    id: newId(),
    name,
    serviceId,
    domain,
    color,
    category,
    price,
    cycle: { unit, every: 1 },
    startDate: toISODate(start),
    isTrial: false,
    status: 'active',
    reminderDays: [3],
    sharedWith: [],
    createdAt: new Date().toISOString(),
    priceHistory: [],
    ...extra,
  });
  return [
    make('Netflix', 'netflix', 'netflix.com', '#E50914', 'streaming', 13.99, 'month', addMonths(addDays(now, 3), -14), {
      priceHistory: [{ date: toISODate(addMonths(now, -5)), price: 12.99 }],
    }),
    make('Spotify', 'spotify', 'spotify.com', '#1DB954', 'music', 11.99, 'month', addMonths(addDays(now, 9), -20)),
    make('Palestra', 'gym', undefined, '#00B894', 'sport', 39, 'month', addMonths(addDays(now, 1), -7)),
    make('iCloud+', 'icloud', 'icloud.com', '#3693F3', 'cloud', 2.99, 'month', addMonths(addDays(now, 17), -30)),
    make('Microsoft 365', 'm365', 'microsoft.com', '#D83B01', 'work', 99, 'year', addMonths(addDays(now, 46), -12)),
    make('Disney+', 'disney', 'disneyplus.com', '#0E47A1', 'streaming', 9.99, 'month', addDays(now, 5), { isTrial: true, reminderDays: [2] }),
    make('DAZN', 'dazn', 'dazn.com', '#111111', 'streaming', 34.99, 'month', addMonths(now, -8), {
      status: 'cancelled',
      statusDate: toISODate(addMonths(now, -2)),
    }),
  ];
}
