import { StyleSheet, Text, View } from 'react-native';
import Svg, { Circle, Defs, LinearGradient, Path, Rect, Stop } from 'react-native-svg';

/** Brand colors of the Maik logo. They stay fixed regardless of the app accent. */
export const LOGO_COLORS = { from: '#9B7BFF', to: '#5B3DF5', spark: '#C8FF3D' };

type Props = {
  size?: number;
  /** Shows the "maik subs" wordmark next to the mark. */
  wordmark?: boolean;
  textColor?: string;
  subtitle?: string;
};

/** The Maik mark: a rounded "M" whose dot is the reminder that arrives before every renewal. */
export function MaikMark({ size = 48 }: { size?: number }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 100 100">
      <Defs>
        <LinearGradient id="maikBg" x1="0" y1="0" x2="1" y2="1">
          <Stop offset="0" stopColor={LOGO_COLORS.from} />
          <Stop offset="1" stopColor={LOGO_COLORS.to} />
        </LinearGradient>
      </Defs>
      <Rect x="0" y="0" width="100" height="100" rx="28" fill="url(#maikBg)" />
      <Path
        d="M27 71 V36 Q27 30 32 34 L50 54 L68 34 Q73 30 73 36 V71"
        stroke="#FFFFFF"
        strokeWidth={10}
        strokeLinecap="round"
        strokeLinejoin="round"
        fill="none"
      />
      <Circle cx="77" cy="23" r="9" fill={LOGO_COLORS.spark} stroke={LOGO_COLORS.to} strokeWidth={3} />
    </Svg>
  );
}

export function MaikLogo({ size = 48, wordmark = true, textColor = '#0B0B12', subtitle }: Props) {
  return (
    <View style={styles.row}>
      <MaikMark size={size} />
      {wordmark && (
        <View>
          <Text style={[styles.word, { color: textColor, fontSize: size * 0.5 }]}>
            maik<Text style={{ color: LOGO_COLORS.to }}> subs</Text>
          </Text>
          {subtitle ? (
            <Text style={[styles.subtitle, { color: textColor, fontSize: Math.max(11, size * 0.22) }]}>{subtitle}</Text>
          ) : null}
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  word: { fontWeight: '800', letterSpacing: -0.8 },
  subtitle: { opacity: 0.55, fontWeight: '600', marginTop: 1 },
});
