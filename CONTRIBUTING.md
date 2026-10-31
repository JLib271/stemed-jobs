# Contributing

Thank you for helping. This project collects STEM education research and teaching jobs for
graduate students, postdocs and faculty, sorted by discipline.

## The one rule

**Only read existing RSS feeds or APIs. Do not scrape web pages.** A board without a feed can be
added to `config/job_boards.json` (the list of boards readers search themselves), but not to
`config/feeds.json`.

## How changes are made

1. Fork the repository and make your change on a branch.
2. Open a pull request. The Tests check runs automatically.
3. A maintainer reviews it. Nothing goes live until it is merged, and merged changes are published
   at the next daily run (06:00 UTC) or when a maintainer runs the workflow by hand.

Please do not push to `main` directly.

## Easy ways to help

- **Suggest a board or feed**: open an issue with the "Suggest a job board or feed" form.
- **Report a job in the wrong list**: open an issue with the "A job is in the wrong list" form,
  including the job title and the wording in the ad that shows where it belongs.
- **Add a feed**: add an entry to `config/feeds.json`:

  ```json
  {
    "name": "Example Board",
    "url": "https://example.org/jobs/feed/",
    "disciplines": ["Chemistry"],
    "retain_days": 90
  }
  ```

  `disciplines` is optional; use it only for a board devoted to one field. `retain_days` is for
  boards that list only their newest postings: older postings seen in earlier runs are kept for
  that many days. Check the address in a browser first: it should show XML with current items.
- **Add terms for a field**: the word lists are `EARTH_TERMS`, `CHEMISTRY_TERMS`,
  `BIOSCIENCE_TERMS`, `PHYSICS_TERMS` and `HEALTH_TERMS` in `stemed_jobs/disciplines.py`. Add the
  term, and add a test with a real job title to `tests/test_disciplines.py`.

## How jobs are sorted, in brief

- **Audience** (graduate, postdoc, faculty) is read from the job title.
- **Discipline** comes from the strongest evidence: the title, then the hiring department, then the
  board's default, then repeated mentions in the description. See the README for the full order.
- **Relevance**: a job is listed only when it shows education research or teaching, for example
  "chemistry education" in the title or a faculty teaching role.
- **Current ads**: an ad stays until 30 days after a stated application deadline, or 3 months after
  a stated review start date, or (with neither) if posted since the most recent May 1.

## AI assistance

You are welcome to use AI tools. If an AI tool wrote a substantial part of your change, say so in the
pull request description, and review and test everything it produced before you submit it. You remain
responsible for the change, including that any new source is an RSS feed or API and not scraped.

## Running it locally

```
python -m pip install -r requirements.txt
python -m unittest discover -s tests
python -m stemed_jobs --allow-feed-errors
```

The last command reads every feed and writes the site to `output/`.

## Tests

Sorting changes need a test with a real (or realistic) job title, so the same mistake is not
reintroduced later. Tests live in `tests/`.
