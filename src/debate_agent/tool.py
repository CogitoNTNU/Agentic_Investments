"""Debate tool for a supervisor agent."""

from langchain_core.tools import tool

from src.debate_agent.schemas import AnalysisPacket


@tool
def run_debate(analysis_packet: AnalysisPacket) -> dict:
    """Run a structured bull vs. bear debate on an analysis packet.

    Returns both opening theses, both rebuttals, concessions,
    revised positions and unresolved questions.
    """
    # Registering the tool should not initialize the LLM.
    from src.debate_agent.graph import graph

    result = graph.invoke({"analysis_packet": analysis_packet.model_dump()})
    return result["debate_report"]
