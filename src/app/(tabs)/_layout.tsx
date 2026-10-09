import { Redirect } from 'expo-router';
import { Tabs } from 'expo-router/js-tabs';

import { TabBar } from '@/components/TabBar';
import { useApp } from '@/state/app';

export default function TabsLayout() {
  const { t, settings, palette } = useApp();

  if (!settings.onboarded) return <Redirect href="/onboarding" />;

  return (
    <Tabs
      tabBar={(props) => <TabBar {...props} />}
      screenOptions={{ headerShown: false, sceneStyle: { backgroundColor: palette.background } }}>
      <Tabs.Screen name="index" options={{ title: t('tabHome') }} />
      <Tabs.Screen name="calendar" options={{ title: t('tabCalendar') }} />
      <Tabs.Screen name="stats" options={{ title: t('tabStats') }} />
      <Tabs.Screen name="settings" options={{ title: t('tabSettings') }} />
    </Tabs>
  );
}
