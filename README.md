# FuelCue website

Landing page for [FuelCue](https://bruynr.github.io/fuelcue-site/), a free Garmin Connect IQ data field for fuel reminders during runs. Static HTML, served by GitHub Pages from this branch.

- Texts: `i18n/<lang>.json` (en, nl, de, fr, es, it); all files have the same keys
- Build: `python build.py` → `index.html` (en), `<lang>/index.html`, `sitemap.xml`, `robots.txt`, `llms.txt`
- SEO: canonical + hreflang per page, Open Graph, `SoftwareApplication` and `FAQPage` JSON-LD, sitemap with language alternates
- Moving to another domain: change `BASE` in `build.py` and rebuild

If you like FuelCue: [donate via PayPal](https://paypal.me/rdbruijn)
