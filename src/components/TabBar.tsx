import { Ionicons } from '@expo/vector-icons';
import { router } from 'expo-router';
import type { BottomTabBarProps } from 'expo-router/js-tabs';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { FREE_LIMIT } from '@/lib/purchases-types';
import { useApp } from '@/state/app';

import { haptic, Tap, type IconName } from './ui';

const ICONS: Record<string, [IconName, IconName]> = {
  index: ['home', 'home-outline'],
  calendar: ['calendar', 'calendar-outline'],
  stats: ['pie-chart', 'pie-chart-outline'],
  settings: ['person-circle', 'person-circle-outline'],
};

export function openAdd(canAddMore: boolean) {
  router.push(canAddMore ? '/add' : { pathname: '/premium', params: { reason: 'limit' } });
}

export function TabBar({ state, descriptors, navigation, insets }: BottomTabBarProps) {
  const { palette, t, canAddMore } = useApp();
  const routes = state.routes;
  const half = Math.ceil(routes.length / 2);

  const renderTab = (route: (typeof routes)[number], index: number) => {
    const focused = state.index === index;
    const { options } = descriptors[route.key];
    const label = typeof options.title === 'string' ? options.title : route.name;
    const [on, off] = ICONS[route.name] ?? ['ellipse', 'ellipse-outline'];
    return (
      <Pressable
        key={route.key}
        accessibilityRole="tab"
        accessibilityState={{ selected: focused }}
        accessibilityLabel={label}
        onPress={() => {
          const event = navigation.emit({ type: 'tabPress', target: route.key, canPreventDefault: true });
          if (!focused && !event.defaultPrevented) {
            haptic('select');
            navigation.navigate(route.name);
          }
        }}
        style={styles.tab}>
        <Ionicons name={focused ? on : off} size={24} color={focused ? palette.accent : palette.textTertiary} />
        <Text style={[styles.label, { color: focused ? palette.accent : palette.textTertiary }]} numberOfLines={1}>
          {label}
        </Text>
      </Pressable>
    );
  };

  return (
    <View style={[styles.wrap, { paddingBottom: Math.max(insets.bottom, 10) }]} pointerEvents="box-none">
      <View style={[styles.bar, { backgroundColor: palette.tabBar, borderColor: palette.border }]}>
        {routes.slice(0, half).map((r, i) => renderTab(r, i))}
        <View style={styles.addSlot}>
          <Tap
            onPress={() => openAdd(canAddMore)}
            hapticKind="medium"
            scaleTo={0.9}
            accessibilityRole="button"
            accessibilityLabel={t('tabAdd')}
            accessibilityHint={canAddMore ? undefined : t('limitReached', { n: FREE_LIMIT })}
            style={[styles.add, { backgroundColor: palette.accent, shadowColor: palette.accent }]}>
            <Ionicons name="add" size={30} color={palette.onAccent} />
          </Tap>
        </View>
        {routes.slice(half).map((r, i) => renderTab(r, i + half))}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { position: 'absolute', left: 0, right: 0, bottom: 0, alignItems: 'center', paddingHorizontal: 16 },
  bar: {
    flexDirection: 'row',
    alignItems: 'center',
    height: 68,
    borderRadius: 28,
    borderWidth: StyleSheet.hairlineWidth,
    paddingHorizontal: 6,
    width: '100%',
    maxWidth: 520,
    shadowColor: '#000',
    shadowOpacity: 0.1,
    shadowRadius: 20,
    shadowOffset: { width: 0, height: 8 },
    elevation: 12,
  },
  tab: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 3, height: '100%' },
  label: { fontSize: 10.5, fontWeight: '700' },
  addSlot: { flex: 1, alignItems: 'center' },
  add: {
    width: 54,
    height: 54,
    borderRadius: 20,
    alignItems: 'center',
    justifyContent: 'center',
    shadowOpacity: 0.45,
    shadowRadius: 12,
    shadowOffset: { width: 0, height: 6 },
    elevation: 6,
  },
});
