import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import Animated, { FadeInDown, FadeOutDown } from 'react-native-reanimated';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { useApp } from '@/state/app';

type ToastOptions = { message: string; action?: string; onAction?: () => void; duration?: number };

const ToastContext = createContext<(opts: ToastOptions) => void>(() => {});

export function ToastProvider({ children }: { children: ReactNode }) {
  const { palette, isDark } = useApp();
  const insets = useSafeAreaInsets();
  const [toast, setToast] = useState<(ToastOptions & { id: number }) | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const show = useCallback((opts: ToastOptions) => {
    if (timer.current) clearTimeout(timer.current);
    const id = Date.now();
    setToast({ ...opts, id });
    timer.current = setTimeout(() => setToast((t) => (t?.id === id ? null : t)), opts.duration ?? 4000);
  }, []);

  return (
    <ToastContext.Provider value={show}>
      {children}
      {toast && (
        <View pointerEvents="box-none" style={[StyleSheet.absoluteFill, styles.host, { paddingBottom: insets.bottom + 96 }]}>
          <Animated.View
            key={toast.id}
            entering={FadeInDown.springify().damping(18)}
            exiting={FadeOutDown.duration(180)}
            style={[styles.toast, { backgroundColor: isDark ? '#F5F5FA' : '#15151C' }]}>
            <Text style={[styles.message, { color: isDark ? '#0B0B12' : '#FFFFFF' }]} numberOfLines={2}>
              {toast.message}
            </Text>
            {toast.action ? (
              <Pressable
                hitSlop={10}
                onPress={() => {
                  toast.onAction?.();
                  setToast(null);
                }}>
                <Text style={[styles.action, { color: palette.accent }]}>{toast.action}</Text>
              </Pressable>
            ) : null}
          </Animated.View>
        </View>
      )}
    </ToastContext.Provider>
  );
}

export function useToast() {
  return useContext(ToastContext);
}

const styles = StyleSheet.create({
  host: { justifyContent: 'flex-end', alignItems: 'center', paddingHorizontal: 16 },
  toast: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 16,
    paddingVertical: 14,
    paddingHorizontal: 18,
    borderRadius: 18,
    maxWidth: 520,
    width: '100%',
    shadowColor: '#000',
    shadowOpacity: 0.2,
    shadowRadius: 16,
    shadowOffset: { width: 0, height: 6 },
    elevation: 8,
  },
  message: { flex: 1, fontSize: 15, fontWeight: '600' },
  action: { fontSize: 15, fontWeight: '800' },
});
