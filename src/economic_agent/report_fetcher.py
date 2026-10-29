"""Fetch financial reports by S&P 500 ticker directly from SEC EDGAR."""

import os
import re
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

SP500_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"

# Full filings are 100k-400k characters and are re-sent on every LLM call in the
# tool loop, so only the sections the analysis needs are kept, each with a cap.
# Body headings have the title on the same line; table-of-contents entries and
# page headers ("Item 1A") do not, so they are not matched.
ITEM_HEADING = re.compile(r"(?im)^item\s+\d+[a-z]?\.\s*[a-z].*$")
REPORT_SECTIONS = (
    # (title pattern, max characters); core statements come first in their item.
    (re.compile(r"(?i)management.s discussion"), 30_000),
    (re.compile(r"(?i)^item\s+\d+[a-z]?\.\s*financial statements"), 25_000),
    (re.compile(r"(?i)risk factors"), 12_000),
    (re.compile(r"(?i)disclosures about market risk"), 3_000),
)
MAX_REPORT_CHARS = sum(limit for _, limit in REPORT_SECTIONS)


def normalize_ticker(ticker: str) -> str:
    ticker = ticker.strip().upper().replace("-", ".")
    if not re.fullmatch(r"[A-Z]{1,5}(?:\.[A-Z])?", ticker):
        raise ValueError("Provide a ticker such as AAPL or BRK.B, not a company name.")
    return ticker


def get_sp500_company(ticker: str, session: requests.Session) -> dict:
    response = session.get(SP500_URL, timeout=30)
    response.raise_for_status()
    table = BeautifulSoup(response.text, "html.parser").find("table", id="constituents")
    if table is None:
        raise ValueError("Could not read the S&P 500 constituent list.")
    for row in table.select("tr"):
        cells = row.find_all("td")
        if len(cells) >= 7 and cells[0].get_text(strip=True) == ticker:
            return {"cik": int(cells[6].get_text(strip=True))}
    raise ValueError(f"{ticker} is not in the current S&P 500 constituent list.")


def select_latest_report(filings: dict) -> dict:
    """Select by period first; ignore amendments that may lack full financials."""
    reports = []
    for i, form in enumerate(filings.get("form", [])):
        if form not in {"10-Q", "10-K"}:
            continue
        report = {
            key: filings[key][i]
            for key in (
                "form",
                "reportDate",
                "filingDate",
                "accessionNumber",
                "primaryDocument",
            )
        }
        if report["reportDate"] and report["primaryDocument"]:
            reports.append(report)
    if not reports:
        raise ValueError("No original 10-Q or 10-K found in recent SEC filing history.")
    return max(reports, key=lambda r: (r["reportDate"], r["filingDate"]))


def extract_report_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for element in soup.find_all(["script", "style", "ix:header", "ix:hidden"]):
        element.decompose()
    # Keep table cells separated without splitting inline XBRL numbers/signs.
    for cell in soup.select("td, th"):
        cell.append(" | ")
    for block in soup.select("tr, p, div, br"):
        block.append("\n")
    text = "\n".join(
        line.strip() for line in soup.get_text().splitlines() if line.strip()
    )
    if len(text) < 500:
        raise ValueError("Very little text could be extracted from the SEC report.")
    return text


def condense_report_text(text: str) -> str:
    """Keep MD&A, financial statements, risk factors and market risk, each capped."""
    headings = list(ITEM_HEADING.finditer(text))
    sections = []
    for i, heading in enumerate(headings):
        end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
        for pattern, limit in REPORT_SECTIONS:
            if pattern.search(heading.group()):
                section = text[heading.start():end]
                if len(section) > limit:
                    section = section[:limit] + "\n[... section truncated ...]"
                sections.append(section)
                break
    if not sections:
        # Unusual layout: fall back to the start of the filing.
        return text[:MAX_REPORT_CHARS]
    return "\n\n".join(sections)


def sec_session() -> requests.Session:
    """Create an identified SEC client."""
    load_dotenv(dotenv_path=Path(__file__).resolve().parents[2] / ".env")
    user_agent = os.getenv("SEC_USER_AGENT", "").strip()
    if not user_agent:
        raise ValueError(
            "Set SEC_USER_AGENT to your application name and contact email."
        )
    session = requests.Session()
    session.headers.update({"User-Agent": user_agent})
    return session


def get_latest_report(ticker: str) -> dict:
    """Check the latest filing without downloading its document."""
    ticker = normalize_ticker(ticker)
    with sec_session() as session:
        cik = get_sp500_company(ticker, session)["cik"]
        response = session.get(
            f"https://data.sec.gov/submissions/CIK{cik:010d}.json", timeout=30
        )
        response.raise_for_status()
        submissions = response.json()
        report = select_latest_report(submissions["filings"]["recent"])
        accession = report["accessionNumber"].replace("-", "")
        url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{report['primaryDocument']}"
        return {
            "ticker": ticker,
            "report_id": report["accessionNumber"],
            "company_name": submissions["name"],
            "report_url": url,
            "report_form": report["form"],
            "report_date": report["reportDate"],
            "filing_date": report["filingDate"],
        }


def download_report(report: dict) -> dict:
    with sec_session() as session:
        response = session.get(report["report_url"], timeout=60)
        response.raise_for_status()
        text = condense_report_text(extract_report_text(response.text))
        return {**report, "report_text": text}


def fetch_latest_quarterly_report(ticker: str) -> dict:
    """Fetch the newest 10-Q or newer 10-K (year-end), with source metadata."""
    return download_report(get_latest_report(ticker))
