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
    { "name": "Research institute", "url": "https://example.org/careers/feed" }
  ]
}
```

Then run:

```sh
python -m pip install -r requirements.txt
python -m stemed_jobs
```

Jobs are written to `output/jobs.json` by default. Override either path with
`--feeds path/to/feeds.json` or `--output path/to/jobs.json`. A failing feed is
reported while the other feeds are still imported; the JSON output is still
written and the command exits nonzero to make scheduled runs detect failures.
Jobs are deduplicated by their posting URL. The normalized JSON fields are
`id`, `title`, `company`, `location`, `url`, `published`, `summary`, `source`,
and `source_url`; feeds that do not provide a field leave it empty.
Each job also has `categories` and `functions` arrays. Categories are
`undergraduates`, `graduates`, `postdocs`, and `faculty`; functions are
`research` and `teaching`. These are evidence-based tags, not exclusions:
unclassified jobs stay in the output with an empty `categories` array, and a
job may have both research and teaching functions. Audience categories are
inferred from the title, while functions are inferred from the title and
description.

Jobs also have a `disciplines` array using the labels on the Seekers Hub
Faculty page: Agriculture, Bioscience, Chemistry, Earth Science, Engineering,
Learning Science, Mathematics, Physics, Science Education, Technology, and
Other. Discipline labels are inferred from titles; a posting
may appear in multiple discipline groups, and unmatched postings go under
Other.

The default run generates `output/index.html` as the Pages site homepage, plus
WordPress-ready HTML snippets for graduates,
postdocs, and faculty in `output/graduates-jobs.html`,
`output/postdocs-jobs.html`, and `output/faculty-jobs.html`. Each includes
discipline buttons linking to section anchors, the filtered jobs, RSS links,
and relevant job-board links from `config/job_boards.json`. The board registry
includes all discussed boards, including those not ingested because they
currently have no verified RSS/API.

The run generates 33 filtered RSS 2.0 feeds (three audiences across 11
disciplines) under `output/feeds/{audience}/{discipline}.xml`; for example,
`output/feeds/graduates/chemistry.xml`. The HTML links default to `/feeds/...`.
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
Any title containing `DBER` is an explicit exception and appears in every
audience/discipline RSS feed. Conventional titles such as condensed-matter
theory remain excluded unless they meet the faculty teaching-title rule.
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
base URL, then deploys the complete `output/` directory to GitHub Pages.

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