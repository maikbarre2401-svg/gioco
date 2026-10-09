import { DarkTheme, DefaultTheme, Stack, ThemeProvider, router } from 'expo-router';
import * as SplashScreen from 'expo-splash-screen';
import { StatusBar } from 'expo-status-bar';
import { useEffect } from 'react';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import { LockGate } from '@/components/LockGate';
import { ToastProvider } from '@/components/Toast';
import { addOpenListener } from '@/lib/notifications';
import { AppProvider, useApp } from '@/state/app';

SplashScreen.preventAutoHideAsync().catch(() => {});

function RootNavigator() {
  const { hydrated, palette, isDark } = useApp();

  useEffect(() => {
    if (hydrated) SplashScreen.hideAsync().catch(() => {});
  }, [hydrated]);

  useEffect(() => addOpenListener((id) => router.push(`/subscription/${id}`)), []);

  const base = isDark ? DarkTheme : DefaultTheme;
  const navTheme = {
    ...base,
    colors: { ...base.colors, background: palette.background, card: palette.background, primary: palette.accent, text: palette.text, border: palette.border },
  };

  if (!hydrated) return null;

  return (
    <ThemeProvider value={navTheme}>
      <StatusBar style={isDark ? 'light' : 'dark'} />
      <ToastProvider>
        <LockGate>
          <Stack
            screenOptions={{
              headerShown: false,
              contentStyle: { backgroundColor: palette.background },
            }}>
            <Stack.Screen name="(tabs)" />
            <Stack.Screen name="add" options={{ presentation: 'modal' }} />
            <Stack.Screen name="subscription/[id]" />
            <Stack.Screen name="premium" options={{ presentation: 'modal' }} />
            <Stack.Screen name="family" />
            <Stack.Screen name="onboarding" options={{ presentation: 'fullScreenModal', gestureEnabled: false, animation: 'fade' }} />
          </Stack>
        </LockGate>
      </ToastProvider>
    </ThemeProvider>
  );
}

export default function RootLayout() {
  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <SafeAreaProvider>
        <AppProvider>
          <RootNavigator />
        </AppProvider>
      </SafeAreaProvider>
    </GestureHandlerRootView>
  );
}
