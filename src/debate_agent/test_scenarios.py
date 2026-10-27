import json
import sys
from copy import deepcopy
from pathlib import Path

from .graph import graph
from .test import analysis_packet


SCENARIOS = {
    "positive": {
        "FIN-1": (
            "Revenue grew 24% year over year in the latest quarter, "
            "following 20% growth in the previous quarter."
        ),
        "FIN-2": (
            "Free cash flow margin increased from 12% to 18% "
            "year over year."
        ),
        "FIN-3": (
            "Net debt decreased by 30% during the last "
            "twelve months."
        ),
        "VAL-1": (
            "The company trades at 26 times forward earnings, "
            "compared with a peer median of 22 times."
        ),
        "NEWS-1": (
            "The company signed a three-year enterprise contract "
            "with minimum annual commitments equivalent to 8% "
            "of prior-year annual revenue."
        ),
        "RISK-1": (
            "The company's three largest customers account "
            "for 42% of total revenue."
        ),
        "MACRO-1": (
            "Interest rates are expected to remain elevated "
            "over the analysis horizon."
        ),
    },

    "negative": {
        "FIN-1": (
            "Revenue declined 8% year over year in the latest "
            "quarter, following a 3% decline in the previous quarter."
        ),
        "FIN-2": (
            "Free cash flow margin decreased from 12% to 4% "
            "year over year."
        ),
        "FIN-3": (
            "Net debt increased by 40% during the last "
            "twelve months."
        ),
        "VAL-1": (
            "The company trades at 32 times forward earnings, "
            "compared with a peer median of 22 times."
        ),
        "NEWS-1": (
            "The company announced a three-year enterprise "
            "contract with a major customer. "
            "The contract value was not disclosed."
        ),
        "RISK-1": (
            "The company's three largest customers account "
            "for 55% of total revenue."
        ),
        "MACRO-1": (
            "Interest rates are expected to remain elevated "
            "over the analysis horizon, potentially increasing "
            "financing costs."
        ),
    },
}


def build_packet(scenario: str) -> dict:

    if scenario not in SCENARIOS:
        raise ValueError(
            f"Unknown scenario: {scenario}. "
            f"Choose from {list(SCENARIOS)}"
        )

    packet = deepcopy(analysis_packet)

    packet["ticker"] = (
        "DEMO_POS" if scenario == "positive" else "DEMO_NEG"
    )

    packet["company_name"] = (
        f"Demo Technologies - {scenario.title()} Scenario"
    )

    for evidence in packet["evidence"]:
        evidence["statement"] = SCENARIOS[scenario][
            evidence["id"]
        ]

    return packet


def main():

    scenario = (
        sys.argv[1] if len(sys.argv) > 1 else "positive"
    )

    packet = build_packet(scenario)

    print(f"\n=== TEST SCENARIO: {scenario.upper()} ===")

    result = graph.invoke({
        "analysis_packet": packet
    })

    report = result["debate_report"]

    for side in ("bull", "bear"):

        opening = report[side]["opening"]
        rebuttal = report[side]["rebuttal"]

        print(f"\n=== {side.upper()} ANALYSIS ===")
        print("Summary:", opening["summary"])

        for argument in opening["arguments"]:
            print(
                f"{argument['argument_id']}: "
                f"{argument['claim']}"
            )
            print("Evidence:", argument["evidence_ids"])
            print("Confidence:", argument["confidence"])

        print(f"\n=== {side.upper()} REBUTTAL ===")

        for response in rebuttal["responses"]:
            print(
                "Responding to:",
                response["opposing_argument_id"]
            )
            print("Concession:", response["concession"])

        print("\nRevised position:")
        print(rebuttal["revised_position"])

    print("\n=== UNRESOLVED QUESTIONS ===")

    for question in report["unresolved_questions"]:
        print("-", question)

    # Save report
    output_dir = Path("data/debate_agent")
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / (
        f"debate_{scenario}.json"
    )

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