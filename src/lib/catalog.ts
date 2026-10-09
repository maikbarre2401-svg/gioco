import type { CategoryId, Cycle } from './types';

export type CategoryInfo = {
  id: CategoryId;
  icon: string;
  color: string;
};

/** Ionicons names from @expo/vector-icons. */
export const CATEGORIES: CategoryInfo[] = [
  { id: 'streaming', icon: 'tv', color: '#E50914' },
  { id: 'music', icon: 'musical-notes', color: '#1DB954' },
  { id: 'gaming', icon: 'game-controller', color: '#7B61FF' },
  { id: 'work', icon: 'briefcase', color: '#FF8A00' },
  { id: 'cloud', icon: 'cloud', color: '#2D9CDB' },
  { id: 'sport', icon: 'barbell', color: '#00B894' },
  { id: 'news', icon: 'newspaper', color: '#636E72' },
  { id: 'home', icon: 'home', color: '#F2C94C' },
  { id: 'food', icon: 'fast-food', color: '#FF5E7E' },
  { id: 'education', icon: 'school', color: '#5B8DEF' },
  { id: 'transport', icon: 'train', color: '#00A8A8' },
  { id: 'other', icon: 'apps', color: '#A0A4AB' },
];

export function categoryInfo(id: CategoryId): CategoryInfo {
  return CATEGORIES.find((c) => c.id === id) ?? CATEGORIES[CATEGORIES.length - 1];
}

export type CatalogService = {
  id: string;
  name: string;
  domain?: string;
  icon?: string;
  color: string;
  category: CategoryId;
  /** Indicative price in EUR, always editable by the user. */
  price: number;
  cycle: Cycle;
  url?: string;
};

const monthly: Cycle = { unit: 'month', every: 1 };
const yearly: Cycle = { unit: 'year', every: 1 };

export const CATALOG: CatalogService[] = [
  // Streaming
  { id: 'netflix', name: 'Netflix', domain: 'netflix.com', color: '#E50914', category: 'streaming', price: 13.99, cycle: monthly },
  { id: 'disney', name: 'Disney+', domain: 'disneyplus.com', color: '#0E47A1', category: 'streaming', price: 9.99, cycle: monthly },
  { id: 'prime', name: 'Amazon Prime', domain: 'amazon.it', color: '#00A8E1', category: 'streaming', price: 4.99, cycle: monthly },
  { id: 'now', name: 'NOW', domain: 'nowtv.it', color: '#00C9B1', category: 'streaming', price: 9.99, cycle: monthly },
  { id: 'dazn', name: 'DAZN', domain: 'dazn.com', color: '#111111', category: 'streaming', price: 34.99, cycle: monthly },
  { id: 'appletv', name: 'Apple TV+', domain: 'tv.apple.com', color: '#1C1C1E', category: 'streaming', price: 9.99, cycle: monthly },
  { id: 'paramount', name: 'Paramount+', domain: 'paramountplus.com', color: '#0064FF', category: 'streaming', price: 7.99, cycle: monthly },
  { id: 'crunchyroll', name: 'Crunchyroll', domain: 'crunchyroll.com', color: '#F47521', category: 'streaming', price: 5.99, cycle: monthly },
  { id: 'max', name: 'HBO Max', domain: 'hbomax.com', color: '#5A2DFF', category: 'streaming', price: 9.99, cycle: monthly },
  { id: 'twitch', name: 'Twitch Turbo', domain: 'twitch.tv', color: '#9146FF', category: 'streaming', price: 11.99, cycle: monthly },
  // Music
  { id: 'spotify', name: 'Spotify', domain: 'spotify.com', color: '#1DB954', category: 'music', price: 11.99, cycle: monthly },
  { id: 'applemusic', name: 'Apple Music', domain: 'music.apple.com', color: '#FA243C', category: 'music', price: 10.99, cycle: monthly },
  { id: 'youtube', name: 'YouTube Premium', domain: 'youtube.com', color: '#FF0000', category: 'music', price: 13.99, cycle: monthly },
  { id: 'amazonmusic', name: 'Amazon Music', domain: 'music.amazon.it', color: '#25D1DA', category: 'music', price: 10.99, cycle: monthly },
  { id: 'deezer', name: 'Deezer', domain: 'deezer.com', color: '#A238FF', category: 'music', price: 11.99, cycle: monthly },
  { id: 'tidal', name: 'TIDAL', domain: 'tidal.com', color: '#000000', category: 'music', price: 10.99, cycle: monthly },
  { id: 'audible', name: 'Audible', domain: 'audible.it', color: '#F8991C', category: 'music', price: 9.99, cycle: monthly },
  // Gaming
  { id: 'gamepass', name: 'Xbox Game Pass', domain: 'xbox.com', color: '#107C10', category: 'gaming', price: 14.99, cycle: monthly },
  { id: 'psplus', name: 'PlayStation Plus', domain: 'playstation.com', color: '#003791', category: 'gaming', price: 8.99, cycle: monthly },
  { id: 'nintendo', name: 'Nintendo Switch Online', domain: 'nintendo.com', color: '#E60012', category: 'gaming', price: 19.99, cycle: yearly },
  { id: 'applearcade', name: 'Apple Arcade', domain: 'apple.com', color: '#FF2D55', category: 'gaming', price: 6.99, cycle: monthly },
  // Work & AI
  { id: 'chatgpt', name: 'ChatGPT Plus', domain: 'chatgpt.com', color: '#10A37F', category: 'work', price: 23, cycle: monthly },
  { id: 'claude', name: 'Claude Pro', domain: 'claude.ai', color: '#D97757', category: 'work', price: 18, cycle: monthly },
  { id: 'm365', name: 'Microsoft 365', domain: 'microsoft.com', color: '#D83B01', category: 'work', price: 99, cycle: yearly },
  { id: 'adobe', name: 'Adobe Creative Cloud', domain: 'adobe.com', color: '#FA0F00', category: 'work', price: 61.99, cycle: monthly },
  { id: 'canva', name: 'Canva Pro', domain: 'canva.com', color: '#00C4CC', category: 'work', price: 11.99, cycle: monthly },
  { id: 'notion', name: 'Notion', domain: 'notion.so', color: '#000000', category: 'work', price: 10, cycle: monthly },
  { id: 'figma', name: 'Figma', domain: 'figma.com', color: '#A259FF', category: 'work', price: 15, cycle: monthly },
  { id: 'github', name: 'GitHub', domain: 'github.com', color: '#24292F', category: 'work', price: 4, cycle: monthly },
  { id: 'linkedin', name: 'LinkedIn Premium', domain: 'linkedin.com', color: '#0A66C2', category: 'work', price: 39.99, cycle: monthly },
  // Cloud
  { id: 'icloud', name: 'iCloud+', domain: 'icloud.com', color: '#3693F3', category: 'cloud', price: 0.99, cycle: monthly },
  { id: 'googleone', name: 'Google One', domain: 'one.google.com', color: '#4285F4', category: 'cloud', price: 1.99, cycle: monthly },
  { id: 'dropbox', name: 'Dropbox', domain: 'dropbox.com', color: '#0061FF', category: 'cloud', price: 11.99, cycle: monthly },
  { id: 'nordvpn', name: 'NordVPN', domain: 'nordvpn.com', color: '#4687FF', category: 'cloud', price: 4.99, cycle: monthly },
  { id: 'onepassword', name: '1Password', domain: '1password.com', color: '#0572EC', category: 'cloud', price: 2.99, cycle: monthly },
  // Sport & health
  { id: 'gym', name: 'Palestra', icon: 'barbell', color: '#00B894', category: 'sport', price: 39, cycle: monthly },
  { id: 'strava', name: 'Strava', domain: 'strava.com', color: '#FC4C02', category: 'sport', price: 7.99, cycle: monthly },
  { id: 'headspace', name: 'Headspace', domain: 'headspace.com', color: '#F47D31', category: 'sport', price: 12.99, cycle: monthly },
  { id: 'calm', name: 'Calm', domain: 'calm.com', color: '#3A7BD5', category: 'sport', price: 69.99, cycle: yearly },
  { id: 'pool', name: 'Piscina', icon: 'water', color: '#2D9CDB', category: 'sport', price: 45, cycle: monthly },
  // News & reading
  { id: 'kindle', name: 'Kindle Unlimited', domain: 'amazon.it', color: '#FF9900', category: 'news', price: 9.99, cycle: monthly },
  { id: 'medium', name: 'Medium', domain: 'medium.com', color: '#000000', category: 'news', price: 5, cycle: monthly },
  { id: 'ilpost', name: 'Il Post', domain: 'ilpost.it', color: '#1A1A1A', category: 'news', price: 8, cycle: monthly },
  { id: 'corriere', name: 'Corriere della Sera', domain: 'corriere.it', color: '#1D3A5F', category: 'news', price: 9.99, cycle: monthly },
  // Home & bills
  { id: 'phone', name: 'Telefono', icon: 'phone-portrait', color: '#5B8DEF', category: 'home', price: 9.99, cycle: monthly },
  { id: 'internet', name: 'Internet casa', icon: 'wifi', color: '#F2994A', category: 'home', price: 27.9, cycle: monthly },
  { id: 'carinsurance', name: 'Assicurazione auto', icon: 'car', color: '#6C5CE7', category: 'home', price: 480, cycle: yearly },
  { id: 'electricity', name: 'Luce e gas', icon: 'flash', color: '#F2C94C', category: 'home', price: 85, cycle: monthly },
  // Food
  { id: 'glovo', name: 'Glovo Prime', domain: 'glovoapp.com', color: '#FFC244', category: 'food', price: 5.99, cycle: monthly },
  { id: 'deliveroo', name: 'Deliveroo Plus', domain: 'deliveroo.it', color: '#00CCBC', category: 'food', price: 5.99, cycle: monthly },
  { id: 'justeat', name: 'Just Eat+', domain: 'justeat.it', color: '#FF8000', category: 'food', price: 4.99, cycle: monthly },
  // Education
  { id: 'duolingo', name: 'Duolingo Super', domain: 'duolingo.com', color: '#58CC02', category: 'education', price: 12.99, cycle: monthly },
  { id: 'coursera', name: 'Coursera Plus', domain: 'coursera.org', color: '#0056D2', category: 'education', price: 59, cycle: monthly },
  { id: 'udemy', name: 'Udemy', domain: 'udemy.com', color: '#A435F0', category: 'education', price: 19.99, cycle: monthly },
  // Transport
  { id: 'train', name: 'Abbonamento treno', icon: 'train', color: '#00A8A8', category: 'transport', price: 60, cycle: monthly },
  { id: 'bus', name: 'Abbonamento bus', icon: 'bus', color: '#00B894', category: 'transport', price: 35, cycle: monthly },
  { id: 'sharing', name: 'Car sharing', icon: 'car-sport', color: '#2F80ED', category: 'transport', price: 9.99, cycle: monthly },
];

export const POPULAR_IDS = ['netflix', 'spotify', 'prime', 'disney', 'youtube', 'gym', 'icloud', 'chatgpt'];

export function findService(id?: string): CatalogService | undefined {
  return id ? CATALOG.find((s) => s.id === id) : undefined;
}

/** Palette offered for custom subscriptions. */
export const COLOR_SWATCHES = [
  '#7C5CFF', '#E50914', '#1DB954', '#FF8A00', '#2D9CDB', '#00B894',
  '#FF5E7E', '#F2C94C', '#111111', '#A259FF', '#00A8A8', '#5B8DEF',
];
