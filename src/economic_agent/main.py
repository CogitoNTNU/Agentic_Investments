from src.economic_agent.graph import graph

def main(): 
    company = input("Which company do you want to analyze?")

    initial_state = {
        "company_query": company, 
        "messages": []
    }

    result = graph.invoke(
        initial_state,
        config = {
            "recursion_limit": 30
        }
    )

    print(
        "\n\n=== FINANCIAL ANALYSIS ===\n"
    )

    print(
        f"Company: "
        f"{result['company_name']}"
    )

    print(
        f"\nReport: "
        f"{result['report_url']}"
    )

    print(
        f"\nSummary:\n"
        f"{result['summary']}"
    )

    print(
        "\nKey financial points:"
    )

    for point in result[
        "key_financial_points"
    ]:
        print(
            f"- {point}"
        )

    print(
        "\nPositive factors:"
    )

    for factor in result[
        "positive_factors"
    ]:
        print(
            f"- {factor}"
        )

    print(
        "\nRisk factors:"
    )

    for risk in result[
        "risk_factors"
    ]:
        print(
            f"- {risk}"
        )

    print(
        f"\nOutlook score: "
        f"{result['outlook_score']}/10"
    )

    print(
        f"\nReasoning:\n"
        f"{result['outlook_reasoning']}"
    )



if __name__ == "__main__":
    main()