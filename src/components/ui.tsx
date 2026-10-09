import { Ionicons } from '@expo/vector-icons';
import * as Haptics from 'expo-haptics';
import type { ComponentProps, ReactNode } from 'react';
import {
  ActivityIndicator,
  Platform,
  Pressable,
  StyleSheet,
  Switch,
  Text,
  TextInput,
  View,
  type PressableProps,
  type StyleProp,
  type TextInputProps,
  type TextProps,
  type TextStyle,
  type ViewStyle,
} from 'react-native';
import Animated, { useAnimatedStyle, useSharedValue, withSpring } from 'react-native-reanimated';

import { Radius, Space } from '@/lib/theme';
import { useApp } from '@/state/app';

export type IconName = ComponentProps<typeof Ionicons>['name'];

export function haptic(kind: 'light' | 'medium' | 'success' | 'warning' | 'select' = 'light') {
  if (Platform.OS === 'web') return;
  switch (kind) {
    case 'success':
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success).catch(() => {});
      break;
    case 'warning':
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Warning).catch(() => {});
      break;
    case 'select':
      Haptics.selectionAsync().catch(() => {});
      break;
    case 'medium':
      Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium).catch(() => {});
      break;
    default:
      Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light).catch(() => {});
  }
}

type Variant = 'display' | 'hero' | 'title' | 'heading' | 'body' | 'bodyBold' | 'caption' | 'label' | 'tiny';

const variants: Record<Variant, TextStyle> = {
  display: { fontSize: 44, fontWeight: '800', letterSpacing: -1.5 },
  hero: { fontSize: 34, fontWeight: '800', letterSpacing: -1 },
  title: { fontSize: 28, fontWeight: '800', letterSpacing: -0.8 },
  heading: { fontSize: 18, fontWeight: '700', letterSpacing: -0.3 },
  body: { fontSize: 15, fontWeight: '500' },
  bodyBold: { fontSize: 15, fontWeight: '700' },
  caption: { fontSize: 13, fontWeight: '500' },
  label: { fontSize: 12, fontWeight: '700', letterSpacing: 0.6, textTransform: 'uppercase' },
  tiny: { fontSize: 11, fontWeight: '600' },
};

export function AppText({
  variant = 'body',
  tone = 'primary',
  style,
  ...props
}: TextProps & { variant?: Variant; tone?: 'primary' | 'secondary' | 'tertiary' | 'accent' | 'danger' | 'success' | 'onAccent' }) {
  const { palette } = useApp();
  const color = {
    primary: palette.text,
    secondary: palette.textSecondary,
    tertiary: palette.textTertiary,
    accent: palette.accent,
    danger: palette.danger,
    success: palette.success,
    onAccent: palette.onAccent,
  }[tone];
  return <Text {...props} style={[variants[variant], { color, fontVariant: ['tabular-nums'] }, style]} />;
}

const AnimatedPressable = Animated.createAnimatedComponent(Pressable);

/** Pressable that gently scales down while pressed. */
export function Tap({
  style,
  scaleTo = 0.97,
  hapticKind,
  onPress,
  children,
  ...props
}: Omit<PressableProps, 'style'> & {
  style?: StyleProp<ViewStyle>;
  scaleTo?: number;
  hapticKind?: Parameters<typeof haptic>[0] | false;
  children?: ReactNode;
}) {
  const scale = useSharedValue(1);
  const animated = useAnimatedStyle(() => ({ transform: [{ scale: scale.get() }] }));
  return (
    <AnimatedPressable
      {...props}
      onPressIn={(e) => {
        scale.set(withSpring(scaleTo, { damping: 20, stiffness: 400 }));
        props.onPressIn?.(e);
      }}
      onPressOut={(e) => {
        scale.set(withSpring(1, { damping: 15, stiffness: 300 }));
        props.onPressOut?.(e);
      }}
      onPress={(e) => {
        if (hapticKind !== false) haptic(hapticKind ?? 'light');
        onPress?.(e);
      }}
      style={[animated, style]}>
      {children}
    </AnimatedPressable>
  );
}

export function Card({ style, children, padded = true }: { style?: StyleProp<ViewStyle>; children: ReactNode; padded?: boolean }) {
  const { palette } = useApp();
  return (
    <View style={[styles.card, { backgroundColor: palette.card, borderColor: palette.border }, padded && styles.cardPad, style]}>
      {children}
    </View>
  );
}

export function Icon({ name, size = 20, color }: { name: IconName; size?: number; color?: string }) {
  const { palette } = useApp();
  return <Ionicons name={name} size={size} color={color ?? palette.text} />;
}

export function Button({
  title,
  onPress,
  variant = 'primary',
  icon,
  disabled,
  loading,
  style,
}: {
  title: string;
  onPress: () => void;
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger';
  icon?: IconName;
  disabled?: boolean;
  loading?: boolean;
  style?: StyleProp<ViewStyle>;
}) {
  const { palette } = useApp();
  const bg = {
    primary: palette.accent,
    secondary: palette.cardAlt,
    ghost: 'transparent',
    danger: palette.danger + '1A',
  }[variant];
  const fg = {
    primary: palette.onAccent,
    secondary: palette.text,
    ghost: palette.accent,
    danger: palette.danger,
  }[variant];
  return (
    <Tap
      onPress={onPress}
      disabled={disabled || loading}
      accessibilityRole="button"
      accessibilityLabel={title}
      hapticKind={variant === 'primary' ? 'medium' : 'light'}
      style={[styles.button, { backgroundColor: bg, opacity: disabled ? 0.45 : 1 }, style]}>
      {loading ? (
        <ActivityIndicator color={fg} />
      ) : (
        <>
          {icon && <Ionicons name={icon} size={19} color={fg} />}
          <Text style={[styles.buttonText, { color: fg }]}>{title}</Text>
        </>
      )}
    </Tap>
  );
}

export function IconButton({
  icon,
  onPress,
  label,
  tint,
  background,
  size = 40,
}: {
  icon: IconName;
  onPress: () => void;
  label: string;
  tint?: string;
  background?: string;
  size?: number;
}) {
  const { palette } = useApp();
  return (
    <Tap
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={label}
      hitSlop={8}
      style={[
        styles.iconButton,
        { width: size, height: size, borderRadius: size / 2, backgroundColor: background ?? palette.cardAlt },
      ]}>
      <Ionicons name={icon} size={size * 0.5} color={tint ?? palette.text} />
    </Tap>
  );
}

export function Chip({
  label,
  selected,
  onPress,
  icon,
  color,
  badge,
}: {
  label: string;
  selected?: boolean;
  onPress: () => void;
  icon?: IconName;
  color?: string;
  badge?: string;
}) {
  const { palette } = useApp();
  const active = color ?? palette.accent;
  return (
    <Tap
      onPress={onPress}
      hapticKind="select"
      accessibilityRole="button"
      accessibilityState={{ selected }}
      style={[
        styles.chip,
        {
          backgroundColor: selected ? active : palette.card,
          borderColor: selected ? active : palette.border,
        },
      ]}>
      {icon && <Ionicons name={icon} size={15} color={selected ? '#fff' : palette.textSecondary} />}
      <Text style={[styles.chipText, { color: selected ? '#fff' : palette.text }]}>{label}</Text>
      {badge ? (
        <View style={[styles.chipBadge, { backgroundColor: selected ? 'rgba(255,255,255,0.25)' : palette.accentSoft }]}>
          <Text style={[styles.chipBadgeText, { color: selected ? '#fff' : palette.accent }]}>{badge}</Text>
        </View>
      ) : null}
    </Tap>
  );
}

export function Segmented<T extends string>({
  options,
  value,
  onChange,
}: {
  options: { value: T; label: string }[];
  value: T;
  onChange: (v: T) => void;
}) {
  const { palette } = useApp();
  return (
    <View style={[styles.segmented, { backgroundColor: palette.cardAlt }]}>
      {options.map((o) => {
        const selected = o.value === value;
        return (
          <Pressable
            key={o.value}
            accessibilityRole="button"
            accessibilityState={{ selected }}
            onPress={() => {
              haptic('select');
              onChange(o.value);
            }}
            style={[styles.segment, selected && { backgroundColor: palette.card }, selected && styles.segmentShadow]}>
            <Text style={[styles.segmentText, { color: selected ? palette.text : palette.textSecondary }]}>{o.label}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

export function Field({ label, children, hint, error }: { label: string; children: ReactNode; hint?: string; error?: string }) {
  return (
    <View style={{ gap: 8 }}>
      <AppText variant="label" tone="secondary">
        {label}
      </AppText>
      {children}
      {error ? (
        <AppText variant="caption" tone="danger">
          {error}
        </AppText>
      ) : hint ? (
        <AppText variant="caption" tone="tertiary">
          {hint}
        </AppText>
      ) : null}
    </View>
  );
}

export function Input(props: TextInputProps & { large?: boolean }) {
  const { palette } = useApp();
  const { large, style, ...rest } = props;
  return (
    <TextInput
      placeholderTextColor={palette.textTertiary}
      selectionColor={palette.accent}
      {...rest}
      style={[
        styles.input,
        large && styles.inputLarge,
        { backgroundColor: palette.card, color: palette.text, borderColor: palette.border },
        style,
      ]}
    />
  );
}

export function Row({
  icon,
  iconColor,
  title,
  subtitle,
  value,
  onPress,
  right,
  danger,
  last,
}: {
  icon?: IconName;
  iconColor?: string;
  title: string;
  subtitle?: string;
  value?: string;
  onPress?: () => void;
  right?: ReactNode;
  danger?: boolean;
  last?: boolean;
}) {
  const { palette } = useApp();
  const content = (
    <View style={[styles.row, !last && { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: palette.border }]}>
      {icon && (
        <View style={[styles.rowIcon, { backgroundColor: (iconColor ?? palette.accent) + '22' }]}>
          <Ionicons name={icon} size={18} color={danger ? palette.danger : iconColor ?? palette.accent} />
        </View>
      )}
      <View style={{ flex: 1 }}>
        <AppText variant="body" tone={danger ? 'danger' : 'primary'} style={{ fontWeight: '600' }}>
          {title}
        </AppText>
        {subtitle ? (
          <AppText variant="caption" tone="secondary" style={{ marginTop: 2 }}>
            {subtitle}
          </AppText>
        ) : null}
      </View>
      {value ? (
        <AppText variant="body" tone="secondary">
          {value}
        </AppText>
      ) : null}
      {right}
      {onPress && !right ? <Ionicons name="chevron-forward" size={18} color={palette.textTertiary} /> : null}
    </View>
  );
  if (!onPress) return content;
  return (
    <Pressable onPress={onPress} accessibilityRole="button" style={({ pressed }) => pressed && { opacity: 0.6 }}>
      {content}
    </Pressable>
  );
}

export function Toggle({ value, onValueChange, disabled }: { value: boolean; onValueChange: (v: boolean) => void; disabled?: boolean }) {
  const { palette } = useApp();
  return (
    <Switch
      value={value}
      disabled={disabled}
      onValueChange={(v) => {
        haptic('select');
        onValueChange(v);
      }}
      trackColor={{ true: palette.accent, false: palette.cardAlt }}
      thumbColor="#FFFFFF"
      ios_backgroundColor={palette.cardAlt}
      // react-native-web ignores thumbColor when the switch is on.
      {...({ activeThumbColor: '#FFFFFF' } as object)}
    />
  );
}

export function SectionTitle({ children, action, onAction }: { children: string; action?: string; onAction?: () => void }) {
  return (
    <View style={styles.sectionTitle}>
      <AppText variant="heading">{children}</AppText>
      {action && onAction ? (
        <Pressable onPress={onAction} hitSlop={10}>
          <AppText variant="caption" tone="accent" style={{ fontWeight: '700' }}>
            {action}
          </AppText>
        </Pressable>
      ) : null}
    </View>
  );
}

export function PremiumBadge() {
  const { palette } = useApp();
  return (
    <View style={[styles.premiumBadge, { backgroundColor: palette.accentSoft }]}>
      <Ionicons name="sparkles" size={11} color={palette.accent} />
      <Text style={[styles.premiumBadgeText, { color: palette.accent }]}>PRO</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    borderRadius: Radius.lg,
    borderWidth: StyleSheet.hairlineWidth,
  },
  cardPad: { padding: Space.lg },
  button: {
    height: 54,
    borderRadius: Radius.md + 2,
    paddingHorizontal: Space.xl,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
  },
  buttonText: { fontSize: 16, fontWeight: '700', letterSpacing: -0.2 },
  iconButton: { alignItems: 'center', justifyContent: 'center' },
  chip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 14,
    height: 36,
    borderRadius: Radius.pill,
    borderWidth: 1,
  },
  chipText: { fontSize: 14, fontWeight: '600' },
  chipBadge: { paddingHorizontal: 6, paddingVertical: 1, borderRadius: 8 },
  chipBadgeText: { fontSize: 10, fontWeight: '800' },
  segmented: { flexDirection: 'row', padding: 3, borderRadius: Radius.md - 2 },
  segment: { flex: 1, height: 34, borderRadius: Radius.sm + 2, alignItems: 'center', justifyContent: 'center' },
  segmentShadow: {
    shadowColor: '#000',
    shadowOpacity: 0.08,
    shadowRadius: 6,
    shadowOffset: { width: 0, height: 2 },
    elevation: 2,
  },
  segmentText: { fontSize: 13, fontWeight: '700' },
  input: {
    height: 52,
    borderRadius: Radius.md,
    borderWidth: 1,
    paddingHorizontal: Space.lg,
    fontSize: 16,
    fontWeight: '500',
  },
  inputLarge: { height: 76, fontSize: 36, fontWeight: '800', letterSpacing: -1 },
  row: { flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 14, minHeight: 56 },
  rowIcon: { width: 34, height: 34, borderRadius: 10, alignItems: 'center', justifyContent: 'center' },
  sectionTitle: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 },
  premiumBadge: { flexDirection: 'row', alignItems: 'center', gap: 3, paddingHorizontal: 7, paddingVertical: 3, borderRadius: 8 },
  premiumBadgeText: { fontSize: 10, fontWeight: '800', letterSpacing: 0.5 },
});
