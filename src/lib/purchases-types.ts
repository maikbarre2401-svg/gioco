export type Plan = {
  id: string;
  kind: 'monthly' | 'yearly' | 'lifetime';
  priceString: string;
  pricePerMonth?: string;
};

export type PurchaseResult = { ok: true; premium: boolean } | { ok: false; cancelled: boolean; message?: string };

/** Entitlement identifier configured in the RevenueCat dashboard. */
export const ENTITLEMENT_ID = 'premium';

/** Subscriptions allowed in the free version. */
export const FREE_LIMIT = 8;

/** Shown when the store is not configured (demo mode, web). */
export const DEMO_PLANS: Plan[] = [
  { id: 'monthly', kind: 'monthly', priceString: '2,99 €', pricePerMonth: '2,99 €' },
  { id: 'yearly', kind: 'yearly', priceString: '19,99 €', pricePerMonth: '1,67 €' },
  { id: 'lifetime', kind: 'lifetime', priceString: '49,99 €' },
];
