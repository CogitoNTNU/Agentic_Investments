"""
US SEC EDGAR Form 4 fetching tool.
Uses official SEC EDGAR submissions JSON endpoint.
"""
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List
import requests


# SEC krever en eksplisitt User-Agent etter formatet: 'AppOrCompany contact@domain.com'
SEC_HEADERS = {
    "User-Agent": "TradingResearchAgent/1.0 (contact@researchlab.io)",
    "Accept-Encoding": "gzip, deflate",
}


def _get_cik_from_ticker(ticker: str) -> str:
    """Henter CIK-nummer for gitt US ticker fra SECs mappingliste."""
    url = "https://www.sec.gov/files/company_tickers.json"
    resp = requests.get(url, headers=SEC_HEADERS, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    
    clean_ticker = ticker.upper().strip()
    for entry in data.values():
        if entry["ticker"] == clean_ticker:
            # CIK må være 10 siffer med ledende nuller for submissions-endepunktet
            return str(entry["cik_str"]).zfill(10)
    raise ValueError(f"Ticker '{ticker}' ble ikke funnet hos SEC.")


def fetch_us_insider_transactions(ticker: str, days: int = 90) -> List[Dict[str, Any]]:
    """
    Henter Form 4-innleveringer fra SEC submissions API.
    Filtrerer på dato og returnerer strukturerte handler.
    """
    cik = _get_cik_from_ticker(ticker)
    url = f"https://data.sec.gov/submissions/CIK{cik}.json"
    
    resp = requests.get(url, headers=SEC_HEADERS, timeout=10)
    resp.raise_for_status()
    sub_data = resp.json()
    
    recent = sub_data.get("filings", {}).get("recent", {})
    if not recent:
        return []
    
    cutoff_date = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    
    forms = recent.get("form", [])
    filing_dates = recent.get("filingDate", [])
    accession_numbers = recent.get("accessionNumber", [])
    primary_docs = recent.get("primaryDocument", [])
    doc_descs = recent.get("primaryDocDescription", [])
    
    trades = []
    
    for i in range(len(forms)):
        if filing_dates[i] < cutoff_date:
            break  # Listene er kronologisk sortert nyeste først
            
        if forms[i] == "4":  # Form 4 = Insider transaction
            accession = accession_numbers[i].replace("-", "")
            doc = primary_docs[i]
            doc_url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession}/{doc}"
            
            trades.append({
                "filing_date": filing_dates[i],
                "insider_name": doc_descs[i] if doc_descs[i] else "Reported Insider",
                "role": "Officer/Director/10% Owner",
                "transaction_type": "buy",  # Standardkategori før detaljparsing
                "shares": 0.0,
                "price_per_share": None,
                "value": None,
                "link": doc_url,
            })
            
    return trades