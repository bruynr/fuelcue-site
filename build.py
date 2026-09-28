"""Builds the site: one page per language from i18n/<lang>.json, plus sitemap.xml, robots.txt and llms.txt.

Run: python build.py   (English at the root, the other languages in /<lang>/)
"""
import json
import html
import re
from datetime import date
from pathlib import Path

BASE = "https://bruynr.github.io/fuelsteps-site/"
DONATE = "https://paypal.me/rdbruijn"
ORDER = ["en", "nl", "de", "fr", "es", "it"]
ROOT = Path(__file__).parent

T = {code: json.loads((ROOT / "i18n" / f"{code}.json").read_text(encoding="utf-8")) for code in ORDER}


def path(code):
    return "" if code == "en" else f"{code}/"


def esc(s):
    return html.escape(s, quote=True)


# "[word]" in a text marks the donation link: a link in HTML, the URL written out in plain text (JSON-LD, llms.txt)
def linked(s):
    return re.sub(r"\[(.+?)\]", lambda m: f'<a href="{DONATE}">{m.group(1)}</a>', esc(s))


def unlinked(s):
    return re.sub(r"\[(.+?)\]", lambda m: f"{m.group(1)} ({DONATE})", s)



def page(code):
    t = T[code]
    up = "" if code == "en" else "../"
    url = BASE + path(code)
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
        "image": BASE + "img/icon.png",
        "screenshot": [BASE + "img/fr970-run.png", BASE + "img/fr970-alert.png", BASE + "img/fenix847mm-before.png"],
        "availableLanguage": [T[c]["language"] for c in ORDER],
    }
    faq = {
        "@context": "https://schema.org", "@type": "FAQPage", "inLanguage": code,
        "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": unlinked(a)}} for q, a in t["faq"]],
    }
    ld = lambda o: json.dumps(o, ensure_ascii=False, indent=1)
    li = lambda items: "".join(f"<li>{i}</li>" for i in items)
    faqs = "\n".join(f"<details><summary>{esc(q)}</summary><p>{linked(a)}</p></details>" for q, a in t["faq"])
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
<meta property="og:image" content="{BASE}img/og.png">
<meta property="og:locale" content="{t["locale"]}">
<meta name="twitter:card" content="summary_large_image">
<meta name="theme-color" content="#15171a">
<link rel="icon" href="{up}img/icon.png">
<link rel="stylesheet" href="{up}style.css">
<script type="application/ld+json">
{ld(app)}
</script>
<script type="application/ld+json">
{ld(faq)}
</script>
</head>
<body>

<header><div class="wrap">
  <img src="{up}img/icon.png" alt=""><b>FuelSteps</b>
  <nav class="langs" aria-label="Language">{langs}</nav>
  <a class="btn ghost" href="{DONATE}">{t["nav_donate"]}</a>
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
      <a class="btn amber" href="{DONATE}">{t["hero_gel"]}</a>
    </div>
  </div>
  <img class="watch" src="{up}img/fr970-run.png" alt="{esc(t["alt_hero"])}" width="612" height="822">
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
  <img class="watch" src="{up}img/fr970-alert.png" alt="{esc(t["alt_alert"])}" width="612" height="822" loading="lazy">
</div></section>

<section><div class="wrap split rev">
  <div>
    <div class="kicker">{t["glance_kicker"]}</div>
    <h2>{t["glance_h2"]}</h2>
    <p class="lead">{t["glance_lead"]}</p>
  </div>
  <div class="pair">
    <img src="{up}img/fenix847mm-run.png" alt="{esc(t["alt_run"])}" width="684" height="897" loading="lazy">
    <img src="{up}img/fenix847mm-almost.png" alt="{esc(t["alt_almost"])}" width="684" height="897" loading="lazy">
  </div>
</div></section>

<section class="alt"><div class="wrap" style="text-align: center;">
  <div class="kicker">{t["layout_kicker"]}</div>
  <h2>{t["layout_h2"]}</h2>
  <p class="lead" style="margin: 18px auto 44px;">{t["layout_lead"]}</p>
  <div class="faces">
    <div class="face"><div><img src="{up}img/fr970-run.png" alt="" loading="lazy"></div>{t["full"]}</div>
    <div class="face"><div><img src="{up}img/fr970-half.png" alt="" loading="lazy"></div>{t["half"]}</div>
    <div class="face"><div><img src="{up}img/fr970-quarter.png" alt="" loading="lazy"></div>{t["quarter"]}</div>
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
  <a class="btn amber" href="{DONATE}">{t["free_btn"]}</a>
</div></section>
</main>

<div class="stripe"></div>
<footer><div class="wrap">
  <span>FuelSteps · {t["footer_watches"]}</span>
  <nav class="langs-foot" aria-label="Language">{langs}</nav>
  <span>{t["not_affiliated"]}</span>
</div></footer>

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
    faq = "\n".join(f"### {q}\n{unlinked(a)}\n" for q, a in t["faq"])
    pages = "\n".join(f"- [{T[c]['language']}]({BASE + path(c)})" for c in ORDER)
    return f"""# FuelSteps

> {t["desc"]}

- Type: Garmin Connect IQ data field (runs inside the native Run activity)
- Price: free, no subscription, no ads, no account; donations: {DONATE}
- Watches: round Garmin watches with Connect IQ 5.0+ (Forerunner 165–970, fēnix 7/8/9/E, epix Gen 2/Pro, Enduro 3, MARQ Gen 2, Venu 2/3/4, vívoactive 5/6)
- Schedules: up to 5, each a chain of steps by distance (km) or time (min) with repeats; per step a name, grams of carbs and a caffeine mark
- Alert: vibration, tone and full screen, 30 s / 50 m before the planned moment by default
- Data: planned carbs, carbs per hour, fuel and caffeine moments saved in the activity (Garmin Connect charts)
- Languages: English, Dutch, German, French, Spanish, Italian

## Pages
{pages}

## FAQ
{faq}"""


def main():
    for code in ORDER:
        out = ROOT / path(code) / "index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(page(code), encoding="utf-8", newline="\n")
    (ROOT / "sitemap.xml").write_text(sitemap(), encoding="utf-8", newline="\n")
    (ROOT / "robots.txt").write_text(f"User-agent: *\nAllow: /\n\nSitemap: {BASE}sitemap.xml\n", encoding="utf-8", newline="\n")
    (ROOT / "llms.txt").write_text(llms(), encoding="utf-8", newline="\n")
    print("built:", ", ".join(ORDER))


if __name__ == "__main__":
    main()
