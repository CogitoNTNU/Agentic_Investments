import json
from langchain_core.exceptions import OutputParserException
from pydantic import ValidationError
from ..model import get_model
from .prompts import (
    BEAR_PROMPT,
    BEAR_REBUTTAL_PROMPT,
    BULL_PROMPT,
    BULL_REBUTTAL_PROMPT,
)
from .schemas import AnalysisPacket, Rebuttal, Thesis
from .state import DebateState


def _invoke(schema, system_prompt: str, payload: dict):
    structured_model = get_model().with_structured_output(schema, method="function_calling")
    messages = [
        ("system", system_prompt),
        ("human", json.dumps(payload, ensure_ascii=False)),
    ]
    for attempt in range(3):
        try:
            response = structured_model.invoke(messages)
            return schema.model_validate(response)
        except (ValidationError, OutputParserException) as error:
            if attempt == 2:
                raise
            print(f"Debatt: ugyldig {schema.__name__}-svar, ber om korrigering ({attempt + 1}/2)", flush=True)
            messages.append(("human", (
                f"Your response failed validation: {error}. "
                "Return a complete corrected structured response using the original "
                "evidence. Do not invent missing facts. Required schema: "
                + json.dumps(schema.model_json_schema(), ensure_ascii=False)
            )))


def _valid_ids(packet: dict) -> set[str]:
    return {
        item["id"]
        for item in packet["evidence"]
    }

def _validate_evidence_ids(
    ids: list[str],
    valid_ids: set[str]
) -> None:

    invalid = set(ids) - valid_ids

    if invalid:
        raise ValueError(
            f"Model referenced unknown evidence IDs: {sorted(invalid)}"
        )

def _serialize_thesis(
    thesis: Thesis,
    side: str,
    packet: dict
) -> dict:

    result = thesis.model_dump()
    valid_ids = _valid_ids(packet)

    for i, arg in enumerate(result["arguments"], start=1):

        _validate_evidence_ids(
            arg["evidence_ids"],
            valid_ids
        )

        arg["argument_id"] = f"{side.upper()}-{i}"

    return result


def _serialize_rebuttal(
    rebuttal: Rebuttal,
    opposing_analysis: dict,
    packet: dict
) -> dict:

    result = rebuttal.model_dump()

    allowed_arguments = {
        argument["argument_id"]
        for argument in opposing_analysis["arguments"]
    }

    valid_ids = _valid_ids(packet)

    for response in result["responses"]:

        target = response["opposing_argument_id"]

        if target not in allowed_arguments:
            raise ValueError(
                f"Model referenced unknown opposing argument: {target}"
            )

        _validate_evidence_ids(
            response["evidence_ids"],
            valid_ids
        )

    return result

def _debate_context(state: DebateState) -> dict:
    context = {"analysis_packet": state["analysis_packet"]}
    if "account_snapshot" in state:
        context["account_snapshot"] = state["account_snapshot"]
    return context


def _run_rebuttal(
    state: DebateState,
    system_prompt: str,
    opposing_analysis_key: str,
) -> dict:

    packet = state["analysis_packet"]

    opposing_analysis = state[opposing_analysis_key]

    allowed_ids = [
        argument["argument_id"]
        for argument in opposing_analysis["arguments"]
    ]

    payload = {
        **_debate_context(state),
        "bull_analysis": state["bull_analysis"],
        "bear_analysis": state["bear_analysis"],
        "allowed_opposing_argument_ids": allowed_ids,
    }

    MAX_ATTEMPTS = 2

    for attempt in range(MAX_ATTEMPTS):

        response = _invoke(
            Rebuttal,
            system_prompt,
            payload
        )

        try:
            return _serialize_rebuttal(
                response,
                opposing_analysis,
                packet
            )

        except ValueError as error:

            if attempt == MAX_ATTEMPTS - 1:
                raise

            # Ask the model to correct invalid references
            payload["validation_feedback"] = (
                f"Your previous response was invalid: {error}. "
                f"Generate a corrected rebuttal. "
                f"Valid opposing_argument_ids: {allowed_ids}. "
                "Use ONLY these IDs. "
                "Put your revised thesis in revised_position."
            )


def validate_input(state: DebateState) -> dict:

    packet = AnalysisPacket.model_validate(
        state["analysis_packet"]
    )

    ids = [e.id for e in packet.evidence]

    if len(ids) != len(set(ids)):
        raise ValueError(
            "analysis_packet has duplicate evidence IDs"
        )

    return {
        "analysis_packet": packet.model_dump()
    }


def bull_opening(state: DebateState) -> dict:
    packet = state["analysis_packet"]
    print(f"[{packet['ticker']}] Debatt: bull lager åpningsanalyse", flush=True)

    thesis = _invoke(
        Thesis,
        BULL_PROMPT,
        _debate_context(state)
    )
    return {
        "bull_analysis": _serialize_thesis(
            thesis, "bull", packet
        )
    }


def bear_opening(state: DebateState) -> dict:
    packet = state["analysis_packet"]
    print(f"[{packet['ticker']}] Debatt: bear lager åpningsanalyse", flush=True)
    thesis = _invoke(
        Thesis,
        BEAR_PROMPT,
        _debate_context(state)
    )
    return {
        "bear_analysis": _serialize_thesis(
            thesis, "bear", packet
        )
    }

def bull_rebuttal(state: DebateState) -> dict:
    print(f"[{state['analysis_packet']['ticker']}] Debatt: bull svarer på bears argumenter", flush=True)

    result = _run_rebuttal(
        state=state,
        system_prompt=BULL_REBUTTAL_PROMPT,
        opposing_analysis_key="bear_analysis",
    )

    return {
        "bull_rebuttal": result
    }


def bear_rebuttal(state: DebateState) -> dict:
    print(f"[{state['analysis_packet']['ticker']}] Debatt: bear svarer på bulls argumenter", flush=True)

    result = _run_rebuttal(
        state=state,
        system_prompt=BEAR_REBUTTAL_PROMPT,
        opposing_analysis_key="bull_analysis",
    )

    return {
        "bear_rebuttal": result
    }
