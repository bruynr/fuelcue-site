# FuelSteps website

Landing page for [FuelSteps](https://fuelsteps.com/), a free Garmin Connect IQ data field for fuel reminders during runs. Static HTML, built and served by GitHub Pages (GitHub Actions).

- Texts: `i18n/<lang>.json` (en, nl, de, fr, es, it); all files have the same keys
- Build: `python build.py` (needs Pillow: `pip install pillow`) → `index.html` (en), `<lang>/index.html`, WebP images and icons in `img/web/`, `manifest.webmanifest`, `404.html`, `sitemap.xml`, `robots.txt`, `llms.txt`, `llms-full.txt`. These are generated and not in git: on every push to `gh-pages`, `.github/workflows/pages.yml` builds and publishes them. Locally, run `build.py` to preview.
- SEO: canonical + hreflang per page, Open Graph, `SoftwareApplication`, `FAQPage` and `WebSite` JSON-LD, sitemap with language alternates, responsive WebP
- Language: the home page sends first-time visitors to their browser language (nl, de, fr, es, it); a choice in the switcher is remembered (localStorage `fuelsteps-lang`) and always wins
- Moving to another domain: change `BASE` in `build.py` and rebuild

If you like FuelSteps: [donate via PayPal](https://paypal.me/rdbruijn)
