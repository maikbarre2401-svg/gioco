import type { ReactNode } from 'react';
import { ScrollView, StyleSheet, View, type ScrollViewProps } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { MaxWidth } from '@/lib/theme';
import { useApp } from '@/state/app';

/** Scrollable page with safe areas, max width on tablets/web and room for the tab bar. */
export function Screen({
  children,
  tabBar = true,
  topInset = true,
  ...props
}: ScrollViewProps & { children: ReactNode; tabBar?: boolean; topInset?: boolean }) {
  const { palette } = useApp();
  const insets = useSafeAreaInsets();
  return (
    <ScrollView
      {...props}
      style={[{ flex: 1, backgroundColor: palette.background }, props.style]}
      contentContainerStyle={[
        styles.content,
        { paddingTop: (topInset ? insets.top : 0) + 12, paddingBottom: insets.bottom + (tabBar ? 120 : 40) },
        props.contentContainerStyle,
      ]}
      keyboardShouldPersistTaps="handled"
      showsVerticalScrollIndicator={false}>
      <View style={styles.inner}>{children}</View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  content: { paddingHorizontal: 16, alignItems: 'center' },
  inner: { width: '100%', maxWidth: MaxWidth, gap: 20 },
});
