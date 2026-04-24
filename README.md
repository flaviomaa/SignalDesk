# SignalDesk

SignalDesk is a multi-source regulatory, privacy, AI-policy, and cybersecurity monitoring workspace for collecting, normalizing, enriching, and preparing signals from public institutional sources.

The project is designed to track developments across EU law, German legislation, data protection authorities, cybersecurity bodies, and AI regulation sources, then prepare the results for downstream review, prioritization, and dashboard workflows.

## Why this project exists

Regulatory and cybersecurity monitoring is fragmented across many websites, feeds, and publication formats. Important updates are often spread across:

- EU institutions
- German federal and state authorities
- data protection regulators
- cybersecurity agencies
- legal and policy sources
- AI regulation news and implementation material

SignalDesk brings these sources into one workflow so they can be scraped, normalized, deduplicated, summarized, prioritized, and pushed into a structured review environment.

## Features

- Multi-source scraping across regulatory and cybersecurity domains
- Source-specific scrapers for institutional websites and publication pages
- Structured JSON outputs for downstream processing
- Preparation for dashboard and table-based review workflows
- Relevance scoring and prioritization fields
- Source/category/language/date normalization
- Baserow-compatible data handling
- n8n-friendly workflow integration
- Modular structure for adding new scrapers over time

## Covered sources

Current sources visible in the project include:

- BMJ (German legislation)
- EDPB
- EDPS
- ENISA News
- ENISA Publications
- BSI
- BayLDA
- Berlin DPA / LfD Berlin
- Hessen
- EUR-Lex
- AI Act related monitoring sources

The project is built so additional public sources can be added incrementally.

## High-level workflow

SignalDesk follows a pipeline like this:

1. Scrape source content from public websites or feeds
2. Store source-specific outputs as JSON
3. Normalize and clean records into a common structure
4. Enrich entries with summaries, categories, and metadata
5. Deduplicate and prepare records for table/dashboard use
6. Push or review the results in downstream tools such as Baserow and n8n workflows

## Project structure

Example project structure based on the current repository layout:

```text
SignalDesk/
├── docker-compose.yml
├── requirements.txt
├── README.md
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

## Data model

The downstream dashboard-oriented output currently contains fields such as:

- `title`
- `dashboard_title`
- `source`
- `category`
- `language`
- `date`
- `url`
- `summary`
- `relevance_score`
- `priority`
- `tags`
- `status`
- `processed_at`
- `is_new`
- `error_message`

This makes the project suitable not only for scraping, but also for triage, analyst review, and automation workflows.

## Requirements

Recommended environment:

- Python 3.10+
- pip
- virtual environment support
- Docker and Docker Compose (if you want to run n8n locally)
- Internet access for scraping and enrichment steps

Current Python dependencies seen in the project include:

- requests
- beautifulsoup4
- feedparser
- openai
- playwright
- PyMuPDF

Install them with:

```bash
pip install -r requirements.txt
```

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/flaviomaa/SignalDesk.git
cd SignalDesk
```

### 2. Create and activate a virtual environment

Windows:

```bash
python -m venv .venv
.venv\Scripts\activate
```

Linux/macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Install browser dependencies if Playwright is used

```bash
playwright install
```

## Configuration

Some parts of the project may require environment variables, especially for API-based post-processing or table integrations.

Create a `.env` file in the project root if needed.

Example:

```env
BASEROW_BASE_URL=https://api.baserow.io
BASEROW_API_TOKEN=your_token_here
BASEROW_TABLE_ID=your_table_id_here
OPENAI_API_KEY=your_key_here
```

Important notes:

- Keep secrets out of the repository
- Never commit a real `.env`
- Prefer a `.env.example` file for shared documentation

## Usage

### Run all scrapers

```bash
python run_scrapers.py all
```

### Run a specific scraper

Depending on your implementation, individual scrapers can be launched directly, for example:

```bash
python scraper/scraper_edpb.py
python scraper/scraper_bmj.py
python scraper/scraper_enisa_news.py
```

### Run downstream processing

If normalization / deduplication scripts are available in your local version:

```bash
python dedupe_and_push.py
```

Or, in older/local variants of the workflow:

```bash
python normalize_all.py
```

## n8n integration

The repository also includes an n8n-related setup via Docker Compose, which suggests a workflow-oriented use case for automation and review.

Example local start:

```bash
docker compose up -d
```

With n8n, you can orchestrate steps such as:

- scheduled execution
- triggering scrapers
- fetching rows from Baserow
- filtering new items
- sending items to LLM summarization/classification
- updating rows with processed metadata

## Output

Scrapers write source-specific output files, typically as JSON, into dedicated output folders.

Examples seen in the project include files like:

- `bmj_YYYYMMDD.json`
- `edpb_YYYYMMDD.json`
- `enisa_news_YYYYMMDD.json`
- `hessen_YYYYMMDD.json`

The project also contains dashboard-ready exports that combine normalized metadata and review-oriented fields.

## Typical use cases

SignalDesk can be used for:

- regulatory horizon scanning
- privacy and cybersecurity monitoring
- AI Act implementation tracking
- legal and compliance intelligence
- analyst dashboards
- internal news/risk signal pipelines
- research support for governance, compliance, and security teams

## Troubleshooting

### Environment variables are not detected

If a script reports missing variables such as `BASEROW_API_TOKEN` or `BASEROW_TABLE_ID`, make sure:

- the `.env` file is in the correct folder
- the script actually loads the `.env`
- the variable names are spelled exactly right
- the file is really named `.env`, not `.env.txt`

### n8n cannot run local batch files directly

In some n8n setups, local process execution from code nodes is restricted. In that case, use a small local HTTP trigger service as a bridge between n8n and local scripts.

### Scraper breaks after website changes

This project depends on external websites. If selectors, layouts, feeds, or document structures change, individual scrapers may need updates.

## Roadmap

Possible next improvements:

- add `.env.example`
- add per-source documentation
- add test coverage for parsers
- add a unified normalization pipeline
- add schema validation
- add logging conventions
- add retry/error handling per source
- add contributor documentation
- add automated scheduled runs
- add export profiles for dashboard/reporting targets

## Contributing

Contributions, scraper fixes, source additions, and workflow improvements are welcome.

If you want to contribute, a good starting point is:

- improve an existing scraper
- add a new public source
- improve normalization quality
- improve deduplication logic
- improve documentation
- add tests or validation

## License

Add a dedicated `LICENSE` file to define how this project may be used.

If you want this repository to be open source, choose a license such as MIT, Apache-2.0, or GPL-3.0 and add it explicitly.

## Status

This project appears to be an actively evolving workspace rather than a finished product. Expect changes in structure, scripts, and pipeline steps as the monitoring workflow matures.