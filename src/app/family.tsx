import { Ionicons } from '@expo/vector-icons';
import { router } from 'expo-router';
import { useState } from 'react';
import { StyleSheet, View } from 'react-native';
import Animated, { FadeInDown, FadeOut, LinearTransition } from 'react-native-reanimated';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { Screen } from '@/components/Screen';
import { AppText, Button, Card, IconButton, Input } from '@/components/ui';
import { newId } from '@/lib/backup';
import { COLOR_SWATCHES } from '@/lib/catalog';
import { monthlyCost } from '@/lib/money';
import { useApp } from '@/state/app';

export default function FamilyScreen() {
  const { settings, updateSettings, subscriptions, palette, t, money } = useApp();
  const insets = useSafeAreaInsets();
  const [name, setName] = useState('');

  const add = () => {
    const n = name.trim();
    if (!n) return;
    const color = COLOR_SWATCHES[(settings.family.length + 1) % COLOR_SWATCHES.length];
    updateSettings({ family: [...settings.family, { id: newId(), name: n.slice(0, 30), color }] });
    setName('');
  };

  const remove = (id: string) => updateSettings({ family: settings.family.filter((m) => m.id !== id) });

  /** What each member owes per month for the subscriptions shared with them. */
  const owed = (memberId: string) =>
    subscriptions
      .filter((s) => s.status === 'active' && s.sharedWith.includes(memberId))
      .reduce((a, s) => a + monthlyCost(s) / (s.sharedWith.filter((id) => settings.family.some((m) => m.id === id)).length + 1), 0);

  return (
    <View style={{ flex: 1, backgroundColor: palette.background }}>
      <View style={[styles.top, { paddingTop: insets.top + 8 }]}>
        <IconButton icon="chevron-back" label={t('goBack')} onPress={() => router.back()} />
      </View>
      <Screen tabBar={false} topInset={false}>
        <View style={{ gap: 6 }}>
          <AppText variant="title">{t('family')}</AppText>
          <AppText variant="body" tone="secondary">
            {t('familyBody')}
          </AppText>
        </View>
        <Card style={{ gap: 12 }}>
          <Input value={name} onChangeText={setName} placeholder={t('memberName')} onSubmitEditing={add} returnKeyType="done" maxLength={30} />
          <Button title={t('addMember')} icon="person-add" onPress={add} disabled={!name.trim()} />
        </Card>
        {settings.family.map((m) => (
          <Animated.View key={m.id} entering={FadeInDown} exiting={FadeOut} layout={LinearTransition}>
            <Card style={styles.member}>
              <View style={[styles.avatar, { backgroundColor: m.color }]}>
                <AppText variant="heading" style={{ color: '#fff' }}>
                  {m.name[0]?.toUpperCase()}
                </AppText>
              </View>
              <View style={{ flex: 1 }}>
                <AppText variant="bodyBold">{m.name}</AppText>
                <AppText variant="caption" tone="secondary">
                  {subscriptions.filter((s) => s.sharedWith.includes(m.id)).length} · {money(owed(m.id))} {t('perMonth')}
                </AppText>
              </View>
              <IconButton icon="trash-outline" label={t('delete')} tint={palette.danger} onPress={() => remove(m.id)} />
            </Card>
          </Animated.View>
        ))}
        {settings.family.length === 0 && (
          <View style={{ alignItems: 'center', paddingVertical: 24, gap: 8 }}>
            <Ionicons name="people-outline" size={48} color={palette.textTertiary} />
          </View>
        )}
      </Screen>
    </View>
  );
}

const styles = StyleSheet.create({
  top: { paddingHorizontal: 16, paddingBottom: 4 },
  member: { flexDirection: 'row', alignItems: 'center', gap: 14 },
  avatar: { width: 46, height: 46, borderRadius: 23, alignItems: 'center', justifyContent: 'center' },
});
