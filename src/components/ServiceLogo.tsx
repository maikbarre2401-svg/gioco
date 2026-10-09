import { Ionicons } from '@expo/vector-icons';
import { Image } from 'expo-image';
import { useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { findService } from '@/lib/catalog';
import { readableOn } from '@/lib/theme';
import { useApp } from '@/state/app';

type Props = {
  name: string;
  color: string;
  domain?: string;
  serviceId?: string;
  size?: number;
};

function initials(name: string): string {
  const words = name.trim().split(/\s+/).filter(Boolean);
  if (words.length === 0) return '?';
  if (words.length === 1) return words[0][0].toUpperCase();
  return (words[0][0] + words[1][0]).toUpperCase();
}

/**
 * Brand tile: colored rounded square with the service icon or initials, and the real logo
 * on top when logos are enabled and it can be downloaded.
 */
export function ServiceLogo({ name, color, domain, serviceId, size = 48 }: Props) {
  const { settings } = useApp();
  const [failed, setFailed] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const service = findService(serviceId);
  const icon = service?.icon;
  const fg = readableOn(color);
  const radius = size * 0.3;
  const showRemote = settings.showLogos && domain && !failed && !icon;

  return (
    <View style={[styles.tile, { width: size, height: size, borderRadius: radius, backgroundColor: color }]}>
      {icon ? (
        <Ionicons name={icon as any} size={size * 0.5} color={fg} />
      ) : (
        <Text style={[styles.initials, { color: fg, fontSize: size * 0.36 }]} numberOfLines={1}>
          {initials(name)}
        </Text>
      )}
      {showRemote ? (
        <View style={[StyleSheet.absoluteFill, styles.remoteWrap, { borderRadius: radius, opacity: loaded ? 1 : 0 }]}>
          <Image
            source={{ uri: `https://www.google.com/s2/favicons?domain=${encodeURIComponent(domain)}&sz=128` }}
            style={{ width: size * 0.62, height: size * 0.62, borderRadius: size * 0.12 }}
            contentFit="contain"
            cachePolicy="disk"
            transition={150}
            onLoad={() => setLoaded(true)}
            onError={() => setFailed(true)}
            accessibilityIgnoresInvertColors
          />
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  tile: { alignItems: 'center', justifyContent: 'center', overflow: 'hidden' },
  initials: { fontWeight: '800', letterSpacing: -0.5 },
  remoteWrap: { alignItems: 'center', justifyContent: 'center', backgroundColor: '#FFFFFF' },
});
