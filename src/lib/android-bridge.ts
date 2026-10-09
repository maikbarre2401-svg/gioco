/**
 * Bridge to the native Android wrapper in /android (window.MaikAndroid).
 * It exists only when the web build runs inside that app; everywhere else it is undefined.
 */
export type MaikAndroidBridge = {
  notificationsAllowed(): boolean;
  requestNotifications(): void;
  /** JSON array of { at: epoch ms, title, body, subId } replacing every scheduled reminder. */
  schedule(json: string): void;
  test(title: string, body: string): void;
  vibrate(ms: number): void;
  shareText(text: string): void;
  saveFile(name: string, content: string, mimeType: string): void;
  openUrl(url: string): void;
  setBars(color: string, dark: boolean): void;
};

export const androidBridge: MaikAndroidBridge | undefined =
  typeof window !== 'undefined' ? (window as unknown as { MaikAndroid?: MaikAndroidBridge }).MaikAndroid : undefined;
