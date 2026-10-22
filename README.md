<!-- TODO: CHANGE ALL INSTANCES OF "PROJECT-TEMPLATE" IN ENTIRE PROJECT TO YOUR PROJECT TITLE-->

# PROJECT-TEMPLATE

<div align="center">

![GitHub Workflow Status (with event)](https://img.shields.io/github/actions/workflow/status/CogitoNTNU/PROJECT-TEMPLATE/ci.yml)
![GitHub top language](https://img.shields.io/github/languages/top/CogitoNTNU/PROJECT-TEMPLATE)
![GitHub language count](https://img.shields.io/github/languages/count/CogitoNTNU/PROJECT-TEMPLATE)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Project Version](https://img.shields.io/badge/version-0.0.1-blue)](https://img.shields.io/badge/version-0.0.1-blue)

<img src="docs/images/project-logo.png" width="50%" alt="Cogito Project Logo" style="display: block; margin-left: auto; margin-right: auto;">
</div>

<details> 
<summary><b>📋 Table of contents </b></summary>

- [PROJECT-TEMPLATE](#PROJECT-TEMPLATE)
  - [Description](#description)
  - [🛠️ Prerequisites](#%EF%B8%8F-prerequisites)
  - [Getting started](#getting-started)
  - [Usage](#usage)
    - [📖 Generate Documentation Site](#-generate-documentation-site)
  - [Testing](#testing)
  - [Team](#team)
    - [License](#license)

</details>

## Description

<!-- TODO: Provide a brief overview of what this project does and its key features. Please add pictures or videos of the application -->

## 🛠️ Prerequisites

<!-- TODO: In this section you put what is needed for the program to run.
For example: OS version, programs, libraries, etc.  

-->

- **Git**: Ensure that git is installed on your machine. [Download Git](https://git-scm.com/downloads)
- **Python 3.12**: Required for the project. [Download Python](https://www.python.org/downloads/)
- **UV**: Used for managing Python environments. [Install UV](https://docs.astral.sh/uv/getting-started/installation/)
- **Docker** (optional): For DevContainer development. [Download Docker](https://www.docker.com/products/docker-desktop)

## Getting started

<!-- TODO: In this Section you describe how to install this project in its intended environment.(i.e. how to get it to run)  
-->

1. **Clone the repository**:

   ```sh
   git clone https://github.com/CogitoNTNU/PROJECT-TEMPLATE.git
   cd PROJECT-TEMPLATE
   ```

1. **Install dependencies**:

   ```sh
   uv sync
   ```

<!--
1. **Configure environment variables**:
    This project uses environment variables for configuration. Copy the example environment file to create your own:
    ```sh
    cp .env.example .env
    ```
    Then edit the `.env` file to include your specific configuration settings.
-->

1. **Set up pre commit** (only for development):
   ```sh
   uv run pre-commit install
   ```

## Usage

### Economic agent

The economic agent is a LangChain tool with required argument `ticker` and
optional `force_refresh` (default `False`). Register it
in the supervisor's tool list, or call it directly:

```python
from src.economic_agent.main import economic_agent

tools = [economic_agent]  # Pass to the LangChain/LangGraph supervisor.
result = economic_agent.invoke({"ticker": "AAPL"})
```

For a manual run: `uv run python -m src.economic_agent.main AAPL`.
Run `uv sync` to install dependencies. Configure these environment variables
(or put them in `.env`):

```dotenv
MODEL=your-model
IDUN_API_KEY=your-api-key
IDUN_BASE_URL=your-model-endpoint
SEC_USER_AGENT=YourApp your-real-contact-email@example.com
```

Use your own contact email in `SEC_USER_AGENT`; it identifies requests to SEC.
No Tavily API key or PDF tooling is needed by the economic agent.

The tool normalizes tickers (`aapl` → `AAPL`, `BRK-B` → `BRK.B`), checks the
[current S&P 500 constituent table](https://en.wikipedia.org/wiki/List_of_S%26P_500_companies),
and uses its CIK to retrieve filings from the
[SEC submissions API](https://www.sec.gov/search-filings/edgar-application-programming-interfaces).
S&P 500 membership defines the supported US equity universe; this is not an
additional headquarters/incorporation-country filter. The constituent source is
Wikipedia, not a licensed S&P feed, and must be available for each call.

It selects the latest original `10-Q` or `10-K` by reporting period, then filing
date, from SEC's recent filing history. A newer `10-K` covers year-end and is
explicitly labeled annual; amendments (`10-Q/A`, `10-K/A`) are excluded because
they may not contain the full report. The full HTML report is supplied to the
model without truncation, so the configured model needs sufficient context.

The returned dictionary includes `ticker`, `company_name`, `report_url`,
`report_form`, `report_date`, `filing_date`, and the analysis fields (summary,
financial points, positives, risks, score, reasoning). Internal messages and
report text are excluded. Invalid tickers, unavailable sources, missing
configuration and model failures raise errors for the supervisor to handle.
Completed analyses are saved to `data/economic_analysis/<TICKER>.json`, relative
to the project root (not the terminal's working directory). Each call still
checks S&P 500 membership and the latest SEC filing. If the filing metadata and
`analysis_version` match the saved result, it returns that result without
downloading the report or calling the model. New filings, missing/damaged cache
files or a changed analysis version trigger a new analysis.

Results also include `report_id` (SEC accession number), `analyzed_at` (UTC), and
`analysis_version`. Only a complete, successful analysis replaces the old file.
Cache files are ignored by Git. Full report text is not saved. Network failures
during the freshness check raise an error rather than returning an unverified
old result. Amendment handling remains unchanged: only original 10-Q/10-K filings
are selected. Simultaneous calls may duplicate analysis work; writes use separate
temporary files and atomic replacement to avoid partially written JSON.

To force a new analysis:

```python
result = economic_agent.invoke({"ticker": "AAPL", "force_refresh": True})
```

Or run `uv run python -m src.economic_agent.main AAPL --force-refresh`.
Increment `ANALYSIS_VERSION` in `src/economic_agent/cache.py` when changing
analysis prompts or logic so old analyses are regenerated.

Run the offline tests with `uv run pytest tests/test_economic_agent.py -q`.

To run the project, run the following command from the root directory of the project:

```bash

```

<!-- TODO: Instructions on how to run the project and use its features. -->

### 📖 Generate Documentation Site

To build and preview the documentation site locally:

```bash
uv run mkdocs build
uv run mkdocs serve
```

This will build the documentation and start a local server at [http://127.0.0.1:8000/](http://127.0.0.1:8000/) where you can browse the docs and API reference. Get the documentation according to the lastes commit on main by viewing the `gh-pages` branch on GitHub: [https://cogitontnu.github.io/PROJECT-TEMPLATE/](https://cogitontnu.github.io/PROJECT-TEMPLATE/).

## Testing

To run the test suite, run the following command from the root directory of the project:

```bash
uv run pytest --doctest-modules --cov=src --cov-report=html
```

## Team

This project would not have been possible without the hard work and dedication of all of the contributors. Thank you for the time and effort you have put into making this project a reality.

<table align="center">
    <tr>
        <!--
        <td align="center">
            <a href="https://github.com/NAME_OF_MEMBER">
              <img src="https://github.com/NAME_OF_MEMBER.png?size=100" width="100px;" alt="NAME OF MEMBER"/><br />
              <sub><b>NAME OF MEMBER</b></sub>
            </a>
        </td>
        -->
    </tr>
</table>

![Group picture](docs/img/team.png)

### License

______________________________________________________________________

Distributed under the MIT License. See `LICENSE` for more information.
