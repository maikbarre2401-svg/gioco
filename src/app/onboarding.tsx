import { Ionicons } from '@expo/vector-icons';
import { router } from 'expo-router';
import { useState } from 'react';
import { ScrollView, StyleSheet, View } from 'react-native';
import Animated, { FadeIn, FadeInDown, FadeInRight } from 'react-native-reanimated';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { MaikLogo } from '@/components/MaikLogo';
import { AppText, Button, Chip, Tap, type IconName } from '@/components/ui';
import { CURRENCIES } from '@/lib/money';
import { requestPermission } from '@/lib/notifications';
import { MaxWidth } from '@/lib/theme';
import { useApp } from '@/state/app';

export default function Onboarding() {
  const { palette, t, settings, updateSettings } = useApp();
  const insets = useSafeAreaInsets();
  const [step, setStep] = useState(0);

  const slides: { icon: IconName; title: string; body: string; color: string }[] = [
    { icon: 'wallet', title: t('onb1Title'), body: t('onb1Body'), color: palette.accent },
    { icon: 'notifications', title: t('onb2Title'), body: t('onb2Body'), color: '#FF8A00' },
    { icon: 'shield-checkmark', title: t('onb3Title'), body: t('onb3Body'), color: '#14B371' },
  ];
  const last = step === slides.length - 1;
  const slide = slides[step];

  const finish = async () => {
    await requestPermission(t).catch(() => false);
    updateSettings({ onboarded: true });
    router.replace('/');
  };

  return (
    <View style={[styles.root, { backgroundColor: palette.background, paddingTop: insets.top + 16, paddingBottom: insets.bottom + 16 }]}>
      <View style={styles.inner}>
        <View style={styles.top}>
          <MaikLogo size={40} textColor={palette.text} />
          {!last && (
            <Tap onPress={() => setStep(slides.length - 1)} hapticKind={false}>
              <AppText variant="bodyBold" tone="secondary">
                {t('skip')}
              </AppText>
            </Tap>
          )}
        </View>

        <Animated.View key={step} entering={FadeInRight.duration(350)} style={styles.slide}>
          <View style={[styles.illustration, { backgroundColor: slide.color + '1A' }]}>
            <View style={[styles.illustrationInner, { backgroundColor: slide.color }]}>
              <Ionicons name={slide.icon} size={64} color="#fff" />
            </View>
          </View>
          <AppText variant="hero" style={{ textAlign: 'center' }}>
            {slide.title}
          </AppText>
          <AppText variant="body" tone="secondary" style={{ textAlign: 'center', fontSize: 17, lineHeight: 25 }}>
            {slide.body}
          </AppText>
        </Animated.View>

        {last && (
          <Animated.View entering={FadeInDown.delay(150)} style={{ gap: 10 }}>
            <AppText variant="label" tone="secondary" style={{ textAlign: 'center' }}>
              {t('chooseCurrency')}
            </AppText>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 8, paddingHorizontal: 4 }}>
              {CURRENCIES.map((c) => (
                <Chip key={c} label={c} selected={settings.currency === c} onPress={() => updateSettings({ currency: c })} />
              ))}
            </ScrollView>
          </Animated.View>
        )}

        <View style={{ gap: 18 }}>
          <View style={styles.dots}>
            {slides.map((_, i) => (
              <Animated.View
                key={i}
                entering={FadeIn}
                style={[styles.dot, { backgroundColor: i === step ? palette.accent : palette.cardAlt, width: i === step ? 24 : 8 }]}
              />
            ))}
          </View>
          <Button title={last ? t('start') : t('next')} icon={last ? 'rocket' : 'arrow-forward'} onPress={() => (last ? finish() : setStep(step + 1))} />
          <AppText variant="caption" tone="tertiary" style={{ textAlign: 'center' }}>
            {t('madeBy')}
          </AppText>
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, paddingHorizontal: 24 },
  inner: { flex: 1, width: '100%', maxWidth: MaxWidth, alignSelf: 'center', justifyContent: 'space-between', gap: 24 },
  top: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  slide: { alignItems: 'center', gap: 18 },
  illustration: { width: 200, height: 200, borderRadius: 64, alignItems: 'center', justifyContent: 'center', marginBottom: 12 },
  illustrationInner: { width: 128, height: 128, borderRadius: 42, alignItems: 'center', justifyContent: 'center' },
  dots: { flexDirection: 'row', justifyContent: 'center', gap: 6 },
  dot: { height: 8, borderRadius: 4 },
});
