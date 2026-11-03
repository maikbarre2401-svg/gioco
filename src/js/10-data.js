'use strict';
/* ════════════════════════════════════════════════════════════════
   DATI DI RIFERIMENTO (statici, pubblici, etichettati REF/STIMA)
   Coordinate da fonti aperte; "≈" = posizione approssimata.
═══════════════════════════════════════════════════════════════════ */
const DATA = {};

/* Zone calde: base = peso storico/editoriale (0-100), il punteggio live
   viene ricalcolato da notizie reali + attività militare ADS-B. */
DATA.HOTSPOTS = [
  { id: 'UA', name: 'Ucraina', flag: '🇺🇦', lat: 48.6, lon: 35.0, range: 1400000, r: 700, base: 62,
    rx: /ukrain|ucrain|kyiv|kiev|kharkiv|kharkov|odesa|odessa|donbas|donetsk|zaporizh|kherson|crimea|luhansk|lugansk|bakhmut|pokrovsk|zelensk|dnipro|kursk|belgorod/i },
  { id: 'IL', name: 'Israele/Gaza', flag: '🇮🇱', lat: 31.6, lon: 34.8, range: 420000, r: 220, base: 58,
    rx: /gaza|israel|hamas|idf|netanyahu|west bank|cisgiordania|rafah|khan you?nis|jerusalem|gerusalemme|tel aviv|palestin/i },
  { id: 'LB', name: 'Libano/Siria', flag: '🇱🇧', lat: 34.0, lon: 36.2, range: 600000, r: 300, base: 44,
    rx: /leban|liban|hezbollah|beirut|syria|siria|damasc|aleppo|idlib|golan/i },
  { id: 'IR', name: 'Iran/Golfo', flag: '🇮🇷', lat: 30.5, lon: 53.0, range: 2200000, r: 900, base: 50,
    rx: /iran|tehran|teheran|irgc|pasdaran|khamenei|hormuz|persian gulf|golfo persico|natanz|fordow|isfahan/i },
  { id: 'YE', name: 'Yemen/Mar Rosso', flag: '🇾🇪', lat: 15.5, lon: 43.0, range: 1500000, r: 700, base: 46,
    rx: /yemen|houthi|huthi|red sea|mar rosso|bab.el.mandeb|sanaa|hodeidah|aden/i },
  { id: 'SD', name: 'Sudan', flag: '🇸🇩', lat: 14.5, lon: 29.0, range: 2000000, r: 900, base: 46,
    rx: /sudan|khartoum|darfur|el.fasher|rsf\b|rapid support|kordofan/i },
  { id: 'TW', name: 'Taiwan', flag: '🇹🇼', lat: 23.8, lon: 120.5, range: 900000, r: 450, base: 34,
    rx: /taiwan|taipei|taiwan strait|stretto di taiwan|pla navy|south china sea|mar cinese/i },
  { id: 'KP', name: 'Corea del Nord', flag: '🇰🇵', lat: 39.5, lon: 127.0, range: 1000000, r: 450, base: 34,
    rx: /north korea|corea del nord|pyongyang|kim jong|dprk/i },
  { id: 'BA', name: 'Baltico', flag: '🇪🇺', lat: 56.5, lon: 21.5, range: 1400000, r: 600, base: 24,
    rx: /baltic|baltico|kaliningrad|lithuan|lituan|latvia|letton|estonia|suwalki|gotland/i },
  { id: 'SH', name: 'Sahel', flag: '🌍', lat: 15.0, lon: 0.0, range: 2600000, r: 1100, base: 32,
    rx: /sahel|mali\b|burkina|niger\b|jnim|wagner|africa corps/i }
];

/* Basi militari (pubbliche, posizioni di massima) */
DATA.BASES = [
  ['Pentagono (Dip. Difesa USA)', 38.8719, -77.0563, 'USA', 'Comando'],
  ['Ramstein Air Base', 49.4369, 7.6003, 'USA/DE', 'Base aerea'],
  ['Aviano Air Base', 46.0319, 12.5965, 'USA/IT', 'Base aerea'],
  ['NAS Sigonella', 37.4017, 14.9224, 'USA/IT', 'Base aeronavale'],
  ['NSA Napoli (6ª Flotta)', 40.8860, 14.2908, 'USA/IT', 'Comando navale'],
  ['Incirlik Air Base', 37.0021, 35.4259, 'USA/TR', 'Base aerea'],
  ['RAF Akrotiri', 34.5904, 32.9879, 'UK/CY', 'Base aerea'],
  ['Souda Bay', 35.5317, 24.1497, 'USA/GR', 'Base aeronavale'],
  ['Naval Station Rota', 36.6453, -6.3496, 'USA/ES', 'Base navale'],
  ['RAF Lakenheath', 52.4093, 0.5610, 'USA/UK', 'Base aerea'],
  ['Al Udeid Air Base', 25.1173, 51.3150, 'USA/QA', 'Base aerea'],
  ['NSA Bahrain (5ª Flotta)', 26.2097, 50.6103, 'USA/BH', 'Comando navale'],
  ['Al Dhafra Air Base', 24.2483, 54.5477, 'USA/AE', 'Base aerea'],
  ['Ali Al Salem Air Base', 29.3467, 47.5208, 'USA/KW', 'Base aerea'],
  ['Camp Lemonnier', 11.5470, 43.1595, 'USA/DJ', 'Base expeditionary'],
  ['Base logistica PLA Gibuti', 11.5900, 43.0600, 'CN/DJ', 'Base navale ≈'],
  ['Diego Garcia', -7.3133, 72.4111, 'UK/USA', 'Base aeronavale'],
  ['Kadena Air Base', 26.3516, 127.7695, 'USA/JP', 'Base aerea'],
  ['Yokosuka (7ª Flotta)', 35.2833, 139.6667, 'USA/JP', 'Base navale'],
  ['Yokota Air Base', 35.7485, 139.3485, 'USA/JP', 'Base aerea'],
  ['Osan Air Base', 37.0906, 127.0296, 'USA/KR', 'Base aerea'],
  ['Andersen AFB (Guam)', 13.5840, 144.9300, 'USA', 'Base aerea'],
  ['Pearl Harbor–Hickam', 21.3500, -157.9500, 'USA', 'Base congiunta'],
  ['Naval Station Norfolk', 36.9466, -76.3033, 'USA', 'Base navale'],
  ['Naval Base San Diego', 32.6840, -117.1290, 'USA', 'Base navale'],
  ['Pituffik Space Base', 76.5312, -68.7031, 'USA/GL', 'Base spaziale/radar'],
  ['Guantanamo Bay', 19.9000, -75.1000, 'USA/CU', 'Base navale'],
  ['Hmeimim (status incerto)', 35.4011, 35.9486, 'RU/SY', 'Base aerea'],
  ['Tartus (status incerto)', 34.9150, 35.8800, 'RU/SY', 'Base navale ≈'],
  ['Sebastopoli (Flotta Mar Nero)', 44.6166, 33.5254, 'RU', 'Base navale'],
  ['Baltijsk (Flotta Baltico)', 54.6500, 19.9000, 'RU', 'Base navale'],
  ['Severomorsk (Flotta Nord)', 69.0700, 33.4200, 'RU', 'Base navale'],
  ['Engels-2', 51.4800, 46.2000, 'RU', 'Base bombardieri'],
  ['Vladivostok (Flotta Pacifico)', 43.1100, 131.8900, 'RU', 'Base navale'],
  ['Yulin (Hainan)', 18.2200, 109.5500, 'CN', 'Base sottomarini ≈'],
  ['Qingdao (Flotta Nord PLA)', 36.0700, 120.3800, 'CN', 'Base navale ≈'],
  ['Ream', 10.5100, 103.6300, 'KH', 'Base navale ≈']
].map(([name, lat, lon, cc, type]) => ({ name, lat, lon, cc, type }));

/* Siti nucleari (pubblici) — risk: CRIT/HIGH/MED/MON */
DATA.NUCLEAR = [
  ['Zaporizhzhia NPP', 47.5119, 34.5856, 'UA', 'Centrale (6 reattori, occupata)', 'CRIT'],
  ['Chernobyl', 51.3890, 30.0990, 'UA', 'Zona di esclusione', 'MON'],
  ['South Ukraine NPP', 47.8139, 31.2200, 'UA', 'Centrale', 'MED'],
  ['Kursk NPP', 51.6750, 35.6060, 'RU', 'Centrale (vicino al fronte)', 'HIGH'],
  ['Natanz', 33.7246, 51.7275, 'IR', 'Arricchimento uranio', 'CRIT'],
  ['Fordow', 34.8846, 50.9958, 'IR', 'Arricchimento (sotterraneo)', 'CRIT'],
  ['Isfahan UCF', 32.5700, 51.8200, 'IR', 'Conversione uranio ≈', 'HIGH'],
  ['Bushehr NPP', 28.8296, 50.8879, 'IR', 'Centrale', 'HIGH'],
  ['Arak (IR-40)', 34.3730, 49.2410, 'IR', 'Reattore ad acqua pesante', 'MED'],
  ['Yongbyon', 39.7967, 125.7536, 'KP', 'Reattore / plutonio', 'HIGH'],
  ['Punggye-ri', 41.2780, 129.0870, 'KP', 'Sito test nucleari', 'HIGH'],
  ['Dimona (Negev NRC)', 31.0016, 35.1446, 'IL', 'Centro ricerca', 'MED'],
  ['Fukushima Daiichi', 37.4211, 141.0328, 'JP', 'Smantellamento', 'MON'],
  ['Barakah NPP', 23.9586, 52.2600, 'AE', 'Centrale', 'MON'],
  ['Akkuyu NPP', 36.1440, 33.5410, 'TR', 'Centrale in costruzione', 'MON'],
  ['Los Alamos', 35.8800, -106.3031, 'US', 'Laboratorio armi', 'MON'],
  ['Pantex', 35.3155, -101.5591, 'US', 'Assemblaggio testate', 'MON'],
  ['AWE Aldermaston', 51.3600, -1.1500, 'UK', 'Armi nucleari', 'MON'],
  ['Sellafield', 54.4205, -3.4975, 'UK', 'Ritrattamento', 'MON'],
  ['La Hague', 49.6779, -1.8806, 'FR', 'Ritrattamento', 'MON'],
  ['Sarov (Arzamas-16)', 54.9333, 43.3167, 'RU', 'Centro armi', 'MED'],
  ['Novaja Zemlja', 73.3700, 54.9600, 'RU', 'Sito test ≈', 'MED'],
  ['Lop Nur', 41.6000, 88.4000, 'CN', 'Sito test ≈', 'MED']
].map(([name, lat, lon, cc, type, risk]) => ({ name, lat, lon, cc, type, risk }));

/* Colli di bottiglia marittimi strategici */
DATA.CHOKEPOINTS = [
  ['Stretto di Hormuz', 26.566, 56.25, '~20% del petrolio mondiale'],
  ['Bab el-Mandeb', 12.583, 43.333, 'Accesso al Mar Rosso'],
  ['Canale di Suez', 30.70, 32.34, '~12% del commercio mondiale'],
  ['Stretto di Malacca', 2.50, 101.30, 'Rotta Asia–Europa'],
  ['Bosforo', 41.12, 29.07, 'Accesso al Mar Nero'],
  ['Stretto di Kerch', 45.32, 36.53, 'Mar d\'Azov'],
  ['Stretto di Taiwan', 24.50, 119.60, 'Rotta Asia orientale'],
  ['Canale di Panama', 9.08, -79.68, 'Atlantico–Pacifico'],
  ['Stretto di Gibilterra', 35.96, -5.50, 'Mediterraneo–Atlantico'],
  ['Stretti danesi (Øresund)', 55.90, 12.65, 'Accesso al Baltico'],
  ['Capo di Buona Speranza', -34.36, 18.47, 'Rotta alternativa a Suez']
].map(([name, lat, lon, type]) => ({ name, lat, lon, type }));

/* Zone di conflitto (STIMA, aree indicative) */
DATA.CONFLICT_ZONES = [
  ['Fronte Ucraina orientale', 47.9, 37.6, 280], ['Striscia di Gaza', 31.42, 34.38, 30], ['Libano meridionale', 33.25, 35.45, 50],
  ['Darfur', 13.5, 24.5, 420], ['Khartoum', 15.55, 32.53, 120], ['Mar Rosso (attacchi Houthi)', 15.5, 41.5, 350],
  ['Sahel centrale', 14.5, -1.5, 700], ['Kivu (RD Congo)', -1.5, 29.0, 220], ['Myanmar', 21.0, 96.0, 450],
  ['Haiti', 18.55, -72.33, 60], ['Somalia', 3.5, 45.5, 350]
].map(([name, lat, lon, r]) => ({ name, lat, lon, r }));

/* Zone con interferenze GNSS segnalate frequentemente (STIMA) */
DATA.GPS_ZONES = [
  ['Baltico / Kaliningrad', 55.0, 21.0, 300], ['Mediterraneo orientale', 33.5, 35.2, 250], ['Mar Nero', 44.5, 33.5, 300],
  ['Golfo Persico', 27.0, 52.0, 450], ['Finlandia est / S. Pietroburgo', 60.0, 29.5, 200], ['Confine India–Pakistan', 31.0, 74.0, 200]
].map(([name, lat, lon, r]) => ({ name, lat, lon, r }));

/* ── GAZETTEER per geolocalizzare i titoli delle notizie ──
   [nomi alternativi (regex), lat, lon, etichetta, hotspot] — le città hanno priorità */
DATA.PLACES_CITY = [
  ['kyiv|kiev|kiew', 50.45, 30.52, 'Kyiv', 'UA'], ['kharkiv|kharkov', 49.99, 36.23, 'Kharkiv', 'UA'], ['odesa|odessa', 46.48, 30.72, 'Odesa', 'UA'],
  ['kherson', 46.64, 32.62, 'Kherson', 'UA'], ['zaporizhzhia|zaporizhia|zaporozhye', 47.84, 35.14, 'Zaporizhzhia', 'UA'],
  ['donetsk', 48.00, 37.80, 'Donetsk', 'UA'], ['luhansk|lugansk', 48.57, 39.31, 'Luhansk', 'UA'], ['pokrovsk', 48.28, 37.18, 'Pokrovsk', 'UA'],
  ['bakhmut', 48.59, 38.00, 'Bakhmut', 'UA'], ['dnipro', 48.46, 35.04, 'Dnipro', 'UA'], ['lviv|leopoli', 49.84, 24.03, 'Lviv', 'UA'],
  ['sumy', 50.91, 34.80, 'Sumy', 'UA'], ['kramatorsk', 48.72, 37.56, 'Kramatorsk', 'UA'],
  ['crimea|crimean|sevastopol|sebastopoli', 44.95, 34.10, 'Crimea', 'UA'], ['kursk', 51.73, 36.19, 'Kursk', 'UA'], ['belgorod', 50.60, 36.59, 'Belgorod', 'UA'],
  ['moscow|mosca|kremlin|cremlino', 55.75, 37.62, 'Mosca', null], ['st petersburg|san pietroburgo|saint petersburg', 59.93, 30.36, 'San Pietroburgo', 'BA'],
  ['kaliningrad', 54.71, 20.51, 'Kaliningrad', 'BA'], ['minsk', 53.90, 27.56, 'Minsk', null],
  ['gaza', 31.50, 34.47, 'Gaza', 'IL'], ['rafah', 31.29, 34.25, 'Rafah', 'IL'], ['khan younis|khan yunis', 31.34, 34.30, 'Khan Younis', 'IL'],
  ['jerusalem|gerusalemme', 31.77, 35.21, 'Gerusalemme', 'IL'], ['tel aviv', 32.08, 34.78, 'Tel Aviv', 'IL'],
  ['west bank|cisgiordania|jenin|nablus|ramallah', 32.00, 35.25, 'Cisgiordania', 'IL'], ['golan', 33.00, 35.75, 'Golan', 'LB'],
  ['beirut', 33.89, 35.50, 'Beirut', 'LB'], ['damascus|damasco', 33.51, 36.29, 'Damasco', 'LB'], ['aleppo', 36.20, 37.16, 'Aleppo', 'LB'], ['idlib', 35.93, 36.63, 'Idlib', 'LB'],
  ['tehran|teheran', 35.69, 51.39, 'Teheran', 'IR'], ['isfahan', 32.65, 51.67, 'Isfahan', 'IR'], ['hormuz', 26.57, 56.25, 'Hormuz', 'IR'],
  ['baghdad', 33.31, 44.37, 'Baghdad', null], ['erbil', 36.19, 44.01, 'Erbil', null],
  ['sanaa|sana\'a', 15.37, 44.19, 'Sana\'a', 'YE'], ['aden', 12.79, 45.03, 'Aden', 'YE'], ['hodeidah|hudaydah', 14.80, 42.95, 'Hodeidah', 'YE'],
  ['red sea|mar rosso', 18.0, 39.5, 'Mar Rosso', 'YE'], ['khartoum', 15.50, 32.56, 'Khartoum', 'SD'], ['darfur|el fasher|al fashir', 13.63, 25.35, 'Darfur', 'SD'],
  ['port sudan', 19.62, 37.22, 'Port Sudan', 'SD'], ['taipei', 25.03, 121.57, 'Taipei', 'TW'], ['taiwan strait|stretto di taiwan', 24.5, 119.6, 'Stretto di Taiwan', 'TW'],
  ['south china sea|mar cinese meridionale', 13.0, 114.0, 'Mar Cinese Meridionale', 'TW'], ['beijing|pechino', 39.90, 116.40, 'Pechino', null],
  ['shanghai', 31.23, 121.47, 'Shanghai', null], ['hong kong', 22.32, 114.17, 'Hong Kong', null], ['pyongyang', 39.04, 125.76, 'Pyongyang', 'KP'],
  ['seoul', 37.57, 126.98, 'Seoul', 'KP'], ['tokyo', 35.68, 139.69, 'Tokyo', null], ['washington|white house|casa bianca|pentagon|pentagono', 38.90, -77.04, 'Washington', null],
  ['new york|united nations|onu\\b|\\bun security council', 40.71, -74.01, 'New York', null], ['london|londra|downing street', 51.51, -0.13, 'Londra', null],
  ['paris|parigi|elysee', 48.86, 2.35, 'Parigi', null], ['berlin|berlino', 52.52, 13.40, 'Berlino', null], ['brussels|bruxelles|nato hq', 50.85, 4.35, 'Bruxelles', null],
  ['rome|roma|palazzo chigi|vatican|vaticano', 41.90, 12.50, 'Roma', null], ['milan|milano', 45.46, 9.19, 'Milano', null], ['naples|napoli', 40.85, 14.27, 'Napoli', null],
  ['warsaw|varsavia', 52.23, 21.01, 'Varsavia', 'BA'], ['vilnius', 54.69, 25.28, 'Vilnius', 'BA'], ['riga', 56.95, 24.11, 'Riga', 'BA'], ['tallinn', 59.44, 24.75, 'Tallinn', 'BA'],
  ['helsinki', 60.17, 24.94, 'Helsinki', 'BA'], ['stockholm|stoccolma', 59.33, 18.07, 'Stoccolma', 'BA'], ['ankara', 39.93, 32.86, 'Ankara', null],
  ['istanbul', 41.01, 28.98, 'Istanbul', null], ['cairo', 30.04, 31.24, 'Il Cairo', null], ['tripoli', 32.89, 13.19, 'Tripoli', null],
  ['kabul', 34.53, 69.17, 'Kabul', null], ['islamabad', 33.68, 73.05, 'Islamabad', null], ['new delhi|delhi', 28.61, 77.21, 'Nuova Delhi', null],
  ['kashmir', 34.08, 74.80, 'Kashmir', null], ['caracas', 10.49, -66.88, 'Caracas', null], ['havana|l\'avana', 23.11, -82.37, 'L\'Avana', null],
  ['mexico city|citta del messico', 19.43, -99.13, 'Città del Messico', null], ['bogota', 4.71, -74.07, 'Bogotà', null],
  ['port-au-prince|port au prince', 18.54, -72.34, 'Port-au-Prince', null], ['goma', -1.68, 29.22, 'Goma', null], ['mogadishu|mogadiscio', 2.05, 45.32, 'Mogadiscio', null],
  ['addis ababa', 9.03, 38.74, 'Addis Abeba', null], ['bamako', 12.64, -8.00, 'Bamako', 'SH'], ['niamey', 13.51, 2.11, 'Niamey', 'SH'],
  ['ouagadougou', 12.37, -1.52, 'Ouagadougou', 'SH'], ['lagos', 6.52, 3.38, 'Lagos', null], ['nairobi', -1.29, 36.82, 'Nairobi', null],
  ['johannesburg', -26.20, 28.05, 'Johannesburg', null], ['sydney', -33.87, 151.21, 'Sydney', null], ['manila', 14.60, 120.98, 'Manila', null],
  ['jakarta|giacarta', -6.21, 106.85, 'Giacarta', null], ['bangkok', 13.76, 100.50, 'Bangkok', null], ['dubai', 25.20, 55.27, 'Dubai', null],
  ['riyadh', 24.71, 46.68, 'Riad', null], ['doha', 25.29, 51.53, 'Doha', null], ['brasilia', -15.79, -47.88, 'Brasília', null],
  ['buenos aires', -34.60, -58.38, 'Buenos Aires', null], ['ottawa', 45.42, -75.70, 'Ottawa', null], ['los angeles', 34.05, -118.24, 'Los Angeles', null]
];
DATA.PLACES_COUNTRY = [
  ['ukrain|ucrain', 49.0, 31.4, 'Ucraina', 'UA'], ['russia|russian|russo|russi|russa|russe', 61.5, 100.0, 'Russia', null],
  ['belarus|bielorussia', 53.7, 28.0, 'Bielorussia', null], ['israel|israeli|israele|israeliano|israeliani', 31.4, 35.0, 'Israele', 'IL'],
  ['palestin', 31.9, 35.2, 'Palestina', 'IL'], ['hamas', 31.45, 34.4, 'Gaza', 'IL'], ['hezbollah|leban|libano|libanese', 33.9, 35.9, 'Libano', 'LB'],
  ['syria|siria|syrian|siriano', 35.0, 38.5, 'Siria', 'LB'], ['iran|iranian|iraniano|irgc', 32.4, 53.7, 'Iran', 'IR'],
  ['iraq|iraqi|iracheno', 33.2, 43.7, 'Iraq', null], ['yemen|houthi|huthi', 15.6, 48.0, 'Yemen', 'YE'], ['saudi|arabia saudita', 24.0, 45.0, 'Arabia Saudita', null],
  ['qatar', 25.3, 51.2, 'Qatar', null], ['united arab emirates|emirati|\\buae\\b', 24.0, 54.0, 'Emirati Arabi', null], ['oman', 21.0, 57.0, 'Oman', null],
  ['jordan|giordania', 31.2, 36.5, 'Giordania', null], ['egypt|egitto|egiziano', 26.8, 30.8, 'Egitto', null], ['libya|libia', 27.0, 17.0, 'Libia', null],
  ['tunisia', 34.0, 9.5, 'Tunisia', null], ['algeria', 28.0, 3.0, 'Algeria', null], ['morocco|marocco', 31.8, -7.1, 'Marocco', null],
  ['south sudan|sud sudan', 7.3, 30.0, 'Sud Sudan', null], ['sudan|sudanese', 15.5, 30.0, 'Sudan', 'SD'], ['ethiopia|etiopia', 9.1, 40.5, 'Etiopia', null],
  ['eritrea', 15.2, 39.8, 'Eritrea', null], ['somalia|somali|al.shabaab', 5.2, 46.2, 'Somalia', null], ['kenya', 0.0, 38.0, 'Kenya', null],
  ['congo|drc\\b|m23', -2.9, 23.7, 'RD Congo', null], ['nigeria', 9.1, 8.7, 'Nigeria', null], ['\\bmali\\b', 17.6, -4.0, 'Mali', 'SH'],
  ['burkina', 12.2, -1.6, 'Burkina Faso', 'SH'], ['\\bniger\\b', 17.6, 8.1, 'Niger', 'SH'], ['chad|ciad', 15.5, 18.7, 'Ciad', null],
  ['china|chinese|cina|cinese|cinesi|beijing', 35.9, 104.2, 'Cina', null], ['taiwan|taiwanese', 23.7, 121.0, 'Taiwan', 'TW'],
  ['north korea|corea del nord|nordcorean|north korean', 40.3, 127.5, 'Corea del Nord', 'KP'], ['south korea|corea del sud|sudcorean', 36.5, 127.9, 'Corea del Sud', null],
  ['japan|giappone|japanese|giapponese', 36.2, 138.3, 'Giappone', null], ['philippin|filippin', 12.9, 121.8, 'Filippine', null],
  ['vietnam', 14.1, 108.3, 'Vietnam', null], ['myanmar|burma|birmania', 21.9, 95.9, 'Myanmar', null], ['thailand|tailandia|thailandia', 15.9, 101.0, 'Thailandia', null],
  ['cambodia|cambogia', 12.6, 104.9, 'Cambogia', null], ['india|indian|indiano', 21.0, 78.0, 'India', null], ['pakistan', 30.4, 69.3, 'Pakistan', null],
  ['afghanistan|taliban', 33.9, 67.7, 'Afghanistan', null], ['bangladesh', 23.7, 90.4, 'Bangladesh', null], ['indonesia', -2.5, 118.0, 'Indonesia', null],
  ['australia', -25.3, 133.8, 'Australia', null], ['turkey|turkiye|turchia|turco|turkish|erdogan', 39.0, 35.2, 'Turchia', null],
  ['armenia', 40.1, 45.0, 'Armenia', null], ['azerbaijan', 40.1, 47.6, 'Azerbaigian', null], ['georgia\\b', 42.3, 43.4, 'Georgia', null],
  ['moldova|transnistria', 47.4, 28.4, 'Moldavia', null], ['poland|polonia|polish|polacco', 51.9, 19.1, 'Polonia', 'BA'],
  ['lithuania|lituania', 55.2, 23.9, 'Lituania', 'BA'], ['latvia|lettonia', 56.9, 24.6, 'Lettonia', 'BA'], ['estonia', 58.6, 25.0, 'Estonia', 'BA'],
  ['finland|finlandia', 61.9, 25.7, 'Finlandia', 'BA'], ['sweden|svezia', 60.1, 18.6, 'Svezia', null], ['norway|norvegia', 60.5, 8.5, 'Norvegia', null],
  ['denmark|danimarca|greenland|groenlandia', 56.3, 9.5, 'Danimarca', null], ['germany|germania|german|tedesco|tedeschi', 51.2, 10.4, 'Germania', null],
  ['france|francia|french|francese|macron', 46.2, 2.2, 'Francia', null], ['united kingdom|britain|british|regno unito|britannico|starmer', 54.0, -2.0, 'Regno Unito', null],
  ['ireland|irlanda', 53.4, -8.2, 'Irlanda', null], ['spain|spagna|spanish|spagnolo', 40.5, -3.7, 'Spagna', null], ['portugal|portogallo', 39.4, -8.2, 'Portogallo', null],
  ['italy|italia|italian|italiano|italiani|meloni', 41.9, 12.6, 'Italia', null], ['greece|grecia|greek', 39.1, 21.8, 'Grecia', null],
  ['serbia', 44.0, 21.0, 'Serbia', null], ['kosovo', 42.6, 20.9, 'Kosovo', null], ['hungary|ungheria|orban', 47.2, 19.5, 'Ungheria', null],
  ['romania', 45.9, 24.9, 'Romania', null], ['bulgaria', 42.7, 25.5, 'Bulgaria', null], ['netherlands|olanda|paesi bassi|dutch', 52.1, 5.3, 'Paesi Bassi', null],
  ['belgium|belgio', 50.5, 4.5, 'Belgio', null], ['switzerland|svizzera', 46.8, 8.2, 'Svizzera', null], ['austria', 47.5, 14.6, 'Austria', null],
  ['united states|u\\.s\\.|usa\\b|america|stati uniti|statunitens|trump', 39.8, -98.6, 'Stati Uniti', null], ['canada|canadian', 56.1, -106.3, 'Canada', null],
  ['mexico|messico', 23.6, -102.6, 'Messico', null], ['cuba', 21.5, -77.8, 'Cuba', null], ['haiti', 18.97, -72.29, 'Haiti', null],
  ['venezuela', 6.4, -66.6, 'Venezuela', null], ['colombia', 4.6, -74.3, 'Colombia', null], ['brazil|brasile', -14.2, -51.9, 'Brasile', null],
  ['argentina', -38.4, -63.6, 'Argentina', null], ['chile|cile', -35.7, -71.5, 'Cile', null], ['peru\\b|perù', -9.2, -75.0, 'Perù', null],
  ['ecuador', -1.8, -78.2, 'Ecuador', null], ['south africa|sudafrica', -30.6, 22.9, 'Sudafrica', null], ['antarctic|antartide', -80.0, 0.0, 'Antartide', null],
  ['arctic|artico', 80.0, 0.0, 'Artico', null]
];
/* Punti di riferimento per "sopra cosa si trova" (terra + oceani) */
DATA.OCEANS = [
  ['Oceano Pacifico', 30, -150], ['Oceano Pacifico', 0, -140], ['Oceano Pacifico', -30, -120], ['Oceano Pacifico', 20, 160], ['Oceano Pacifico', -20, -170],
  ['Oceano Pacifico', 45, -170], ['Oceano Pacifico', -45, -150], ['Oceano Pacifico', 5, 170], ['Oceano Pacifico', -10, -100], ['Oceano Pacifico', 35, 150],
  ['Oceano Atlantico', 35, -40], ['Oceano Atlantico', 10, -30], ['Oceano Atlantico', -20, -15], ['Oceano Atlantico', -40, -30], ['Oceano Atlantico', 55, -30], ['Oceano Atlantico', 25, -60],
  ['Oceano Indiano', -10, 80], ['Oceano Indiano', -30, 70], ['Oceano Indiano', 5, 65], ['Oceano Indiano', -40, 100], ['Oceano Indiano', -20, 55],
  ['Oceano Artico', 82, 0], ['Oceano Artico', 80, 160], ['Oceano Artico', 78, -120], ['Oceano Australe', -62, 0], ['Oceano Australe', -62, 120], ['Oceano Australe', -62, -120],
  ['Mar Mediterraneo', 35, 18], ['Mar Mediterraneo', 38, 5], ['Mar Mediterraneo', 34, 28], ['Mar Nero', 43.3, 34], ['Mar Caspio', 42, 51], ['Mar Rosso', 20, 38.5],
  ['Golfo Persico', 27, 51], ['Mar Cinese Meridionale', 13, 114], ['Mar del Giappone', 40, 135], ['Golfo del Messico', 25, -90], ['Mar dei Caraibi', 15, -75],
  ['Mare del Nord', 56, 3], ['Mar Baltico', 58, 20], ['Mar Arabico', 15, 63], ['Golfo del Bengala', 14, 88], ['Mar di Tasman', -38, 160], ['Mare di Bering', 58, -178]
];
DATA.LAND_EXTRA = [   // punti aggiuntivi per paesi molto estesi
  ['Russia', 56, 38], ['Russia', 64, 60], ['Russia', 66, 130], ['Russia', 55, 83], ['Russia', 62, 160], ['Russia', 70, 100],
  ['Canada', 60, -110], ['Canada', 52, -75], ['Canada', 50, -100], ['Canada', 66, -130], ['Canada', 70, -90],
  ['Stati Uniti', 35, -115], ['Stati Uniti', 42, -75], ['Stati Uniti', 32, -85], ['Stati Uniti', 45, -120], ['Stati Uniti (Alaska)', 64, -150],
  ['Brasile', -5, -65], ['Brasile', -22, -45], ['Cina', 30, 115], ['Cina', 42, 85], ['Cina (Tibet)', 31, 89], ['Cina', 45, 125],
  ['Australia', -20, 120], ['Australia', -32, 148], ['Australia', -17, 145], ['Argentina', -45, -68], ['Kazakistan', 48, 67], ['Mongolia', 46.8, 103],
  ['India', 28, 77], ['India', 13, 78], ['Indonesia', 0, 102], ['Indonesia', -4, 138], ['Arabia Saudita', 24, 45], ['Groenlandia', 72, -40],
  ['Antartide', -80, 0], ['Antartide', -75, 120], ['Antartide', -75, -100], ['Algeria', 28, 3], ['Libia', 27, 17], ['Niger', 17, 9], ['Mauritania', 20, -10],
  ['Angola', -12, 18], ['Madagascar', -19, 47], ['Nuova Zelanda', -41, 174], ['Giappone', 43, 142], ['Islanda', 65, -18], ['Perù', -10, -75], ['Bolivia', -17, -64],
  // Europa e Mediterraneo: più punti, per non confondere paesi vicini
  ['Francia', 48.8, 2.3], ['Francia', 45.7, 4.8], ['Francia', 43.6, 1.4], ['Francia', 47.2, -1.6], ['Francia', 43.3, 5.4], ['Francia', 48.6, 7.7],
  ['Germania', 52.5, 13.4], ['Germania', 48.1, 11.6], ['Germania', 50.9, 6.9], ['Germania', 53.5, 10.0], ['Germania', 49.4, 8.7],
  ['Italia', 45.5, 9.2], ['Italia', 45.4, 12.3], ['Italia', 40.8, 14.3], ['Italia', 38.1, 13.4], ['Italia', 39.2, 9.1], ['Italia', 44.5, 11.3], ['Italia', 41.1, 16.9],
  ['Spagna', 41.4, 2.2], ['Spagna', 37.4, -6.0], ['Spagna', 43.3, -2.9], ['Spagna', 39.5, -0.4], ['Regno Unito', 51.5, -0.1], ['Regno Unito', 55.9, -3.2], ['Regno Unito', 53.5, -2.2],
  ['Polonia', 52.2, 21.0], ['Polonia', 50.1, 19.9], ['Polonia', 54.4, 18.6], ['Ucraina', 50.45, 30.5], ['Ucraina', 46.5, 30.7], ['Ucraina', 48.5, 35.0], ['Ucraina', 49.8, 24.0],
  ['Turchia', 41.0, 29.0], ['Turchia', 39.9, 32.9], ['Turchia', 37.0, 35.3], ['Turchia', 38.4, 27.1], ['Paesi Bassi', 52.4, 4.9], ['Svizzera', 47.4, 8.5], ['Austria', 48.2, 16.4],
  ['Grecia', 38.0, 23.7], ['Grecia', 40.6, 22.9], ['Portogallo', 38.7, -9.1], ['Portogallo', 41.15, -8.6], ['Romania', 44.4, 26.1], ['Svezia', 59.3, 18.0], ['Svezia', 57.7, 12.0],
  ['Svezia', 63.8, 20.3], ['Norvegia', 59.9, 10.7], ['Norvegia', 63.4, 10.4], ['Norvegia', 69.6, 19.0], ['Finlandia', 60.2, 24.9], ['Finlandia', 65.0, 25.5], ['Repubblica Ceca', 50.1, 14.4],
  ['Ungheria', 47.5, 19.0], ['Serbia', 44.8, 20.5], ['Croazia', 45.8, 16.0], ['Slovenia', 46.05, 14.5], ['Bielorussia', 53.9, 27.6], ['Irlanda', 53.35, -6.26]
];

/* ── ADS-B: classificazione per tipo ICAO e callsign ── */
DATA.AC_TYPES = {
  fighter: ['F15', 'F16', 'F18', 'FA18', 'F18S', 'F18H', 'F22', 'F35', 'F14', 'F4', 'F5', 'EUFI', 'RFAL', 'TOR', 'GRIF', 'JAS39', 'SU24', 'SU25', 'SU27', 'SU30', 'SU33', 'SU34', 'SU35', 'SU57', 'MG29', 'MIG29', 'MG31', 'MIG31', 'J10', 'J11', 'J15', 'J16', 'J20', 'M2000', 'MIR2', 'A10', 'AV8B', 'HAWK', 'T38', 'L39', 'M346', 'KF21', 'JF17', 'TEJ'],
  tanker: ['K35R', 'K35E', 'KC10', 'KC46', 'KC30', 'A3TT', 'MRTT', 'KC2', 'IL78', 'K30', 'KC35', 'KC13'],
  isr: ['E3TF', 'E3CF', 'E3', 'E6', 'E8', 'E7', 'E2', 'R135', 'RC35', 'P8', 'P3', 'U2', 'EP3', 'E737', 'WC35', 'OC35', 'C30M', 'ATLA', 'P1', 'A50', 'KJ20', 'MC12', 'E767', 'E7WW'],
  transport: ['C17', 'C5', 'C5M', 'C130', 'C30J', 'C2', 'A400', 'IL76', 'AN12', 'A124', 'AN124', 'AN22', 'Y20', 'C27J', 'CN35', 'C295', 'KC39', 'C160', 'C40', 'C32', 'C37', 'Y8', 'Y9'],
  helo: ['H60', 'S70', 'UH60', 'EC35', 'EC45', 'H145', 'H135', 'AS32', 'AS50', 'AS65', 'NH90', 'CH47', 'H47', 'AH64', 'H64', 'UH1', 'B06', 'B407', 'B412', 'EC30', 'A139', 'A169', 'A189', 'AW13', 'MI8', 'MI17', 'MI24', 'KA52', 'V22', 'H53', 'S92', 'EH10', 'TIGR', 'LYNX', 'MRLN', 'SH60'],
  drone: ['MQ9', 'MQ1', 'Q9', 'HRON', 'TB2', 'TB3', 'RQ7', 'MQ4C', 'MQ4', 'RQ4', 'GLHK', 'Q4', 'RQ170', 'AKIN', 'MQ1C']
};
DATA.MIL_CALLSIGNS = ['RCH', 'REACH', 'CNV', 'PAT', 'SPAR', 'SAM', 'EXEC', 'NAVY', 'ARMY', 'USAF', 'RFR', 'FAF', 'CTM', 'GAF', 'BAF', 'IAM', 'AME', 'RRR', 'ASCOT', 'PLF', 'NATO', 'LAGR', 'FORTE', 'HOMER', 'JAKE', 'DUKE', 'HKY', 'QID', 'NCHO', 'TOPCAT', 'SNTRY', 'MMF', 'HAVOC', 'VIPER', 'COBRA', 'BOLT', 'IRON', 'NAF', 'HUN', 'CFC', 'KAF', 'RSD', 'AIO', 'MAGMA', 'DOOM', 'GOLD', 'POLO', 'TARTN', 'KNIFE', 'BLKCAT'];
DATA.AC_CLASS = {
  civil: { label: 'CIVILE', icon: '✈', col: '#00c8ff' }, mil: { label: 'MILITARE', icon: '⚔', col: '#ff7a1a' },
  fighter: { label: 'CACCIA', icon: '🔺', col: '#ff1744' }, tanker: { label: 'RIFORNITORE', icon: '⛽', col: '#ffb300' },
  isr: { label: 'ISR / AWACS', icon: '📡', col: '#d14dff' }, transport: { label: 'TRASPORTO MIL.', icon: '📦', col: '#ff9f40' },
  helo: { label: 'ELICOTTERO', icon: '🚁', col: '#ffe000' }, drone: { label: 'UAV / DRONE', icon: '🔻', col: '#00ff41' },
  vip: { label: 'VIP / GOVERNO', icon: '⭐', col: '#ffffff' }
};
DATA.SQUAWK = { '7500': 'DIROTTAMENTO (7500)', '7600': 'AVARIA RADIO (7600)', '7700': 'EMERGENZA GENERALE (7700)' };
DATA.AIRLINES = { RYR: 'Ryanair', EZY: 'easyJet', BAW: 'British Airways', DLH: 'Lufthansa', AFR: 'Air France', ITY: 'ITA Airways', UAE: 'Emirates', QTR: 'Qatar Airways', THY: 'Turkish Airlines', SWR: 'Swiss', KLM: 'KLM', IBE: 'Iberia', UAL: 'United', AAL: 'American', DAL: 'Delta', JAL: 'Japan Airlines', ANA: 'ANA', SIA: 'Singapore Airlines', QFA: 'Qantas', VLG: 'Vueling', WZZ: 'Wizz Air', SAS: 'SAS', AUA: 'Austrian', TAP: 'TAP', ETD: 'Etihad', CCA: 'Air China', CES: 'China Eastern', CSN: 'China Southern', AIC: 'Air India', FDX: 'FedEx', UPS: 'UPS', ACA: 'Air Canada', SWA: 'Southwest', NAX: 'Norwegian', EJU: 'easyJet Europe', AEE: 'Aegean', LOT: 'LOT', ELY: 'El Al', SVA: 'Saudia', KAL: 'Korean Air', CPA: 'Cathay Pacific', EVA: 'EVA Air', THA: 'Thai', MAS: 'Malaysia', GTI: 'Atlas Air', CLX: 'Cargolux', NOS: 'Neos', AZA: 'ITA/Alitalia' };

/* ── Satelliti: gruppi CelesTrak ── */
DATA.SAT_GROUPS = [
  { id: 'stations', label: 'Stazioni', col: '#ffd700', on: true },
  { id: 'visual', label: 'Più luminosi', col: '#e0e0ff', on: true },
  { id: 'gps-ops', label: 'GPS', col: '#00ffcc', on: true },
  { id: 'galileo', label: 'Galileo', col: '#3d8bff', on: true },
  { id: 'glo-ops', label: 'GLONASS', col: '#ff5566', on: true },
  { id: 'beidou', label: 'BeiDou', col: '#ffaa00', on: false },
  { id: 'weather', label: 'Meteo', col: '#66ccff', on: true },
  { id: 'military', label: 'Militari', col: '#ff4400', on: true },
  { id: 'geo', label: 'Geostazionari', col: '#b388ff', on: false },
  { id: 'starlink', label: 'Starlink', col: '#9e9e9e', on: false }
];

/* ── Notizie: feed RSS ── */
DATA.FEEDS = [
  { id: 'bbc', src: 'BBC World', flag: '🇬🇧', cc: 'uk', url: 'https://feeds.bbci.co.uk/news/world/rss.xml' },
  { id: 'aje', src: 'Al Jazeera', flag: '📡', cc: 'gl', url: 'https://www.aljazeera.com/xml/rss/all.xml' },
  { id: 'ansa', src: 'ANSA Mondo', flag: '🇮🇹', cc: 'it', url: 'https://www.ansa.it/sito/notizie/mondo/mondo_rss.xml' },
  { id: 'rai', src: 'RaiNews Esteri', flag: '🇮🇹', cc: 'it', url: 'https://www.rainews.it/rss/esteri' },
  { id: 'dw', src: 'DW', flag: '🇩🇪', cc: 'eu', url: 'https://rss.dw.com/xml/rss-en-world' },
  { id: 'grd', src: 'The Guardian', flag: '🇬🇧', cc: 'uk', url: 'https://www.theguardian.com/world/rss' },
  { id: 'f24', src: 'France 24', flag: '🇫🇷', cc: 'eu', url: 'https://www.france24.com/en/rss' },
  { id: 'nyt', src: 'NYT World', flag: '🇺🇸', cc: 'us', url: 'https://rss.nytimes.com/services/xml/rss/nyt/World.xml' },
  { id: 'npr', src: 'NPR World', flag: '🇺🇸', cc: 'us', url: 'https://feeds.npr.org/1004/rss.xml' },
  { id: 'sky', src: 'Sky News', flag: '🇬🇧', cc: 'uk', url: 'https://feeds.skynews.com/feeds/rss/world.xml' },
  { id: 'dn', src: 'Defense News', flag: '🛡', cc: 'us', url: 'https://www.defensenews.com/arc/outboundfeeds/rss/?outputType=xml' },
  { id: 'toi', src: 'Times of Israel', flag: '🇮🇱', cc: 'gl', url: 'https://www.timesofisrael.com/feed/' }
];
/* parole chiave → gravità (0..1) e categorie */
DATA.SEVERITY = [
  [/nuclear|nucleare|atomic|warhead|testata/i, 0.9, 'nuke'], [/invasion|invasione|invade/i, 0.9, 'mil'], [/coup|golpe/i, 0.8, 'pol'],
  [/missile|ballistic|balistic|icbm|hypersonic|ipersonic/i, 0.8, 'mil'], [/terror|terroris|bombing|attentato|suicide/i, 0.8, 'mil'],
  [/air ?strike|airstrike|raid aereo|bombard|shelling|strike[sd]? on|colpit/i, 0.7, 'mil'], [/killed|dead|deaths|morti|uccis|vittime|massacre|strage/i, 0.6, 'mil'],
  [/attack|attacco|attacchi|assault|offensiv/i, 0.6, 'mil'], [/explosion|esplosion|blast/i, 0.6, 'mil'], [/drone/i, 0.5, 'mil'],
  [/\bwar\b|guerra|conflict|conflitto|combat|battle|battaglia|fighting|combattimenti/i, 0.5, 'mil'], [/troops|truppe|soldier|soldati|army|esercito|military|militar/i, 0.4, 'mil'],
  [/navy|naval|warship|destroyer|carrier|portaerei|fregata|submarine|sottomarin/i, 0.4, 'sea'], [/ship|vessel|tanker|maritime|shipping|nave|navi|petroliera/i, 0.3, 'sea'],
  [/cyber|hack|ransomware|malware|breach|data leak|ddos/i, 0.5, 'cyber'], [/earthquake|terremoto|sisma|tsunami|eruption|eruzione|volcan|vulcan|hurricane|uragano|typhoon|tifone|cyclone|ciclone|flood|alluvion|wildfire|incendi/i, 0.5, 'dis'],
  [/hostage|ostagg|hijack|dirott/i, 0.7, 'mil'], [/sanction|sanzion/i, 0.25, 'eco'], [/ceasefire|tregua|cessate il fuoco|truce|peace talks|negoziat/i, 0.25, 'pol'],
  [/protest|protesta|riot|scontri|unrest/i, 0.35, 'pol'], [/oil|petrolio|gas price|opec/i, 0.2, 'eco']
];

/* ── TV live (canali ufficiali YouTube; la diretta corrente si risolve dal canale) ── */
DATA.TV = [
  { id: 'aje', cat: 'news', label: 'Al Jazeera EN', flag: '📡', ch: 'UCNye-wNBqNL5ZzHSJj3l8Bg' },
  { id: 'dw', cat: 'news', label: 'DW News', flag: '🇩🇪', ch: 'UCknLrEdhRCp1aegoMqRaCZg' },
  { id: 'f24', cat: 'news', label: 'France 24 EN', flag: '🇫🇷', ch: 'UCQfwfsi5VrQ8yKZ-UWmAEFg' },
  { id: 'sky', cat: 'news', label: 'Sky News', flag: '🇬🇧', ch: 'UCoMdktPbSTixAyNGwb-UYkQ' },
  { id: 'eun', cat: 'news', label: 'Euronews', flag: '🇪🇺', ch: 'UCSrZ3UV4jOidv8ppoVuvW9Q' },
  { id: 'bbg', cat: 'news', label: 'Bloomberg', flag: '💹', ch: 'UCIALMKvObZNtJ6AmdCLP7Lg' },
  { id: 'cna', cat: 'news', label: 'CNA Asia', flag: '🇸🇬', ch: 'UC83jt4dlz1Gjl58fzQrrKZg' },
  { id: 'abcau', cat: 'news', label: 'ABC News AU', flag: '🇦🇺', ch: 'UCVgO39Bk5sMo66-6o6Spn6Q' },
  { id: 'nbc', cat: 'news', label: 'NBC News', flag: '🇺🇸', ch: 'UCeY0bbntWzzVIaj2z3QigXg' },
  { id: 'livenow', cat: 'news', label: 'LiveNOW FOX', flag: '🇺🇸', ch: 'UCJg9wBPyKMNA5sRDnvzmkdg' },
  { id: 'trt', cat: 'war', label: 'TRT World', flag: '🇹🇷', ch: 'UC7fWeaHhqgM4Ry-RMpM2YYw' },
  { id: 'wion', cat: 'war', label: 'WION', flag: '🇮🇳', ch: 'UC_gUM8rL-Lrg6O3adPW9K1g' },
  { id: 'aja', cat: 'war', label: 'Al Jazeera AR', flag: '🌙', ch: 'UCfiwzLy-8yKzIbsmZTzxDgw' },
  { id: 'i24', cat: 'war', label: 'i24NEWS EN', flag: '🇮🇱', ch: 'UCvHDpsWKADrDia0c99X37vg' },
  { id: 'nhk', cat: 'war', label: 'NHK World', flag: '🇯🇵', ch: 'UCSPEjw8F2nQDtmUKPFNF7_A' },
  { id: 'f24fr', cat: 'war', label: 'France 24 FR', flag: '🇫🇷', ch: 'UCCCPCZNChQdGa9EkATeye4g' },
  { id: 'nasa', cat: 'sci', label: 'NASA', flag: '🚀', ch: 'UCLA_DiR1FfKNvjuUpBHmylQ' },
  { id: 'esa', cat: 'sci', label: 'ESA', flag: '🇪🇺', ch: 'UCIBaDdAbGlFDeS33shmlD0A' },
  { id: 'nsf', cat: 'sci', label: 'NASASpaceflight', flag: '🛰', ch: 'UCSUu1lih2RifWkKtDOJdsBA' },
  { id: 'spacex', cat: 'sci', label: 'SpaceX', flag: '🚀', ch: 'UCtI0Hodo5o5dUb67FeUjDeA' }
];
/* Webcam: ID video YouTube (scadono: modificabili dall'interfaccia) */
DATA.WEBCAMS = [
  { city: 'Roma', flag: '🇮🇹', lat: 41.9, lon: 12.5, yt: 'Wk4qXuFROnE' },
  { city: 'Venezia', flag: '🇮🇹', lat: 45.43, lon: 12.33, yt: 'A_Cnd2WW9SU' },
  { city: 'New York', flag: '🇺🇸', lat: 40.758, lon: -73.985, yt: 'rnXIjl_Rzy4' },
  { city: 'Tokyo', flag: '🇯🇵', lat: 35.66, lon: 139.70, yt: 'DjdUEyjx8GM' },
  { city: 'Londra', flag: '🇬🇧', lat: 51.5, lon: -0.12, yt: 'Mt3xORZ4G3M' },
  { city: 'Parigi', flag: '🇫🇷', lat: 48.858, lon: 2.294, yt: 'kfWVnQiUJ_4' },
  { city: 'Dubai', flag: '🇦🇪', lat: 25.2, lon: 55.27, yt: '7c0o_Tg3eGc' },
  { city: 'Praga', flag: '🇨🇿', lat: 50.087, lon: 14.42, yt: 'mNXkbDdQv5w' },
  { city: 'Jackson Hole', flag: '🇺🇸', lat: 43.48, lon: -110.76, yt: '1EiC9bvVGnk' }
];

/* ── Mercati ── */
DATA.MARKETS = {
  idx: [['^GSPC', 'S&P 500', '^spx'], ['^IXIC', 'Nasdaq', '^ndq'], ['^DJI', 'Dow Jones', '^dji'], ['^VIX', 'VIX (paura)', null],
    ['^STOXX50E', 'Euro Stoxx 50', null], ['FTSEMIB.MI', 'FTSE MIB', null], ['^GDAXI', 'DAX', '^dax'], ['^N225', 'Nikkei 225', '^nkx']],
  com: [['GC=F', 'Oro', 'gc.f'], ['SI=F', 'Argento', 'si.f'], ['CL=F', 'Petrolio WTI', 'cl.f'], ['BZ=F', 'Petrolio Brent', 'cb.f'],
    ['NG=F', 'Gas naturale USA', 'ng.f'], ['TTF=F', 'Gas TTF Europa', null], ['HG=F', 'Rame', 'hg.f'], ['ZW=F', 'Grano', 'zw.f']],
  def: [['LMT', 'Lockheed Martin', 'lmt.us'], ['RTX', 'RTX (Raytheon)', 'rtx.us'], ['NOC', 'Northrop Grumman', 'noc.us'], ['GD', 'General Dynamics', 'gd.us'],
    ['BA', 'Boeing', 'ba.us'], ['LDO.MI', 'Leonardo', null], ['RHM.DE', 'Rheinmetall', null], ['BA.L', 'BAE Systems', null]]
};
DATA.CRYPTO = [['bitcoin', 'BTC', 'BTCUSDT'], ['ethereum', 'ETH', 'ETHUSDT'], ['solana', 'SOL', 'SOLUSDT'], ['ripple', 'XRP', 'XRPUSDT'], ['binancecoin', 'BNB', 'BNBUSDT'], ['dogecoin', 'DOGE', 'DOGEUSDT']];
DATA.FX = [['EUR', 'EUR/USD', true], ['GBP', 'GBP/USD', true], ['JPY', 'USD/JPY', false], ['CHF', 'USD/CHF', false], ['CNY', 'USD/CNY', false], ['TRY', 'USD/TRY', false], ['ILS', 'USD/ILS', false]];

/* ── EONET categorie ── */
DATA.EONET = {
  wildfires: ['🔥', 'Incendio'], volcanoes: ['🌋', 'Vulcano'], severeStorms: ['🌀', 'Tempesta'], seaLakeIce: ['🧊', 'Ghiaccio'],
  floods: ['🌊', 'Alluvione'], landslides: ['⛰', 'Frana'], drought: ['☀', 'Siccità'], dustHaze: ['🌫', 'Polvere/foschia'],
  snow: ['❄', 'Neve'], tempExtremes: ['🌡', 'Temperature estreme'], earthquakes: ['🌍', 'Terremoto'], manmade: ['⚠', 'Antropico'], waterColor: ['💧', 'Colore acqua']
};
