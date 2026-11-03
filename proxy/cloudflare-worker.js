// Proxy CORS personale per OJO DE DEUS (Cloudflare Workers, piano gratuito).
//
// Perché: molte fonti (RSS, Yahoo Finance, adsb.lol…) non mandano l'header CORS,
// quindi il browser non può leggerle direttamente. OJO prova prima i proxy pubblici,
// che però sono lenti e spesso giù. Con questo Worker tutto diventa affidabile.
//
// Installazione (5 minuti):
//   1. https://dash.cloudflare.com → Workers & Pages → Create → "Hello World" Worker
//   2. Incolla questo file al posto del codice di esempio → Deploy
//   3. In OJO: ⚙ Impostazioni → "Proxy CORS personale" →  https://<nome>.<tuo>.workers.dev/?url={url}
//
// Sicurezza: inoltra SOLO verso gli host usati da OJO (ALLOW), solo GET, senza cookie.

const ALLOW = [
  'api.adsb.lol', 'api.airplanes.live', 'opendata.adsb.fi', 'opensky-network.org', 'api.adsbdb.com', 'api.planespotters.net',
  'celestrak.org', 'api.wheretheiss.at', 'earthquake.usgs.gov', 'eonet.gsfc.nasa.gov', 'firms.modaps.eosdis.nasa.gov',
  'services.swpc.noaa.gov', 'api.rainviewer.com', 'api.gdeltproject.org', 'query1.finance.yahoo.com', 'stooq.com',
  'api.coingecko.com', 'api.binance.com', 'api.frankfurter.dev', 'api.frankfurter.app', 'ipwho.is', 'ipapi.co',
  'feeds.bbci.co.uk', 'www.aljazeera.com', 'www.ansa.it', 'www.rainews.it', 'rss.dw.com', 'www.theguardian.com',
  'www.france24.com', 'rss.nytimes.com', 'feeds.npr.org', 'feeds.skynews.com', 'www.defensenews.com', 'www.timesofisrael.com'
];
const CORS = {
  'access-control-allow-origin': '*',
  'access-control-allow-methods': 'GET, OPTIONS',
  'access-control-allow-headers': 'accept, content-type',
  'access-control-max-age': '86400'
};

export default {
  async fetch(request) {
    if (request.method === 'OPTIONS') return new Response(null, { headers: CORS });
    if (request.method !== 'GET') return new Response('solo GET', { status: 405, headers: CORS });
    const target = new URL(request.url).searchParams.get('url');
    let u;
    try { u = new URL(target); } catch { return new Response('parametro ?url= mancante o non valido', { status: 400, headers: CORS }); }
    if (u.protocol !== 'https:' || !ALLOW.includes(u.hostname)) return new Response('host non consentito: ' + u.hostname, { status: 403, headers: CORS });
    const upstream = await fetch(u.toString(), {
      headers: { 'user-agent': 'Mozilla/5.0 (compatible; OJO-DE-DEUS-proxy/1.0)', accept: request.headers.get('accept') || '*/*' },
      cf: { cacheTtl: 20, cacheEverything: true }
    });
    const headers = new Headers(upstream.headers);
    for (const [k, v] of Object.entries(CORS)) headers.set(k, v);
    headers.delete('set-cookie');
    return new Response(upstream.body, { status: upstream.status, headers });
  }
};
