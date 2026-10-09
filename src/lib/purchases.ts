/**
 * Web / fallback implementation: purchases run in demo mode.
 * The native implementation lives in purchases.native.ts.
 */
import { DEMO_PLANS, type Plan, type PurchaseResult } from './purchases-types';

export type { Plan, PurchaseResult } from './purchases-types';
export { DEMO_PLANS };

export const purchasesConfigured = false;

export async function initPurchases(): Promise<boolean | null> {
  return null;
}

export async function getPlans(): Promise<Plan[]> {
  return DEMO_PLANS;
}

export async function purchase(_planId: string): Promise<PurchaseResult> {
  return { ok: true, premium: true };
}

export async function restore(): Promise<boolean | null> {
  return null;
}
