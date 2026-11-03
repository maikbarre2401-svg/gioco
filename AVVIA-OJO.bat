<# : ---------------------------------------------------------------
@echo off
rem  OJO DE DEUS - avviatore per Windows (nessuna installazione richiesta)
rem  Mettilo nella STESSA cartella di index.html e fai doppio clic.
rem  Apre http://localhost:8765 con un proxy integrato: video YouTube,
rem  notizie, aerei ADS-B e borse funzionano senza blocchi CORS.
title OJO DE DEUS - server locale
set "OJO_ROOT=%~dp0"
set "OJO_BAT=%~f0"
powershell -NoProfile -ExecutionPolicy Bypass -Command "iex ([IO.File]::ReadAllText($env:OJO_BAT))"
echo.
echo Server fermato. Premi un tasto per chiudere.
pause >nul
exit /b
: ---------------------------------------------------------------- #>

$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath($env:OJO_ROOT)
if (-not [IO.File]::Exists([IO.Path]::Combine($root, 'index.html'))) {
  Write-Host "ERRORE: metti AVVIA-OJO.bat nella stessa cartella di index.html" -ForegroundColor Red
  return
}
try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 -bor [Net.SecurityProtocolType]'Tls13' }
catch { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 }

$listener = $null; $port = 0
foreach ($p in 8765..8780) {
  try { $l = New-Object System.Net.HttpListener; $l.Prefixes.Add("http://localhost:$p/"); $l.Start(); $listener = $l; $port = $p; break } catch { }
}
if (-not $listener) { Write-Host "ERRORE: nessuna porta libera tra 8765 e 8780" -ForegroundColor Red; return }

$allow = @('api.adsb.lol','api.airplanes.live','opendata.adsb.fi','opensky-network.org','api.adsbdb.com','api.planespotters.net',
  'celestrak.org','api.wheretheiss.at','earthquake.usgs.gov','eonet.gsfc.nasa.gov','firms.modaps.eosdis.nasa.gov',
  'services.swpc.noaa.gov','api.rainviewer.com','api.gdeltproject.org','query1.finance.yahoo.com','stooq.com',
  'api.coingecko.com','api.binance.com','api.frankfurter.dev','api.frankfurter.app','ipwho.is','ipapi.co',
  'feeds.bbci.co.uk','www.aljazeera.com','www.ansa.it','www.rainews.it','rss.dw.com','www.theguardian.com',
  'www.france24.com','rss.nytimes.com','feeds.npr.org','feeds.skynews.com','www.defensenews.com','www.timesofisrael.com',
  'noembed.com','www.youtube.com')

$handler = {
  param($ctx, $root, $allow)
  $req = $ctx.Request; $res = $ctx.Response
  function Send($code, $type, [byte[]]$bytes) {
    $res.StatusCode = $code; $res.ContentType = $type; $res.ContentLength64 = $bytes.Length
    $res.OutputStream.Write($bytes, 0, $bytes.Length)
  }
  try {
    $res.AddHeader('Access-Control-Allow-Origin', '*')
    $res.AddHeader('Cache-Control', 'no-store')
    $path = $req.Url.AbsolutePath
    if ($path -eq '/ojo-ping') { Send 200 'application/json' ([Text.Encoding]::UTF8.GetBytes('{"ojo":"local-proxy","v":1}')); return }
    if ($path -eq '/ojo-proxy') {
      $target = $req.QueryString['url']; $u = $null
      if (-not [Uri]::TryCreate($target, [UriKind]::Absolute, [ref]$u) -or $u.Scheme -ne 'https' -or ($allow -notcontains $u.Host)) {
        Send 403 'text/plain; charset=utf-8' ([Text.Encoding]::UTF8.GetBytes('host non consentito')); return
      }
      Add-Type -AssemblyName System.Net.Http
      $hh = New-Object System.Net.Http.HttpClientHandler
      $hh.AutomaticDecompression = [System.Net.DecompressionMethods]::GZip -bor [System.Net.DecompressionMethods]::Deflate
      $c = New-Object System.Net.Http.HttpClient($hh)
      $c.Timeout = [TimeSpan]::FromSeconds(45)
      [void]$c.DefaultRequestHeaders.TryAddWithoutValidation('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36')
      [void]$c.DefaultRequestHeaders.TryAddWithoutValidation('Accept', '*/*')
      try {
        $r = $c.GetAsync($u).GetAwaiter().GetResult()
        $bytes = $r.Content.ReadAsByteArrayAsync().GetAwaiter().GetResult()
        $type = 'application/octet-stream'; if ($r.Content.Headers.ContentType) { $type = $r.Content.Headers.ContentType.ToString() }
        Send ([int]$r.StatusCode) $type $bytes
      } finally { $c.Dispose() }
      return
    }
    $rel = [Uri]::UnescapeDataString($path).TrimStart('/')
    if ($rel -eq '') { $rel = 'index.html' }
    $full = [IO.Path]::GetFullPath([IO.Path]::Combine($root, $rel))
    if (-not $full.StartsWith($root, [StringComparison]::OrdinalIgnoreCase) -or -not [IO.File]::Exists($full)) {
      Send 404 'text/plain' ([Text.Encoding]::UTF8.GetBytes('non trovato')); return
    }
    $types = @{ '.html'='text/html; charset=utf-8'; '.js'='application/javascript; charset=utf-8'; '.mjs'='application/javascript; charset=utf-8'; '.css'='text/css; charset=utf-8';
      '.json'='application/json'; '.png'='image/png'; '.jpg'='image/jpeg'; '.svg'='image/svg+xml'; '.ico'='image/x-icon'; '.webp'='image/webp' }
    $ext = [IO.Path]::GetExtension($full).ToLower(); $type = 'application/octet-stream'; if ($types.ContainsKey($ext)) { $type = $types[$ext] }
    Send 200 $type ([IO.File]::ReadAllBytes($full))
  } catch {
    try { Send 502 'text/plain; charset=utf-8' ([Text.Encoding]::UTF8.GetBytes('errore proxy: ' + $_.Exception.Message)) } catch { }
  } finally { try { $res.Close() } catch { } }
}

$pool = [RunspaceFactory]::CreateRunspacePool(1, 24); $pool.Open()
$jobs = New-Object System.Collections.ArrayList
$url = "http://localhost:$port/"
Write-Host ""
Write-Host "  OJO DE DEUS e' attivo su $url" -ForegroundColor Green
Write-Host "  Proxy integrato: video, notizie, aerei e borse senza blocchi CORS."
Write-Host "  Per fermarlo chiudi questa finestra."
Write-Host ""
try { Start-Process $url } catch { Write-Host "  Apri a mano nel browser: $url" -ForegroundColor Yellow }
while ($listener.IsListening) {
  $ctx = $listener.GetContext()
  $ps = [PowerShell]::Create(); $ps.RunspacePool = $pool
  [void]$ps.AddScript($handler).AddArgument($ctx).AddArgument($root).AddArgument($allow)
  [void]$jobs.Add(@{ ps = $ps; h = $ps.BeginInvoke() })
  for ($i = $jobs.Count - 1; $i -ge 0; $i--) {
    if ($jobs[$i].h.IsCompleted) { try { [void]$jobs[$i].ps.EndInvoke($jobs[$i].h) } catch { }; $jobs[$i].ps.Dispose(); $jobs.RemoveAt($i) }
  }
}
