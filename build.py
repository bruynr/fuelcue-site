"""Builds the site: one page per language from i18n/<lang>.json, plus images (img/web/), icons, manifest, 404,
sitemap.xml, robots.txt, llms.txt, llms-full.txt and the IndexNow key file. `python build.py indexnow` pings IndexNow (after a deploy).

Run: python build.py   (English at the root, the other languages in /<lang>/; needs Pillow)
"""
import json
import html
import re
from datetime import date
from pathlib import Path

BASE = "https://fuelsteps.com/"
DONATE_PAYPAL = "https://paypal.me/rdbruijn"
DONATE_BUNQ = "https://bunq.me/fuelsteps"  # iDEAL/WERO
PLAIN_DONATE = f"{DONATE_PAYPAL} · {DONATE_BUNQ}"  # for plain-text output (JSON-LD, llms.txt)
ORDER = ["en", "nl", "de", "fr", "es", "it"]
ROOT = Path(__file__).parent

T = {code: json.loads((ROOT / "i18n" / f"{code}.json").read_text(encoding="utf-8")) for code in ORDER}

WEB = "img/web/"            # generated from img/ by images()
WIDTHS = [320, 480, 960]    # responsive WebP widths
SHOTS = {"fr970-run": (612, 822), "fr970-alert": (612, 822), "fr970-half": (612, 822), "fr970-quarter": (612, 822),
         "fenix847mm-run": (684, 897), "fenix847mm-almost": (684, 897), "fenix847mm-before": (684, 897)}
LANG_KEY = "fuelsteps-lang"  # localStorage: language picked in the switcher
INDEXNOW_KEY = "1d775e9d727f50ad83cd05991cf82236"  # public by design: served as /<key>.txt (Bing, Yandex, …)

# home page only: on the first visit send the visitor to their browser language; a choice in the switcher wins
REDIRECT = f"""<script>
(function () {{
  try {{
    var langs = {json.dumps(ORDER[1:])}, saved = localStorage.getItem("{LANG_KEY}");
    if (saved) {{ if (langs.indexOf(saved) >= 0) location.replace(saved + "/"); return; }}
    var prefs = navigator.languages || [navigator.language || ""];
    for (var i = 0; i < prefs.length; i++) {{
      var l = String(prefs[i]).slice(0, 2).toLowerCase();
      if (l === "en") return;
      if (langs.indexOf(l) >= 0) {{ location.replace(l + "/"); return; }}
    }}
  }} catch (e) {{}}
}})();
</script>"""

REMEMBER = f"""<script>
document.querySelectorAll("a[hreflang]").forEach(function (a) {{
  a.addEventListener("click", function () {{ try {{ localStorage.setItem("{LANG_KEY}", a.hreflang); }} catch (e) {{}} }});
}});
</script>"""

# donation links open the overlay with both options; without JS the href (bunq on NL, PayPal elsewhere) still works
DONATE_JS = """<script>
(function () {
  var o = document.getElementById("donate");
  document.querySelectorAll("a[data-donate]").forEach(function (a) {
    a.addEventListener("click", function (e) { e.preventDefault(); o.hidden = false; });
  });
  o.addEventListener("click", function (e) { if (e.target === o || e.target.closest(".overlay-close")) o.hidden = true; });
  document.addEventListener("keydown", function (e) { if (e.key === "Escape") o.hidden = true; });
})();
</script>"""

# Cloudflare Web Analytics: no cookies, no personal data, so no consent banner (JS snippet: DNS stays "DNS only")
ANALYTICS = """<script type="module" src="https://static.cloudflareinsights.com/beacon.min.js" data-cf-beacon='{"token": "973a24375d1b4099a8a741239c7c7386"}'></script>"""


def images():
    from PIL import Image
    out = ROOT / WEB
    out.mkdir(parents=True, exist_ok=True)
    for name in SHOTS:
        im = Image.open(ROOT / "img" / f"{name}.png").convert("RGB")
        for w in WIDTHS:
            im.resize((w, round(im.height * w / im.width)), Image.LANCZOS).save(out / f"{name}-{w}.webp", "WEBP", quality=82, method=6)
    icon = Image.open(ROOT / "img" / "icon.png").convert("RGBA")
    for n in [32, 180, 192, 512]:
        icon.resize((n, n), Image.LANCZOS).save(out / f"icon-{n}.png")
    Image.open(ROOT / "img" / "og.png").convert("RGB").resize((1200, 600), Image.LANCZOS).save(out / "og.jpg", quality=86)


def pic(up, name, alt, sizes, lazy=True, cls=""):
    w, h = SHOTS[name]
    srcset = ", ".join(f"{up}{WEB}{name}-{x}.webp {x}w" for x in WIDTHS)
    extra = ' loading="lazy"' if lazy else ' fetchpriority="high"'
    c = f' class="{cls}"' if cls else ""
    return f'<img{c} src="{up}{WEB}{name}-480.webp" srcset="{srcset}" sizes="{sizes}" alt="{esc(alt)}" width="{w}" height="{h}"{extra}>'


def strip(s):
    return re.sub(r"<[^>]+>", "", s.replace("<br>", " "))


def path(code):
    return "" if code == "en" else f"{code}/"


def esc(s):
    return html.escape(s, quote=True)


# "[word]" in a text marks the donation link: an overlay trigger in HTML, the URLs written out in plain text (JSON-LD, llms.txt)
def linked(s, url):
    return re.sub(r"\[(.+?)\]", lambda m: f'<a href="{url}" data-donate>{m.group(1)}</a>', esc(s))


def unlinked(s, urls):
    return re.sub(r"\[(.+?)\]", lambda m: f"{m.group(1)} ({urls})", s)



def page(code):
    t = T[code]
    up = "" if code == "en" else "../"
    url = BASE + path(code)
    donates = [(DONATE_BUNQ, t["donate_bunq"]), (DONATE_PAYPAL, t["donate_paypal"])]
    if code != "nl":
        donates.reverse()  # bunq (iDEAL/WERO) on top only for Dutch visitors
    donate = donates[0][0]  # no-JS fallback for the trigger links
    donate_plain = " · ".join(u for u, _ in donates)
    donate_btns = "".join(f'\n    <a class="btn {cls}" href="{u}">{esc(label)}</a>' for (u, label), cls in zip(donates, ("amber", "dark")))
    alternates = "\n".join(f'<link rel="alternate" hreflang="{c}" href="{BASE + path(c)}">' for c in ORDER)
    langs = " ".join(
        f'<a href="{up}{path(c) or "./"}" hreflang="{c}" lang="{c}"{" aria-current=\"page\"" if c == code else ""}>{T[c]["label"]}</a>'
        for c in ORDER)
    app = {
        "@context": "https://schema.org", "@type": "SoftwareApplication", "name": "FuelSteps",
        "description": t["desc"], "url": url, "inLanguage": code,
        "applicationCategory": "SportsApplication", "applicationSubCategory": "Garmin Connect IQ data field",
        "operatingSystem": "Garmin Connect IQ 5.0+", "isAccessibleForFree": True,
        "offers": {"@type": "Offer", "price": "0", "priceCurrency": "EUR"},
        "image": BASE + WEB + "icon-512.png",
        "screenshot": [BASE + "img/fr970-run.png", BASE + "img/fr970-alert.png", BASE + "img/fenix847mm-before.png"],
    }
    faq = {
        "@context": "https://schema.org", "@type": "FAQPage", "name": f"FuelSteps · {t['faq_kicker']}", "url": url, "inLanguage": code,
        "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": unlinked(a, donate_plain)}} for q, a in t["faq"]],
    }
    site = {"@context": "https://schema.org", "@type": "WebSite", "name": "FuelSteps", "url": BASE,
            "inLanguage": ORDER, "description": T["en"]["desc"]}
    ld = lambda o: json.dumps(o, ensure_ascii=False, indent=1)
    li = lambda items: "".join(f"<li>{i}</li>" for i in items)
    faqs = "\n".join(f"<details><summary>{esc(q)}</summary><p>{linked(a, donate)}</p></details>" for q, a in t["faq"])
    return f"""<!doctype html>
<html lang="{code}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(t["title"])}</title>
<meta name="description" content="{esc(t["desc"])}">
<link rel="canonical" href="{url}">
{alternates}
<link rel="alternate" hreflang="x-default" href="{BASE}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="FuelSteps">
<meta property="og:title" content="{esc(t["og_title"])}">
<meta property="og:description" content="{esc(t["desc"])}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{BASE}{WEB}og.jpg">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="600">
<meta property="og:locale" content="{t["locale"]}">
<meta name="twitter:card" content="summary_large_image">
<meta name="theme-color" content="#15171a">
<link rel="icon" href="{up}{WEB}icon-32.png" sizes="32x32" type="image/png">
<link rel="apple-touch-icon" href="{up}{WEB}icon-180.png">
<link rel="manifest" href="{up}manifest.webmanifest">
{REDIRECT if code == "en" else ""}
<link rel="stylesheet" href="{up}style.css">
<script type="application/ld+json">
{ld(app)}
</script>
<script type="application/ld+json">
{ld(faq)}
</script>
<script type="application/ld+json">
{ld(site)}
</script>
{ANALYTICS}
</head>
<body>

<header><div class="wrap">
  <img src="{up}{WEB}icon-192.png" alt="" width="38" height="38"><b>FuelSteps</b>
  <nav class="langs" aria-label="Language">{langs}</nav>
  <a class="btn ghost" href="{donate}" data-donate>{t["nav_donate"]}</a>
  <span class="btn soon">{t["nav_soon"]}</span>
</div></header>

<main>
<section class="alt"><div class="wrap split">
  <div>
    <div class="kicker">{t["hero_kicker"]}</div>
    <h1>{t["hero_h1"]}</h1>
    <p class="lead">{t["hero_lead"]}</p>
    <div class="ctas">
      <span class="btn soon">{t["hero_soon"]}</span>
      <a class="btn amber" href="{donate}" data-donate>{t["hero_gel"]}</a>
    </div>
  </div>
  {pic(up, "fr970-run", t["alt_hero"], "(max-width: 820px) 90vw, 460px", lazy=False, cls="watch")}
</div></section>

<section><div class="wrap split rev">
  <div>
    <div class="kicker">{t["sched_kicker"]}</div>
    <h2>{t["sched_h2"]}</h2>
    <p class="lead">{t["sched_lead"]}</p>
    <ul class="checks">{li(t["sched_li"])}</ul>
  </div>
  <div class="card">
    <h3>{t["card_title"]}</h3>
    <div class="row"><span class="at">0 km</span><span class="name">Gel</span><span class="g">25 g</span><span class="tag b">{t["tag_before"]}</span></div>
    <div class="row"><span class="at">7 km</span><span class="name">Gel</span><span class="g">25 g</span></div>
    <div class="row"><span class="at">7 km</span><span class="name">Dextro</span><span class="g">15 g</span></div>
    <div class="row"><span class="at">7 km</span><span class="name">Gel CAF</span><span class="g">25 g</span><span class="tag">{t["tag_caf"]}</span></div>
    <div class="row"><span class="at">2× 7 km</span><span class="name">Gel</span><span class="g">25 g</span><span class="tag b">#1 #2</span></div>
  </div>
</div></section>

<section class="alt"><div class="wrap split">
  <div>
    <div class="kicker">{t["alert_kicker"]}</div>
    <h2>{t["alert_h2"]}</h2>
    <p class="lead">{t["alert_lead"]}</p>
  </div>
  {pic(up, "fr970-alert", t["alt_alert"], "(max-width: 820px) 90vw, 460px", cls="watch")}
</div></section>

<section><div class="wrap split rev">
  <div>
    <div class="kicker">{t["glance_kicker"]}</div>
    <h2>{t["glance_h2"]}</h2>
    <p class="lead">{t["glance_lead"]}</p>
  </div>
  <div class="pair">
    {pic(up, "fenix847mm-run", t["alt_run"], "(max-width: 820px) 45vw, 330px")}
    {pic(up, "fenix847mm-almost", t["alt_almost"], "(max-width: 820px) 45vw, 330px")}
  </div>
</div></section>

<section class="alt"><div class="wrap" style="text-align: center;">
  <div class="kicker">{t["layout_kicker"]}</div>
  <h2>{t["layout_h2"]}</h2>
  <p class="lead" style="margin: 18px auto 44px;">{t["layout_lead"]}</p>
  <div class="faces">
    <div class="face"><div>{pic(up, "fr970-run", "", "270px")}</div>{t["full"]}</div>
    <div class="face"><div>{pic(up, "fr970-half", "", "270px")}</div>{t["half"]}</div>
    <div class="face"><div>{pic(up, "fr970-quarter", "", "270px")}</div>{t["quarter"]}</div>
  </div>
</div></section>

<section><div class="wrap split">
  <div>
    <div class="kicker">{t["start_kicker"]}</div>
    <h2>{t["start_h2"]}</h2>
    <ol class="steps">{li(t["steps"])}</ol>
  </div>
  <div>
    <div class="kicker">{t["after_kicker"]}</div>
    <h2>{t["after_h2"]}</h2>
    <ul class="checks">{li(t["after_li"])}</ul>
  </div>
</div></section>

<section class="alt"><div class="wrap">
  <div style="text-align: center;">
    <div class="kicker">{t["faq_kicker"]}</div>
    <h2>{t["faq_h2"]}</h2>
  </div>
  <div class="faq">
{faqs}
  </div>
</div></section>

<section class="donate"><div class="wrap">
  <h2>{t["free_h2"]}</h2>
  <p>{t["free_p"]}</p>
  <a class="btn amber" href="{donate}" data-donate>{t["free_btn"]}</a>
</div></section>
</main>

<div class="stripe"></div>
<footer><div class="wrap">
  <span>FuelSteps · {t["footer_watches"]}</span>
  <nav class="langs-foot" aria-label="Language">{langs}</nav>
  <span>{t["not_affiliated"]}</span>
</div></footer>

<div class="overlay" id="donate" hidden>
  <div class="overlay-box" role="dialog" aria-modal="true" aria-labelledby="donate-title">
    <button class="overlay-close" aria-label="{esc(t["donate_close"])}">✕</button>
    <h3 id="donate-title">{esc(t["donate_title"])}</h3>{donate_btns}
  </div>
</div>

{REMEMBER}
{DONATE_JS}
</body>
</html>
"""


def sitemap():
    today = date.today().isoformat()
    alt = "".join(f'\n    <xhtml:link rel="alternate" hreflang="{c}" href="{BASE + path(c)}"/>' for c in ORDER)
    alt += f'\n    <xhtml:link rel="alternate" hreflang="x-default" href="{BASE}"/>'
    urls = "".join(f"\n  <url>\n    <loc>{BASE + path(c)}</loc>\n    <lastmod>{today}</lastmod>{alt}\n  </url>" for c in ORDER)
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">'
            f"{urls}\n</urlset>\n")


def llms():
    t = T["en"]
    faq = "\n".join(f"### {q}\n{unlinked(a, PLAIN_DONATE)}\n" for q, a in t["faq"])
    pages = "\n".join(f"- [{T[c]['language']}]({BASE + path(c)})" for c in ORDER)
    return f"""# FuelSteps

> {t["desc"]}

- Type: Garmin Connect IQ data field (runs inside the native Run activity)
- Price: free, no subscription, no ads, no account; donations: {PLAIN_DONATE}
- Watches: round Garmin watches with Connect IQ 5.0+ (Forerunner 165–970, fēnix 7/8/9/E, epix Gen 2/Pro, Enduro 3, MARQ Gen 2, Venu 2/3/4, vívoactive 5/6)
- Schedules: up to 5, each a chain of steps by distance (km) or time (min) with repeats; per step a name, grams of carbs and a caffeine mark
- Alert: vibration, tone and full screen, 30 s / 50 m before the planned moment by default
- Data: planned carbs, carbs per hour, fuel and caffeine moments saved in the activity (Garmin Connect charts)
- Languages: English, Dutch, German, French, Spanish, Italian

## Pages
{pages}
- [Full text (English)]({BASE}llms-full.txt)

## FAQ
{faq}"""


def manifest():
    return json.dumps({
        "name": "FuelSteps", "short_name": "FuelSteps", "description": T["en"]["desc"],
        "start_url": "./", "display": "browser", "background_color": "#f6f3ec", "theme_color": "#15171a",
        "icons": [{"src": f"{WEB}icon-{n}.png", "sizes": f"{n}x{n}", "type": "image/png"} for n in (192, 512)],
    }, indent=1) + "\n"


# GitHub Pages serves it for every unknown path, so all links are absolute
def not_found():
    langs = " ".join(f'<a href="{BASE + path(c)}" hreflang="{c}" lang="{c}">{T[c]["language"]}</a>' for c in ORDER)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Page not found · FuelSteps</title>
<meta name="robots" content="noindex">
<link rel="icon" href="{BASE}{WEB}icon-32.png" sizes="32x32" type="image/png">
<link rel="stylesheet" href="{BASE}style.css">
{ANALYTICS}
</head>
<body>
<main><section class="alt" style="min-height: 100vh; display: flex; align-items: center;"><div class="wrap" style="text-align: center;">
  <img src="{BASE}{WEB}icon-192.png" alt="" width="96" height="96">
  <div class="kicker" style="margin-top: 24px;">404</div>
  <h1>Off <em>course.</em></h1>
  <p class="lead" style="margin: 22px auto 30px;">This page doesn't exist. Head back to the start line:</p>
  <p><a class="btn dark" href="{BASE}">FuelSteps</a></p>
  <p style="margin-top: 26px;">{langs}</p>
</div></section></main>
</body>
</html>
"""


# the whole English page as plain markdown, for AI crawlers
def llms_full():
    t = T["en"]
    bullets = lambda items: "\n".join(f"- {strip(i)}" for i in items)
    faq = "\n".join(f"### {q}\n{unlinked(a, PLAIN_DONATE)}\n" for q, a in t["faq"])
    return f"""# FuelSteps: {strip(t["hero_h1"])}

> {t["desc"]}

{strip(t["hero_lead"])}

Website: {BASE} · Donations: {PLAIN_DONATE}

## {strip(t["sched_h2"])}
{strip(t["sched_lead"])}

{bullets(t["sched_li"])}

Example schedule ({t["card_title"]}):
- 0 km: Gel, 25 g ({t["tag_before"]})
- 7 km: Gel, 25 g
- 7 km: Dextro, 15 g
- 7 km: Gel CAF, 25 g, {t["tag_caf"]}
- 2× 7 km: Gel, 25 g (Gel #1, Gel #2)

## {strip(t["alert_h2"])}
{strip(t["alert_lead"])}

## {strip(t["glance_h2"])}
{strip(t["glance_lead"])}

## {strip(t["layout_h2"])}
{strip(t["layout_lead"])} ({t["full"]}, {t["half"]}, {t["quarter"]})

## {strip(t["start_h2"])}
{chr(10).join(f"{i + 1}. {strip(s)}" for i, s in enumerate(t["steps"]))}

## {strip(t["after_h2"])}
{bullets(t["after_li"])}

## FAQ
{faq}
## {strip(t["free_h2"])}
{strip(t["free_p"])} {PLAIN_DONATE}

Watches: {t["footer_watches"]}. {t["not_affiliated"]}

Other languages: {", ".join(f"{T[c]['language']} {BASE + path(c)}" for c in ORDER[1:])}
"""


def main():
    images()
    for code in ORDER:
        out = ROOT / path(code) / "index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(page(code), encoding="utf-8", newline="\n")
    (ROOT / "sitemap.xml").write_text(sitemap(), encoding="utf-8", newline="\n")
    (ROOT / "robots.txt").write_text(f"User-agent: *\nAllow: /\n\nSitemap: {BASE}sitemap.xml\n", encoding="utf-8", newline="\n")
    (ROOT / "llms.txt").write_text(llms(), encoding="utf-8", newline="\n")
    (ROOT / "llms-full.txt").write_text(llms_full(), encoding="utf-8", newline="\n")
    (ROOT / "manifest.webmanifest").write_text(manifest(), encoding="utf-8", newline="\n")
    (ROOT / "404.html").write_text(not_found(), encoding="utf-8", newline="\n")
    (ROOT / f"{INDEXNOW_KEY}.txt").write_text(INDEXNOW_KEY, encoding="utf-8", newline="\n")
    print("built:", ", ".join(ORDER))


def indexnow():
    """After a deploy: tell IndexNow search engines that all language pages changed."""
    import urllib.request
    host = BASE.split("/")[2]
    body = {"host": host, "key": INDEXNOW_KEY, "keyLocation": f"{BASE}{INDEXNOW_KEY}.txt",
            "urlList": [BASE + path(c) for c in ORDER]}
    req = urllib.request.Request("https://api.indexnow.org/indexnow", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json; charset=utf-8"})
    with urllib.request.urlopen(req, timeout=30) as r:
        print("indexnow:", r.status, len(body["urlList"]), "urls")


if __name__ == "__main__":
    import sys
    indexnow() if sys.argv[1:] == ["indexnow"] else main()
