# SignalDesk

SignalDesk is a project I built to monitor regulatory, privacy, AI-policy, and cybersecurity developments across multiple public sources and bring them into one structured workflow.

The idea behind it was simple: instead of checking many different institutional websites manually, I wanted a system that collects relevant updates automatically, normalizes them into a common format, and prepares them for review, filtering, prioritization, and dashboard use.

## Project goal

With SignalDesk, I wanted to build a practical monitoring pipeline for legal, regulatory, and cybersecurity signals.

The project focuses on:
- collecting updates from multiple public sources
- transforming heterogeneous source material into a structured format
- enriching items with summaries, metadata, and prioritization
- preparing the data for downstream processing in tools like Baserow and n8n

For me, this project is mainly a hands-on demonstration of how I approach automation, information pipelines, and structured monitoring workflows.

## What it covers

SignalDesk currently includes sources from different regulatory and cybersecurity domains, including:

- BMJ
- EDPB
- EDPS
- ENISA
- BSI
- BayLDA
- Berlin DPA
- Hessen
- EUR-Lex
- AI Act related sources

This gives the project a mix of EU-level, German federal, and German state-level monitoring sources.

## What the project does

At a high level, the workflow looks like this:

1. Scrape or collect source content from public websites and publication pages
2. Store source-specific outputs in structured files
3. Normalize records into a shared schema
4. Enrich entries with summaries, categories, tags, and relevance metadata
5. Deduplicate and prepare the result for downstream review workflows
6. Use the cleaned data in dashboard or table-based environments

The goal was not just to scrape pages, but to create a workflow that turns raw updates into something that can actually be reviewed and acted on.

## Dashboard screenshot

![n8n workflow](dashboardscreenshot.png)


## Tech stack

This project combines several tools and ideas I wanted to connect in a practical way:

- Python for scraping and processing
- requests / BeautifulSoup / feedparser for source collection
- Playwright for more dynamic or difficult pages
- JSON-based intermediate outputs
- Baserow for structured review tables
- n8n for orchestration and automation workflows
- Docker for local workflow tooling

## Example output structure

The processed data is designed for structured review and includes fields such as:

- title
- source
- category
- language
- date
- url
- summary
- relevance score
- priority
- tags
- processing status
- error message

This makes the output more useful than a simple scrape dump, because it can be filtered, reviewed, and prioritized in a workflow-oriented way.

## Repository structure

A simplified view of the project structure looks like this:

```text
SignalDesk/
├── docker-compose.yml
├── requirements.txt
├── run_scrapers.py
├── dedupe_and_push.py
├── proxy.py
├── output/
├── log/
├── n8n_data/
└── scraper/
    ├── run_scrapers.py
    ├── scraper_baylda.py
    ├── scraper_berlin.py
    ├── scraper_bmj.py
    ├── scraper_bsi_cert.py
    ├── scraper_bsi_consumer.py
    ├── scraper_edpb.py
    ├── scraper_edps.py
    ├── scraper_enisa_news.py
    ├── scraper_enisa_publications.py
    ├── scraper_eurlex.py
    ├── scraper_hessen.py
    ├── output/
    └── log/
```

## n8n workflow

I use n8n as a lightweight orchestration layer for scheduled review and enrichment tasks.

Current workflow:
1. A Schedule Trigger starts the workflow automatically.
2. JavaScript code prepares or reshapes incoming records.
3. A Filter step keeps only relevant items for further processing.
4. Existing table rows are retrieved for lookup or matching.
5. A language model generates or refines text output.
6. The processed result is written back by updating the corresponding row.

This workflow demonstrates how I combine scheduled automation, custom transformation logic, filtering, table operations, and AI-assisted enrichment in one practical pipeline.

## Workflow screenshot

![n8n workflow](n8nworkflow.png)

## How I use it

I mainly use SignalDesk as a monitoring and processing workspace.

Typical usage includes:
- running multiple scrapers
- collecting fresh source updates
- preparing results for review
- pushing cleaned items into a structured table workflow
- experimenting with automation in n8n

## Running the project

Install dependencies:

```bash
pip install -r requirements.txt
```

Run all scrapers:

```bash
python run_scrapers.py all
```

Depending on the local setup, additional processing steps can be run afterwards, for example for deduplication or pushing data into a table-based workflow.

## Why this project matters to me

I built SignalDesk as a practical project to combine topics that interest me most:

- automation
- regulatory monitoring
- cybersecurity
- privacy
- AI governance
- structured data workflows

It reflects how I like to work: taking a messy real-world information problem and building a system that makes it more structured, searchable, and operational.

## What this project demonstrates

From a technical and practical perspective, this project demonstrates:

- multi-source scraping
- handling heterogeneous data inputs
- data normalization
- automation workflow thinking
- integration of collection, processing, and review steps
- building useful internal tooling instead of isolated scripts

For me, SignalDesk is less about a single script and more about designing a complete monitoring workflow.