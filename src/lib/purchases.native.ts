/**
 * In-app purchases through RevenueCat (App Store + Google Play).
 *
 * Set EXPO_PUBLIC_REVENUECAT_IOS_KEY and EXPO_PUBLIC_REVENUECAT_ANDROID_KEY to enable real
 * payments. Without keys the app runs in demo mode so every feature can be tried.
 */
import { Platform } from 'react-native';
import Purchases, { PACKAGE_TYPE, type PurchasesPackage } from 'react-native-purchases';

import { DEMO_PLANS, ENTITLEMENT_ID, type Plan, type PurchaseResult } from './purchases-types';

export type { Plan, PurchaseResult } from './purchases-types';
export { DEMO_PLANS };

const apiKey = Platform.select({
  ios: process.env.EXPO_PUBLIC_REVENUECAT_IOS_KEY,
  android: process.env.EXPO_PUBLIC_REVENUECAT_ANDROID_KEY,
});

export const purchasesConfigured = Boolean(apiKey);

let configured = false;
const packages = new Map<string, PurchasesPackage>();

/** Returns the premium status from the store, or null in demo mode. */
export async function initPurchases(): Promise<boolean | null> {
  if (!apiKey) return null;
  try {
    if (!configured) {
      Purchases.configure({ apiKey });
      configured = true;
    }
    const info = await Purchases.getCustomerInfo();
    return Boolean(info.entitlements.active[ENTITLEMENT_ID]);
  } catch {
    return null;
  }
}

function kindOf(pkg: PurchasesPackage): Plan['kind'] | null {
  switch (pkg.packageType) {
    case PACKAGE_TYPE.MONTHLY:
      return 'monthly';
    case PACKAGE_TYPE.ANNUAL:
      return 'yearly';
    case PACKAGE_TYPE.LIFETIME:
      return 'lifetime';
    default:
      return null;
  }
}

export async function getPlans(): Promise<Plan[]> {
  if (!apiKey || !configured) return DEMO_PLANS;
  try {
    const offerings = await Purchases.getOfferings();
    const current = offerings.current;
    if (!current) return DEMO_PLANS;
    const plans: Plan[] = [];
    packages.clear();
    for (const pkg of current.availablePackages) {
      const kind = kindOf(pkg);
      if (!kind) continue;
      packages.set(pkg.identifier, pkg);
      plans.push({
        id: pkg.identifier,
        kind,
        priceString: pkg.product.priceString,
        pricePerMonth: kind === 'yearly' ? pkg.product.pricePerMonthString ?? undefined : undefined,
      });
    }
    return plans.length ? plans : DEMO_PLANS;
  } catch {
    return DEMO_PLANS;
  }
}

export async function purchase(planId: string): Promise<PurchaseResult> {
  const pkg = packages.get(planId);
  if (!apiKey || !pkg) return { ok: true, premium: true };
  try {
    const { customerInfo } = await Purchases.purchasePackage(pkg);
    return { ok: true, premium: Boolean(customerInfo.entitlements.active[ENTITLEMENT_ID]) };
  } catch (e) {
    const err = e as { userCancelled?: boolean; message?: string };
    return { ok: false, cancelled: Boolean(err.userCancelled), message: err.message };
  }
}

export async function restore(): Promise<boolean | null> {
  if (!apiKey || !configured) return null;
  try {
    const info = await Purchases.restorePurchases();
    return Boolean(info.entitlements.active[ENTITLEMENT_ID]);
  } catch {
    return null;
  }
}
