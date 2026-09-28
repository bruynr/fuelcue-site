# FuelSteps website

Landing page for [FuelSteps](https://bruynr.github.io/fuelsteps-site/), a free Garmin Connect IQ data field for fuel reminders during runs. Static HTML, built and served by GitHub Pages (GitHub Actions).

- Texts: `i18n/<lang>.json` (en, nl, de, fr, es, it); all files have the same keys
- Build: `python build.py` → `index.html` (en), `<lang>/index.html`, `sitemap.xml`, `robots.txt`, `llms.txt`. These are generated and not in git: on every push to `gh-pages`, `.github/workflows/pages.yml` builds and publishes them. Locally, run `build.py` to preview.
- SEO: canonical + hreflang per page, Open Graph, `SoftwareApplication` and `FAQPage` JSON-LD, sitemap with language alternates
- Moving to another domain: change `BASE` in `build.py` and rebuild

If you like FuelSteps: [donate via PayPal](https://paypal.me/rdbruijn)
