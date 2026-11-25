# Hint: fetch/scrape code

1. Cache everything: `.cache/<sha1(url)>.html` + `.cache/<sha1(url)>.meta` (etag,
   fetched_at). Check cache before network; honor etag with If-None-Match. The test
   suite must run entirely from cache/fixtures — no network in tests, ever.
2. One `requests.Session` per scraper, `timeout=30` on EVERY call (a missing timeout
   is itself a gotcha in our DB), `User-Agent: gotcha-ingest/<version>`.
3. Parse with BeautifulSoup + explicit `html.parser` (no lxml dependency).
   Changelogs in markdown: parse with markdown-it-py token stream, don't regex HTML.
4. Extraction goes wrong quietly: log counts (`found N sections, M candidates,
   K mapped`) so a format change upstream shows as a count drop, not silent zero.
5. Fail soft: network error → use cache + `logging.warning`; parse produces zero
   candidates → raise (that means the format changed and the scraper is broken).
