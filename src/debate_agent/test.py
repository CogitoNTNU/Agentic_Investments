import json
from pathlib import Path

from .graph import graph


# -----------------------------------
# Synthetic company data
# -----------------------------------

analysis_packet = {
    "ticker": "DEMO",
    "company_name": "Demo Technologies",
    "as_of": "2026-10-27",
    "time_horizon": "6-12 months",

    "evidence": [
        {
            "id": "FIN-1",
            "category": "financial",
            "statement": (
                "Revenue increased 18% year over year "
                "in the latest reported quarter."
            ),
            "source": "SYNTHETIC_TEST_DATA",
            "as_of": "2026-10-27",
        },
        {
            "id": "FIN-2",
            "category": "financial",
            "statement": (
                "Free cash flow margin declined "
                "from 16% to 9% year over year."
            ),
            "source": "SYNTHETIC_TEST_DATA",
            "as_of": "2026-10-27",
        },
        {
            "id": "FIN-3",
            "category": "financial",
            "statement": (
                "Net debt increased by 25% "
                "during the last twelve months."
            ),
            "source": "SYNTHETIC_TEST_DATA",
            "as_of": "2026-10-27",
        },
        {
            "id": "VAL-1",
            "category": "valuation",
            "statement": (
                "The company trades at 35 times "
                "forward earnings, compared with "
                "a peer median of 22 times."
            ),
            "source": "SYNTHETIC_TEST_DATA",
            "as_of": "2026-10-27",
        },
        {
            "id": "NEWS-1",
            "category": "news",
            "statement": (
                "The company announced a three-year "
                "enterprise contract with a major customer. "
                "The contract value was not disclosed."
            ),
            "source": "SYNTHETIC_TEST_DATA",
            "as_of": "2026-10-27",
        },
        {
            "id": "RISK-1",
            "category": "business_risk",
            "statement": (
                "The company's three largest customers "
                "represent 45% of total revenue."
            ),
            "source": "SYNTHETIC_TEST_DATA",
            "as_of": "2026-10-27",
        },
        {
            "id": "MACRO-1",
            "category": "economic",
            "statement": (
                "Interest rates are expected to remain "
                "elevated over the analysis horizon, "
                "potentially increasing financing costs."
            ),
            "source": "SYNTHETIC_TEST_DATA",
            "as_of": "2026-10-27",
        },
    ],
}


def main():

    print("\n=== STARTING BULL/BEAR DEBATE ===")

    result = graph.invoke({
        "analysis_packet": analysis_packet
    })

    report = result["debate_report"]

    # -----------------------------------
    # Bull opening
    # -----------------------------------

    print("\n=== BULL ANALYSIS ===")

    bull = report["bull"]["opening"]

    print("Summary:", bull["summary"])

    for argument in bull["arguments"]:
        print(f"\n{argument['argument_id']}")
        print("Claim:", argument["claim"])
        print("Rationale:", argument["rationale"])
        print("Evidence:", argument["evidence_ids"])
        print("Confidence:", argument["confidence"])

    print("\nAcknowledged weaknesses:")
    for weakness in bull["acknowledged_weaknesses"]:
        print("-", weakness)

    # -----------------------------------
    # Bear opening
    # -----------------------------------

    print("\n=== BEAR ANALYSIS ===")

    bear = report["bear"]["opening"]

    print("Summary:", bear["summary"])

    for argument in bear["arguments"]:
        print(f"\n{argument['argument_id']}")
        print("Claim:", argument["claim"])
        print("Rationale:", argument["rationale"])
        print("Evidence:", argument["evidence_ids"])
        print("Confidence:", argument["confidence"])

    print("\nAcknowledged weaknesses:")
    for weakness in bear["acknowledged_weaknesses"]:
        print("-", weakness)

    # -----------------------------------
    # Bull rebuttal
    # -----------------------------------

    print("\n=== BULL REBUTTAL ===")

    bull_reply = report["bull"]["rebuttal"]

    for response in bull_reply["responses"]:
        print(
            "\nResponding to:",
            response["opposing_argument_id"]
        )
        print("Response:", response["response"])
        print("Evidence:", response["evidence_ids"])
        print("Concession:", response["concession"])

    print("\nRevised position:")
    print(bull_reply["revised_position"])

    # -----------------------------------
    # Bear rebuttal
    # -----------------------------------

    print("\n=== BEAR REBUTTAL ===")

    bear_reply = report["bear"]["rebuttal"]

    for response in bear_reply["responses"]:
        print(
            "\nResponding to:",
            response["opposing_argument_id"]
        )
        print("Response:", response["response"])
        print("Evidence:", response["evidence_ids"])
        print("Concession:", response["concession"])

    print("\nRevised position:")
    print(bear_reply["revised_position"])

    # -----------------------------------
    # Unresolved questions
    # -----------------------------------

    print("\n=== UNRESOLVED QUESTIONS ===")

    for question in report["unresolved_questions"]:
        print("-", question)

    # -----------------------------------
    # Save results
    # -----------------------------------

    output_dir = Path("data/debate_agent")
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / "latest_debate.json"

    output_path.write_text(
        json.dumps(
            report,
            indent=2,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )

    print("\n=== DEBATE COMPLETE ===")
    print("Status:", report["status"])
    print("Saved to:", output_path)


if __name__ == "__main__":
    main()