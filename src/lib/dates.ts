import type { Cycle, Subscription } from './types';

/** Dates are stored as local calendar days in YYYY-MM-DD form. */
export function toISODate(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

export function parseISODate(s: string): Date {
  const [y, m, d] = s.split('-').map(Number);
  return new Date(y, (m ?? 1) - 1, d ?? 1);
}

export function today(): Date {
  const d = new Date();
  return new Date(d.getFullYear(), d.getMonth(), d.getDate());
}

export function addDays(d: Date, n: number): Date {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate() + n);
}

function daysInMonth(year: number, month: number): number {
  return new Date(year, month + 1, 0).getDate();
}

/** Adds months keeping the original day when possible (Jan 31 -> Feb 28 -> Mar 31). */
export function addMonths(d: Date, n: number, anchorDay = d.getDate()): Date {
  const total = d.getMonth() + n;
  const year = d.getFullYear() + Math.floor(total / 12);
  const month = ((total % 12) + 12) % 12;
  return new Date(year, month, Math.min(anchorDay, daysInMonth(year, month)));
}

export function diffInDays(a: Date, b: Date): number {
  const utcA = Date.UTC(a.getFullYear(), a.getMonth(), a.getDate());
  const utcB = Date.UTC(b.getFullYear(), b.getMonth(), b.getDate());
  return Math.round((utcB - utcA) / 86_400_000);
}

export function isSameDay(a: Date, b: Date): boolean {
  return diffInDays(a, b) === 0;
}

/** The k-th charge date (k = 0 is the start date). */
export function occurrence(start: Date, cycle: Cycle, k: number): Date {
  const every = Math.max(1, cycle.every);
  switch (cycle.unit) {
    case 'day':
      return addDays(start, k * every);
    case 'week':
      return addDays(start, k * every * 7);
    case 'month':
      return addMonths(start, k * every, start.getDate());
    case 'year':
      return addMonths(start, k * every * 12, start.getDate());
  }
}

/** Rough length of one cycle in days, used to jump close to a target date. */
function approxCycleDays(cycle: Cycle): number {
  const every = Math.max(1, cycle.every);
  switch (cycle.unit) {
    case 'day':
      return every;
    case 'week':
      return every * 7;
    case 'month':
      return every * 30.436875;
    case 'year':
      return every * 365.2425;
  }
}

/** Index of the first occurrence on or after `from`. */
function firstIndexOnOrAfter(start: Date, cycle: Cycle, from: Date): number {
  if (diffInDays(start, from) <= 0) return 0;
  let k = Math.max(0, Math.floor(diffInDays(start, from) / approxCycleDays(cycle)) - 1);
  while (diffInDays(occurrence(start, cycle, k), from) > 0) k++;
  while (k > 0 && diffInDays(occurrence(start, cycle, k - 1), from) <= 0) k--;
  return k;
}

/** Last day the subscription can still be charged, or null when open-ended. */
function chargeLimit(sub: Subscription): Date | null {
  if (sub.status === 'active' || !sub.statusDate) return null;
  return addDays(parseISODate(sub.statusDate), -1);
}

export function nextRenewal(sub: Subscription, from: Date = today()): Date | null {
  if (sub.status !== 'active') return null;
  const start = parseISODate(sub.startDate);
  return occurrence(start, sub.cycle, firstIndexOnOrAfter(start, sub.cycle, from));
}

export function upcomingRenewals(sub: Subscription, count: number, from: Date = today()): Date[] {
  if (sub.status !== 'active') return [];
  const start = parseISODate(sub.startDate);
  const k0 = firstIndexOnOrAfter(start, sub.cycle, from);
  return Array.from({ length: count }, (_, i) => occurrence(start, sub.cycle, k0 + i));
}

/** All charge dates between `from` and `to` (inclusive). */
export function chargesBetween(sub: Subscription, from: Date, to: Date): Date[] {
  const start = parseISODate(sub.startDate);
  const limit = chargeLimit(sub);
  const end = limit && diffInDays(limit, to) > 0 ? limit : to;
  const result: Date[] = [];
  if (diffInDays(from, end) < 0) return result;
  for (let k = firstIndexOnOrAfter(start, sub.cycle, from); ; k++) {
    const d = occurrence(start, sub.cycle, k);
    if (diffInDays(d, end) < 0) break;
    result.push(d);
    if (result.length > 2000) break;
  }
  return result;
}

export function daysUntil(d: Date, from: Date = today()): number {
  return diffInDays(from, d);
}

export function isInTrial(sub: Subscription, now: Date = today()): boolean {
  return sub.isTrial && sub.status === 'active' && diffInDays(now, parseISODate(sub.startDate)) > 0;
}

export function startOfMonth(d: Date): Date {
  return new Date(d.getFullYear(), d.getMonth(), 1);
}

export function endOfMonth(d: Date): Date {
  return new Date(d.getFullYear(), d.getMonth() + 1, 0);
}
