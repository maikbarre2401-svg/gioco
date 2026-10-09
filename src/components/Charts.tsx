import { useEffect } from 'react';
import { StyleSheet, View } from 'react-native';
import Animated, { useAnimatedStyle, useSharedValue, withDelay, withTiming, Easing } from 'react-native-reanimated';
import Svg, { Circle, G } from 'react-native-svg';

import { useApp } from '@/state/app';

import { AppText } from './ui';

export type Slice = { key: string; value: number; color: string };

export function DonutChart({
  data,
  size = 180,
  thickness = 22,
  centerTitle,
  centerSubtitle,
}: {
  data: Slice[];
  size?: number;
  thickness?: number;
  centerTitle?: string;
  centerSubtitle?: string;
}) {
  const { palette } = useApp();
  const total = data.reduce((a, d) => a + d.value, 0);
  const r = (size - thickness) / 2;
  const c = 2 * Math.PI * r;
  const gap = data.length > 1 ? 4 : 0;
  let offset = 0;

  return (
    <View style={{ width: size, height: size }}>
      <Svg width={size} height={size}>
        <G rotation={-90} origin={`${size / 2}, ${size / 2}`}>
          <Circle cx={size / 2} cy={size / 2} r={r} stroke={palette.cardAlt} strokeWidth={thickness} fill="none" />
          {total > 0 &&
            data.map((d) => {
              const len = (d.value / total) * c;
              const dash = Math.max(0.01, len - gap);
              const el = (
                <Circle
                  key={d.key}
                  cx={size / 2}
                  cy={size / 2}
                  r={r}
                  stroke={d.color}
                  strokeWidth={thickness}
                  strokeLinecap="butt"
                  fill="none"
                  strokeDasharray={`${dash} ${c - dash}`}
                  strokeDashoffset={-offset}
                />
              );
              offset += len;
              return el;
            })}
        </G>
      </Svg>
      <View style={[StyleSheet.absoluteFill, styles.center]}>
        {centerTitle ? <AppText variant="heading" style={{ fontSize: 20 }}>{centerTitle}</AppText> : null}
        {centerSubtitle ? (
          <AppText variant="caption" tone="secondary">
            {centerSubtitle}
          </AppText>
        ) : null}
      </View>
    </View>
  );
}

function Bar({ ratio, color, index, height }: { ratio: number; color: string; index: number; height: number }) {
  const h = useSharedValue(0);
  useEffect(() => {
    h.set(withDelay(index * 35, withTiming(ratio, { duration: 600, easing: Easing.out(Easing.cubic) })));
  }, [ratio, index, h]);
  const style = useAnimatedStyle(() => ({ height: Math.max(4, h.get() * height) }));
  return <Animated.View style={[styles.bar, { backgroundColor: color }, style]} />;
}

export function BarChart({
  data,
  height = 150,
  highlightIndex,
  format,
}: {
  data: { label: string; value: number }[];
  height?: number;
  highlightIndex?: number;
  format?: (v: number) => string;
}) {
  const { palette } = useApp();
  const max = Math.max(1, ...data.map((d) => d.value));
  const peak = data.reduce((best, d, i) => (d.value > data[best].value ? i : best), 0);
  return (
    <View>
      {format && data.length > 0 ? (
        <AppText variant="caption" tone="secondary" style={{ marginBottom: 8 }}>
          max {format(data[peak].value)}
        </AppText>
      ) : null}
      <View style={[styles.bars, { height }]}>
        {data.map((d, i) => (
          <View key={`${d.label}-${i}`} style={styles.barCol}>
            <Bar
              ratio={d.value / max}
              index={i}
              height={height}
              color={i === highlightIndex ? palette.accent : i === peak ? palette.accent + 'AA' : palette.accentSoft}
            />
          </View>
        ))}
      </View>
      <View style={styles.labels}>
        {data.map((d, i) => (
          <AppText
            key={`${d.label}-${i}`}
            variant="tiny"
            tone={i === highlightIndex ? 'accent' : 'tertiary'}
            style={styles.label}
            numberOfLines={1}>
            {d.label}
          </AppText>
        ))}
      </View>
    </View>
  );
}

/** Thin horizontal progress bar, used for the monthly budget. */
export function ProgressBar({ ratio, color, track }: { ratio: number; color: string; track: string }) {
  const w = useSharedValue(0);
  useEffect(() => {
    w.set(withTiming(Math.min(1, Math.max(0, ratio)), { duration: 700, easing: Easing.out(Easing.cubic) }));
  }, [ratio, w]);
  const style = useAnimatedStyle(() => ({ width: `${w.get() * 100}%` }));
  return (
    <View style={[styles.track, { backgroundColor: track }]}>
      <Animated.View style={[styles.fill, { backgroundColor: color }, style]} />
    </View>
  );
}

const styles = StyleSheet.create({
  center: { alignItems: 'center', justifyContent: 'center' },
  bars: { flexDirection: 'row', alignItems: 'flex-end', gap: 6 },
  barCol: { flex: 1, justifyContent: 'flex-end', height: '100%' },
  bar: { width: '100%', borderRadius: 6 },
  labels: { flexDirection: 'row', gap: 6, marginTop: 8 },
  label: { flex: 1, textAlign: 'center' },
  track: { height: 8, borderRadius: 4, overflow: 'hidden' },
  fill: { height: '100%', borderRadius: 4 },
});
