import os
import re
import tempfile
from datetime import datetime
from pathlib import Path

import pymupdf4llm
import requests

from dotenv import load_dotenv
from langchain_tavily import TavilySearch

from llm import llm
from schemas import ReportSearchChoice


load_dotenv()


TAVILY_API_KEY = os.getenv(
    "TAVILY_API_KEY"
)

if not TAVILY_API_KEY:
    raise ValueError(
        "TAVILY_API_KEY mangler i .env"
    )


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/140 Safari/537.36"
    )
}


# -------------------------------------------------------------------
# 1. TAVILY SEARCH
# -------------------------------------------------------------------

tavily_search = TavilySearch(
    max_results=10,
    topic="general",
    search_depth="advanced",
    include_answer=False,
    include_raw_content=False,
    api_key=TAVILY_API_KEY,
)


def search_for_company_reports(
    company_name: str,
) -> list[dict]:
    """
    Search the web for the company's most recent quarterly
    financial reports using Tavily.

    Several queries are used so that we are not dependent on
    one specific wording used by the company.
    """

    current_year = datetime.now().year
    previous_year = current_year - 1

    queries = [
        (
            f'"{company_name}" latest quarterly '
            f'report {current_year} PDF'
        ),
        (
            f'"{company_name}" financial statements '
            f'quarterly {current_year} PDF'
        ),
        (
            f'"{company_name}" Q1 {current_year} '
            f'financial report PDF'
        ),
        (
            f'"{company_name}" Q2 {current_year} '
            f'financial report PDF'
        ),
        (
            f'"{company_name}" Q3 {current_year} '
            f'financial report PDF'
        ),
        (
            f'"{company_name}" Q4 {current_year} '
            f'financial report PDF'
        ),
        (
            f'"{company_name}" Q4 {previous_year} '
            f'financial report PDF'
        ),
    ]

    results = []
    seen_urls = set()

    for query in queries:

        print(
            f"Tavily search: {query}"
        )

        response = tavily_search.invoke(
            {
                "query": query
            }
        )

        search_results = response.get(
            "results",
            []
        )

        for result in search_results:

            url = result.get(
                "url"
            )

            if not url:
                continue

            if url in seen_urls:
                continue

            seen_urls.add(
                url
            )

            results.append(
                {
                    "title": result.get(
                        "title",
                        ""
                    ),
                    "url": url,
                    "description": result.get(
                        "content",
                        ""
                    ),
                    "score": result.get(
                        "score",
                        0
                    ),
                }
            )

    if not results:
        raise ValueError(
            f"Tavily could not find any "
            f"report-related results for "
            f"{company_name}."
        )

    return results


# -------------------------------------------------------------------
# 2. DETECT QUARTER AND YEAR
# -------------------------------------------------------------------

def extract_quarter_and_year(
    result: dict,
):
    """
    Extract a quarter and year from the title, URL,
    and Tavily search content.

    Supported examples:

    Q2 2026
    Q2-2026
    Q2_2026
    2026 Q2
    2026-Q2
    """

    text = (
        result.get(
            "title",
            ""
        )
        + " "
        + result.get(
            "url",
            ""
        )
        + " "
        + result.get(
            "description",
            ""
        )
    )

    # Example:
    # Q2 2026
    # Q2-2026
    # Q2_2026

    match = re.search(
        r"\bQ([1-4])[\s\-_]*(20\d{2})\b",
        text,
        re.IGNORECASE,
    )

    if match:

        quarter = int(
            match.group(1)
        )

        year = int(
            match.group(2)
        )

        return year, quarter

    # Example:
    # 2026 Q2
    # 2026-Q2

    match = re.search(
        r"\b(20\d{2})[\s\-_]*Q([1-4])\b",
        text,
        re.IGNORECASE,
    )

    if match:

        year = int(
            match.group(1)
        )

        quarter = int(
            match.group(2)
        )

        return year, quarter

    return None


# -------------------------------------------------------------------
# 3. CHECK WHETHER URL IS A PDF
# -------------------------------------------------------------------

def is_pdf_url(
    url: str,
) -> bool:
    """
    Determine whether a URL points to a PDF.
    """

    if ".pdf" in url.lower():
        return True

    try:

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=20,
            stream=True,
            allow_redirects=True,
        )

        content_type = (
            response.headers.get(
                "Content-Type",
                "",
            ).lower()
        )

        final_url = (
            response.url
        )

        response.close()

        if (
            "application/pdf"
            in content_type
        ):
            return True

        if (
            ".pdf"
            in final_url.lower()
        ):
            return True

        return False

    except requests.RequestException:
        return False


# -------------------------------------------------------------------
# 4. FILTER OUT NON-REPORT DOCUMENTS
# -------------------------------------------------------------------

def looks_like_financial_report(
    result: dict,
) -> bool:
    """
    Remove obvious presentations, press releases,
    transcripts, and unrelated documents.
    """

    text = (
        result.get(
            "title",
            ""
        )
        + " "
        + result.get(
            "url",
            ""
        )
        + " "
        + result.get(
            "description",
            ""
        )
    ).lower()

    unwanted_terms = [
        "presentation",
        "press release",
        "webcast",
        "transcript",
        "earnings call",
    ]

    for term in unwanted_terms:

        if term in text:
            return False

    wanted_terms = [
        "financial statements",
        "quarterly report",
        "interim report",
        "financial report",
        "financial statements and review",
        "quarterly results",
    ]

    return any(
        term in text
        for term in wanted_terms
    )


# -------------------------------------------------------------------
# 5. CHOOSE NEWEST DIRECT PDF
# -------------------------------------------------------------------

def choose_latest_direct_report(
    results: list[dict],
) -> dict | None:
    """
    Choose the newest report deterministically using
    year and quarter.

    The LLM is deliberately NOT used for comparing
    Q1/Q2/Q3/Q4 because normal Python sorting is
    more reliable for that task.
    """

    candidates = []

    for result in results:

        if not looks_like_financial_report(
            result
        ):
            continue

        if not is_pdf_url(
            result["url"]
        ):
            continue

        period = (
            extract_quarter_and_year(
                result
            )
        )

        if period is None:
            continue

        year, quarter = period

        candidates.append(
            {
                "year": year,
                "quarter": quarter,
                "result": result,
            }
        )

    if not candidates:
        return None

    candidates.sort(
        key=lambda candidate: (
            candidate["year"],
            candidate["quarter"],
            candidate["result"].get(
                "score",
                0
            ),
        ),
        reverse=True,
    )

    selected = candidates[0]

    print(
        f"Newest quarterly report found: "
        f"Q{selected['quarter']} "
        f"{selected['year']}"
    )

    print(
        f"Selected report: "
        f"{selected['result']['title']}"
    )

    return selected[
        "result"
    ]


# -------------------------------------------------------------------
# 6. LLM FALLBACK
# -------------------------------------------------------------------

def choose_report_with_llm(
    company_name: str,
    results: list[dict],
) -> dict:
    """
    Fallback when we cannot identify a direct PDF
    deterministically.

    The LLM receives Tavily's search results and chooses
    the result most likely to represent the newest
    quarterly financial report.
    """

    chooser = (
        llm.with_structured_output(
            ReportSearchChoice
        )
    )

    formatted_results = ""

    for index, result in enumerate(
        results
    ):

        formatted_results += f"""
RESULT {index}

Title:
{result["title"]}

URL:
{result["url"]}

Description:
{result["description"]}

Tavily relevance score:
{result["score"]}

"""

    current_year = (
        datetime.now().year
    )

    prompt = f"""
We need the newest already-published quarterly
financial report for:

{company_name}

Current year:
{current_year}

Review the Tavily search results below.

Choose the result corresponding to the newest
actual quarterly or interim financial report.

Strongly prefer:

- official company documents
- financial statements
- quarterly reports
- interim reports
- direct PDF documents

Avoid:

- presentations
- press releases
- transcripts
- webcasts
- news articles
- analyst reports
- future quarters that have not yet been published

IMPORTANT:

Compare the quarter and year carefully.

For example:

Q2 2026 is newer than Q1 2026.
Q1 2026 is newer than Q4 2025.

SEARCH RESULTS:

{formatted_results}
"""

    choice = chooser.invoke(
        prompt
    )

    if (
        choice.result_index
        >= len(results)
    ):
        raise ValueError(
            "The LLM selected an invalid "
            "Tavily result index."
        )

    selected = results[
        choice.result_index
    ]

    print(
        f"LLM fallback selected: "
        f"{selected['title']}"
    )

    return selected


# -------------------------------------------------------------------
# 7. FIND PDF FOR SELECTED REPORT
# -------------------------------------------------------------------

def find_pdf_for_selected_report(
    company_name: str,
    selected_report: dict,
) -> str:
    """
    If the selected Tavily result is already a PDF,
    simply return it.

    Otherwise perform one targeted Tavily search for
    the exact selected report.
    """

    if is_pdf_url(
        selected_report["url"]
    ):
        return selected_report[
            "url"
        ]

    period = extract_quarter_and_year(
        selected_report
    )

    if period:

        year, quarter = period

        query = (
            f'"{company_name}" '
            f'"Q{quarter} {year}" '
            f'"financial statements" PDF'
        )

    else:

        query = (
            f'"{company_name}" '
            f'"{selected_report["title"]}" '
            f'PDF'
        )

    print(
        "Selected Tavily result is not "
        "a direct PDF."
    )

    print(
        f"Searching for exact PDF: "
        f"{query}"
    )

    response = tavily_search.invoke(
        {
            "query": query
        }
    )

    results = response.get(
        "results",
        []
    )

    pdf_results = []

    for result in results:

        candidate = {
            "title": result.get(
                "title",
                ""
            ),
            "url": result.get(
                "url",
                ""
            ),
            "description": result.get(
                "content",
                ""
            ),
            "score": result.get(
                "score",
                0
            ),
        }

        if not candidate["url"]:
            continue

        if not looks_like_financial_report(
            candidate
        ):
            continue

        if not is_pdf_url(
            candidate["url"]
        ):
            continue

        pdf_results.append(
            candidate
        )

    if not pdf_results:
        raise ValueError(
            "Tavily found the report, "
            "but no direct report PDF "
            "could be located."
        )

    # Prefer the most relevant Tavily result.
    pdf_results.sort(
        key=lambda result: result.get(
            "score",
            0
        ),
        reverse=True,
    )

    selected_pdf = (
        pdf_results[0]
    )

    print(
        f"Selected PDF: "
        f"{selected_pdf['title']}"
    )

    return selected_pdf[
        "url"
    ]


# -------------------------------------------------------------------
# 8. DOWNLOAD PDF
# -------------------------------------------------------------------

def download_pdf(
    pdf_url: str,
    output_path: str,
) -> None:
    """
    Download the selected quarterly report.
    """

    response = requests.get(
        pdf_url,
        headers=HEADERS,
        timeout=60,
        allow_redirects=True,
    )

    response.raise_for_status()

    Path(
        output_path
    ).write_bytes(
        response.content
    )


# -------------------------------------------------------------------
# 9. EXTRACT PDF TEXT
# -------------------------------------------------------------------

def extract_pdf_text(
    pdf_url: str,
) -> str:
    """
    Download the PDF temporarily and convert it to
    Markdown using PyMuPDF4LLM.
    """

    with tempfile.NamedTemporaryFile(
        suffix=".pdf",
        delete=False,
    ) as temp_file:

        temp_path = (
            temp_file.name
        )

    try:

        download_pdf(
            pdf_url,
            temp_path,
        )

        report_markdown = (
            pymupdf4llm.to_markdown(
                temp_path
            )
        )

    finally:

        Path(
            temp_path
        ).unlink(
            missing_ok=True
        )

    if len(
        report_markdown.strip()
    ) < 500:

        raise ValueError(
            "Very little text could be "
            "extracted from the report."
        )

    return report_markdown


# -------------------------------------------------------------------
# 10. MAIN REPORT FETCHER
# -------------------------------------------------------------------

def fetch_latest_quarterly_report(
    company_name: str,
) -> dict:
    """
    Find, download, and extract the company's
    latest published quarterly report.

    Pipeline:

    Tavily
        ↓
    Search results
        ↓
    Python selects newest Q/year
        ↓
    LLM fallback if necessary
        ↓
    Direct PDF
        ↓
    PyMuPDF4LLM
        ↓
    LangGraph state
    """

    print(
        f"Searching for latest "
        f"{company_name} quarterly report..."
    )

    # ---------------------------------------------------------------
    # Search with Tavily
    # ---------------------------------------------------------------

    search_results = (
        search_for_company_reports(
            company_name
        )
    )

    print(
        f"Tavily returned "
        f"{len(search_results)} "
        f"unique results."
    )

    # ---------------------------------------------------------------
    # First try deterministic quarter/year selection
    # ---------------------------------------------------------------

    selected_report = (
        choose_latest_direct_report(
            search_results
        )
    )

    # ---------------------------------------------------------------
    # Fall back to the LLM if no clear direct report could be found
    # ---------------------------------------------------------------

    if selected_report is None:

        print(
            "Could not identify the newest "
            "direct PDF deterministically."
        )

        print(
            "Using the LLM as fallback..."
        )

        selected_report = (
            choose_report_with_llm(
                company_name,
                search_results,
            )
        )

    # ---------------------------------------------------------------
    # Resolve selected result into a PDF
    # ---------------------------------------------------------------

    report_url = (
        find_pdf_for_selected_report(
            company_name,
            selected_report,
        )
    )

    print(
        f"Report URL: "
        f"{report_url}"
    )

    # ---------------------------------------------------------------
    # Download and extract report
    # ---------------------------------------------------------------

    print(
        "Downloading and extracting report..."
    )

    report_text = (
        extract_pdf_text(
            report_url
        )
    )

    # ---------------------------------------------------------------
    # Save locally
    # ---------------------------------------------------------------

    output_path = Path(
        "report_text.txt"
    )

    output_path.write_text(
        report_text,
        encoding="utf-8",
    )

    print(
        "Saved extracted report "
        "to report_text.txt"
    )

    # ---------------------------------------------------------------
    # Return to LangGraph State
    # ---------------------------------------------------------------

    return {
        "company_name": company_name,
        "report_url": report_url,
        "report_path": str(
            output_path
        ),
        "report_text": report_text,
    }