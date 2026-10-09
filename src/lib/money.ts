import { chargesBetween, diffInDays, parseISODate, today } from './dates';
import type { Cycle, FamilyMember, Subscription } from './types';

export const CURRENCIES = ['EUR', 'USD', 'GBP', 'CHF', 'SEK', 'NOK', 'DKK', 'PLN', 'JPY', 'CAD', 'AUD', 'BRL'];

const formatters = new Map<string, Intl.NumberFormat>();

export function formatMoney(value: number, currency: string, locale: string, compact = false): string {
  const key = `${locale}|${currency}|${compact}`;
  let f = formatters.get(key);
  if (!f) {
    try {
      f = new Intl.NumberFormat(locale, {
        style: 'currency',
        currency,
        maximumFractionDigits: compact ? 0 : 2,
        minimumFractionDigits: compact ? 0 : 2,
      });
    } catch {
      f = new Intl.NumberFormat(undefined, { style: 'currency', currency: 'EUR' });
    }
    formatters.set(key, f);
  }
  return f.format(value);
}

/** Accepts "13,99" and "13.99". Returns NaN when the text is not a number. */
export function parsePrice(text: string): number {
  const cleaned = text.replace(/\s/g, '').replace(/[^\d.,]/g, '');
  if (!cleaned) return NaN;
  const lastSep = Math.max(cleaned.lastIndexOf(','), cleaned.lastIndexOf('.'));
  if (lastSep === -1) return Number(cleaned);
  const int = cleaned.slice(0, lastSep).replace(/[.,]/g, '');
  const dec = cleaned.slice(lastSep + 1);
  return Number(`${int || '0'}.${dec}`);
}

/** How many charges a cycle produces in one month on average. */
export function chargesPerMonth(cycle: Cycle): number {
  const every = Math.max(1, cycle.every);
  switch (cycle.unit) {
    case 'day':
      return 30.436875 / every;
    case 'week':
      return 30.436875 / 7 / every;
    case 'month':
      return 1 / every;
    case 'year':
      return 1 / (12 * every);
  }
}

export function shareFactor(sub: Subscription, showMyShare: boolean, family: FamilyMember[]): number {
  if (!showMyShare) return 1;
  const members = sub.sharedWith.filter((id) => family.some((m) => m.id === id));
  return 1 / (members.length + 1);
}

export function effectivePrice(sub: Subscription, showMyShare: boolean, family: FamilyMember[]): number {
  return sub.price * shareFactor(sub, showMyShare, family);
}

export function monthlyCost(sub: Subscription, showMyShare = false, family: FamilyMember[] = []): number {
  return effectivePrice(sub, showMyShare, family) * chargesPerMonth(sub.cycle);
}

/** Money spent on a subscription so far (charges up to today). */
export function spentSoFar(sub: Subscription, showMyShare = false, family: FamilyMember[] = []): number {
  const start = parseISODate(sub.startDate);
  const charges = chargesBetween(sub, start, today()).length;
  return charges * effectivePrice(sub, showMyShare, family);
}

/** Money not spent thanks to a cancellation, from the cancellation date to today. */
export function savedSinceCancel(sub: Subscription, showMyShare = false, family: FamilyMember[] = []): number {
  if (sub.status !== 'cancelled' || !sub.statusDate) return 0;
  const days = Math.max(0, diffInDays(parseISODate(sub.statusDate), today()));
  return (monthlyCost(sub, showMyShare, family) * days) / 30.436875;
}
