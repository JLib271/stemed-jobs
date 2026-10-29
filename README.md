# STEMEd Jobs

A small, source-first job aggregator. The first milestone imports RSS feeds,
normalizes their entries, and writes one JSON file. It does not scrape websites
or implement a website, API, or database.

## Project layout

```text
config/feeds.json                 RSS feed configuration
stemed_jobs/feed_sources/         Source configuration and definitions
stemed_jobs/importers/            RSS-to-job normalization
stemed_jobs/storage/              JSON persistence adapter
output/                           Generated files
tests/                            Importer tests
```

## Configure and run

Install the dependency and add the public RSS feed URLs you want to monitor to
`config/feeds.json`:

```json
{
  "feeds": [
    { "name": "University careers", "url": "https://example.org/jobs.rss" },
    { "name": "Research institute", "url": "https://example.org/careers/feed" },
    { "name": "Math board", "url": "https://example.org/math.rss", "disciplines": ["Mathematics"] }
  ]
}
```

The optional `disciplines` list is a fallback for boards devoted to one field;
see the discipline rules below.

Chronicle Careers has one RSS feed per category, and a job appears only in the
categories it is tagged with: `jobsrss/?PositionType=<id>&countrycode=US`. The
IDs in use are Faculty Positions 1, Education 24, Science & Mathematics 71,
Agriculture & Animal Sciences 72, Biology & Life Sciences 73, Chemistry 75,
Engineering 77, Mathematics 79, and Physics & Space Sciences 81 (each category
page links its own "Subscribe to RSS" URL). A STEM education faculty ad is often
tagged only Faculty Positions, so the Education feed alone misses it.

Then run:

```sh
python -m pip install -r requirements.txt
python -m stemed_jobs
```

Jobs are written to `output/jobs.json` by default. Override either path with
`--feeds path/to/feeds.json` or `--output path/to/jobs.json`. A failing feed
(any error, including a timeout or a malformed feed) is skipped and reported
while the other feeds are still imported, and the output is still written. By
default the command then exits nonzero so failures are noticed; with
`--allow-feed-errors` it exits successfully as long as at least one feed was
imported. If every feed fails, nothing is written, so the existing output is
never replaced by an empty one, and the command exits nonzero either way.

Because every run rebuilds the output from scratch, a skipped feed's jobs would
otherwise vanish until it recovers. Pass `--previous` the base URL of the
published site (or a local directory holding the previous `jobs.json` and
`feed_status.json`) and a failed feed keeps the jobs it had in that previous
output, re-sorted with the current rules. They are kept for at most
`--max-stale-days` (default 7) after the feed's last successful fetch, so
postings that expired at the source do not linger. Each run also writes
`output/feed_status.json`, recording every feed's `last_success` time and, for a
failing feed, its `last_error`. For a working feed it also records `items` (how
many postings the feed returned) and the `oldest` and `newest` dates among them,
which shows whether a board only lists its latest postings and so cannot show
older ones; the same summary is printed in the run log. If the previous output
cannot be read (for example on the very first deployment) the failed feed simply
has no fallback.

Advertisements are kept only while they are current. When the posting states an
application deadline (read from phrases like "application deadline is January 8,
2027" or "submit your application by 23 November 2026" in the title, summary and
full text; "review of applications begins..." is not a deadline), it stays until
30 days after that deadline, whenever it was posted (`--deadline-grace-days`
changes the 30). The date is saved as `deadline` in `jobs.json`. A posting that
states no deadline but says when review of applications begins ("review of
applications will begin December 1") is kept until three months after that date
(`--review-months`; saved as `review_date`). A posting with neither falls back to
its posting date: it is kept if posted on or after the most recent May 1 (the academic hiring year start; override with
`--since YYYY-MM-DD`). A posting with neither date is kept. The run log says how
many advertisements were left out and how many of those kept state a deadline.
Deadlines are only found when the feed's text includes them, and many boards
publish short summaries, so expect many ads to use the posting-date fallback.

Many job boards (AAPT, AGU, Chronicle, Science Careers, Physics Today) only list
their newest 20-25 postings, so older but still-open positions fall out of the
feed. To build up a longer history, give a feed `"retain_days": 90` in
`config/feeds.json`. With `--previous` set, each run then keeps any posting it
saw earlier that the board no longer lists, until it is that many days past its
posting date. The daily deployment makes this accumulate over time: the site
reaches back as far as the oldest run, up to `retain_days`. Notes: history
starts from the first run with this setting (older postings the boards already
dropped cannot be recovered); postings with no posting date are not kept; a
closed posting can linger until its window ends; and the run log shows
`plus N kept from earlier runs` per feed. The PER Jobs (Blogger) feed instead
asks for up to 100 entries with `max-results=100`.
Jobs are deduplicated when their posting URLs match (ignoring tracking
parameters and trailing slashes) or when their title and employer both match;
the first feed listed in `config/feeds.json` wins. The normalized JSON fields are
`id`, `title`, `company`, `location`, `url`, `published`, `summary`, `source`,
and `source_url`; feeds that do not provide a field leave it empty.
Each job also has `categories` and `functions` arrays. Categories are
`undergraduates`, `graduates`, `postdocs`, and `faculty`; functions are
`research` and `teaching`. These are evidence-based tags, not exclusions:
unclassified jobs stay in the output with an empty `categories` array, and a
job may have both research and teaching functions. Audience categories are
inferred from the title, while functions are inferred from the title and
description.

Jobs also have a `disciplines` array using ten labels: Agriculture,
Bioscience, Chemistry, Earth Science, Engineering, Health Education, Learning
Science, Mathematics, Physics, and Science Education. Health Education covers
medicine, nursing, pharmacy, dentistry, public health, allied health (physical
and occupational therapy, kinesiology, nutrition and similar), epidemiology and
veterinary medicine (`HEALTH_TERMS`); benefits boilerplate such as "medical,
dental and vision coverage" is ignored. Each label covers its subfields: Earth Science includes geology, geophysics,
hydrology, atmospheric science, oceanography, paleontology, planetary and soil
science and similar; Chemistry includes biochemistry, chemical biology and
geochemistry; Bioscience includes genetics, genomics, animal and plant science,
zoology, botany, entomology, neuroscience, immunology and biochemistry; Physics
includes astronomy, astrophysics, cosmology and space science. The lists are
`EARTH_TERMS`, `CHEMISTRY_TERMS`, `BIOSCIENCE_TERMS` and `PHYSICS_TERMS` in
`stemed_jobs/disciplines.py`, and the same names followed by "education" make a
title relevant. Disciplines are assigned from the
strongest evidence available, and the first step that finds one decides:

1. A discipline named in the title, plus the first hiring department or program
   named in the posting ("Department of Physics", "Computer Engineering
   Department", "Systems Engineering Program"). Later departments are ignored
   because they are usually collaborators.
2. The feed's own `disciplines` default in `config/feeds.json`, for boards
   devoted to one field (for example MathJobs is Mathematics). It is only a
   fallback and never overrides the title or department.
3. The first school, college or institute named ("School of Electrical and
   Computer Engineering"). It ranks below the feed default because a
   college is often only the parent of the real department (a physics
   department in a College of Engineering is not an engineering job).
4. Disciplines the description mentions at least twice and more than half as
   often as the most-mentioned one. A passing mention never counts.

`DBER` titles are the exception: they are cross-listed under every discipline in
the title or description. A posting may appear in multiple discipline groups. A
posting with no discipline evidence gets an empty `disciplines` array and
appears in no discipline list, rather than being guessed into one.

The default run generates `output/index.html` as the Pages site homepage, plus
WordPress-ready HTML snippets for graduates,
postdocs, and faculty in `output/graduates-jobs.html`,
`output/postdocs-jobs.html`, and `output/faculty-jobs.html`. Each includes
discipline buttons linking to section anchors, the filtered jobs, RSS links,
and relevant job-board links from `config/job_boards.json`. The board registry
includes all discussed boards, including those not ingested because they
currently have no verified RSS/API.
HTML job listings use the same relevance and discipline rules as the RSS
feeds. Titles containing `DBER` are included only in the inferred audience
category and the disciplines identified from the title and description.

The run generates 27 filtered RSS 2.0 feeds (three audiences across 9
disciplines) under `output/feeds/{audience}/{discipline}.xml`; for example,
`output/feeds/graduates/chemistry.xml`. A feed with no jobs holds one placeholder item titled "No current postings", so feed readers and WordPress RSS widgets show that instead of an error; it disappears as soon as a job matches. The HTML links default to `/feeds/...`.
RSS research inclusion uses job titles only; descriptions are never used to
qualify a research listing. The discipline-specific title signals include
Physics Education/PER (or a physics topic paired with Education), Chemistry
Education/CER, Earth Science or Geoscience Education/GER/Environmental
Education, and Bioscience or Biology Education/BER (or a biology field paired
with Education). Engineering, Mathematics, Agriculture, Science Education,
and Learning Science have corresponding education-research title signals.
Faculty jobs additionally qualify when their title contains Teaching, SoTL,
or Instructor. This intentionally excludes conventional STEM research roles
even when their descriptions mention education or teaching.
Any title containing `DBER` is an explicit relevance exception. It appears
only in its inferred audience category and only in disciplines found in the
posting title or description.
Conventional titles such as condensed-matter theory remain excluded unless
they meet the faculty teaching-title rule.
Faculty STEM postings also qualify when their description explicitly requires
a PhD/EdD (or doctoral degree) in education, learning sciences, DBER, or SoTL.
This degree-check exception reads descriptions only to verify that requirement;
all other relevance signals remain title-only.
When publishing, host the `output/feeds/` directory at that public URL path, or
set `--feed-base-url` to the URL where you host it. Paste each generated HTML
snippet into a Custom HTML block on its corresponding category page. Buttons
link to local section anchors such as `#discipline-physics`.

Undergraduate jobs intentionally do not get a generated page or RSS feed;
provide those board links separately. This project generates files but does
not publish them to the hosted WordPress site.

Run the tests with:

```sh
python -m unittest discover -s tests
```

## GitHub Actions

The `Regenerate job feeds` workflow runs daily at 06:00 UTC and can also be
started manually from the repository's Actions tab. It installs dependencies,
runs tests, regenerates the JSON/HTML/RSS files using the repository's Pages
base URL, then deploys the complete `output/` directory to GitHub Pages. It runs
the aggregator with `--allow-feed-errors`, so one broken feed does not stop the
deployment, and with `--previous` set to the site's own URL, so a failed feed
keeps its last good jobs for up to a week. Each skipped feed is shown as a
warning annotation on the run page (and in the log as `Feed error:`), so a green
run can still have skipped feeds; check the annotations. If every feed fails the
run fails and nothing is deployed.

To enable deployment, open the repository's **Settings → Pages**, choose
**GitHub Actions** as the build and deployment source, and save. Commit and push
the workflow, then run it from **Actions → Regenerate job feeds → Run workflow**
(or wait for the next scheduled run). After a successful deployment, the run
summary/environment shows the Pages URL. For this repository, the RSS files
will be available at URLs such as
`https://<owner>.github.io/stemed-jobs/feeds/faculty/physics.xml` (unless a
custom domain is configured). The HTML snippets link to the actual Pages base
URL returned by GitHub.
The workflow pins Ubuntu 24.04 to avoid automatic `ubuntu-latest` image
migrations; update that runner version deliberately when you are ready.

Publishing to GitHub Pages makes the generated outputs public, but does not
edit the WordPress pages on Seekers Hub. Paste the generated audience HTML
snippets into their corresponding WordPress category pages separately.

## Architecture direction

Keep external-source details inside importer adapters, normalize everything to
the shared job record, and keep storage/output formats replaceable. This makes
the next steps straightforward without coupling them to ingestion:

- The scheduled GitHub Actions workflow regenerates and publishes the files to
  GitHub Pages.
- A searchable website can read the normalized jobs and add indexing/search
  without knowing each feed's format.
- The generated audience/discipline RSS feeds are output adapters over the
  same normalized records.
- API importers can later produce the same job records as the RSS importer.

For now, the only importer is RSS and the only persistence format is JSON.