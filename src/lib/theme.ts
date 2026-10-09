export const ACCENTS = ['#7C5CFF', '#FF5E3A', '#00B894', '#2F80ED', '#FF2D87', '#F5A400'];
export const DEFAULT_ACCENT = ACCENTS[0];

export type Palette = {
  background: string;
  card: string;
  cardAlt: string;
  text: string;
  textSecondary: string;
  textTertiary: string;
  border: string;
  accent: string;
  accentSoft: string;
  onAccent: string;
  danger: string;
  success: string;
  warning: string;
  overlay: string;
  tabBar: string;
};

/** Mixes a hex color with alpha, e.g. withAlpha('#7C5CFF', 0.15). */
export function withAlpha(hex: string, alpha: number): string {
  const a = Math.round(Math.min(1, Math.max(0, alpha)) * 255)
    .toString(16)
    .padStart(2, '0');
  return `${hex.slice(0, 7)}${a}`;
}

/** Picks black or white text for a background color. */
export function readableOn(hex: string): string {
  const n = parseInt(hex.slice(1, 7), 16);
  const r = (n >> 16) & 255;
  const g = (n >> 8) & 255;
  const b = n & 255;
  const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
  return luminance > 0.66 ? '#0B0B12' : '#FFFFFF';
}

export function makePalette(dark: boolean, accent: string): Palette {
  return dark
    ? {
        background: '#0A0A0F',
        card: '#15151C',
        cardAlt: '#1E1E27',
        text: '#F5F5FA',
        textSecondary: '#9A9DAA',
        textTertiary: '#5F6270',
        border: 'rgba(255,255,255,0.07)',
        accent,
        accentSoft: withAlpha(accent, 0.18),
        onAccent: readableOn(accent),
        danger: '#FF5468',
        success: '#2BD38A',
        warning: '#FFB020',
        overlay: 'rgba(0,0,0,0.6)',
        tabBar: 'rgba(21,21,28,0.96)',
      }
    : {
        background: '#F4F4F8',
        card: '#FFFFFF',
        cardAlt: '#EEEEF3',
        text: '#0B0B12',
        textSecondary: '#6B6F7B',
        textTertiary: '#A3A6B1',
        border: 'rgba(0,0,0,0.06)',
        accent,
        accentSoft: withAlpha(accent, 0.12),
        onAccent: readableOn(accent),
        danger: '#F0384E',
        success: '#14B371',
        warning: '#F59E0B',
        overlay: 'rgba(10,10,20,0.4)',
        tabBar: 'rgba(255,255,255,0.97)',
      };
}

export const Radius = { sm: 10, md: 16, lg: 24, xl: 32, pill: 999 } as const;
export const Space = { xs: 4, sm: 8, md: 12, lg: 16, xl: 24, xxl: 32 } as const;
export const MaxWidth = 640;
