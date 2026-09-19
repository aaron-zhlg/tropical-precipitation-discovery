"""Run the tropical-precipitation multi-agent system.

    uv run python -m agents.run
    uv run python -m agents.run "Test H1 on CanESM5 and ACCESS-CM2 only"
    uv run python -m agents.run --fingerprint
"""

from __future__ import annotations

import argparse
import json
import sys

from agents.env import load_dotenv
from agents.lead import DEFAULT_GOAL, build


def _llm_configured() -> bool:
    import os

    return bool(
        os.environ.get("DEEPSEEK_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
        or (os.environ.get("ORCHESTRA_API_KEY") and os.environ.get("ORCHESTRA_BASE_URL") and os.environ.get("ORCHESTRA_MODEL"))
    )


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description="H1 multi-agent tropical precipitation tests.")
    parser.add_argument("goal", nargs="*", help="Research goal; default tests H1 on local data.")
    parser.add_argument("--fingerprint", action="store_true", help="Compute observational indices only (no LLM).")
    parser.add_argument("--catalog", action="store_true", help="Print dataset catalog (no LLM).")
    parser.add_argument("--h1-row", default="", help="Compute one CMIP6 model H1 row (no LLM).")
    parser.add_argument("--test-h1", action="store_true", help="Score cached H1 rows (no LLM).")
    parser.add_argument("--lead-model", default=None)
    parser.add_argument("--max-rounds", type=int, default=2)
    parser.add_argument("--log-dir", default="logs")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--no-citations", action="store_true")
    args = parser.parse_args(argv)

    if args.catalog or args.fingerprint or args.h1_row or args.test_h1:
        from agents import diagnostics as diag

        if args.catalog:
            print(json.dumps(diag.catalog(), indent=2, default=str))
        if args.fingerprint:
            print(json.dumps(diag.observational_fingerprint(), indent=2, default=str))
        if args.h1_row:
            print(json.dumps(diag.model_h1_row(args.h1_row), indent=2, default=str))
        if args.test_h1:
            print(json.dumps(diag.test_h1(), indent=2, default=str))
        return 0

    from orchestra import LLMError

    if not _llm_configured():
        print(
            "error: no LLM key. Set DEEPSEEK_API_KEY or OPENAI_API_KEY "
            "(or ORCHESTRA_API_KEY + ORCHESTRA_BASE_URL + ORCHESTRA_MODEL).\n"
            "Diagnostics without an LLM: python -m agents.run --catalog|--fingerprint|--h1-row MODEL|--test-h1",
            file=sys.stderr,
        )
        return 1

    goal = " ".join(args.goal) if args.goal else DEFAULT_GOAL
    try:
        report = build(
            lead_model=args.lead_model,
            max_rounds=args.max_rounds,
            add_citations=not args.no_citations,
            verbose=not args.quiet,
            log_dir=args.log_dir,
        ).run(goal)
    except LLMError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print("\n" + "=" * 80)
    print(report.answer)
    print("=" * 80)
    print(f"[complexity={report.complexity}, rounds={report.rounds}, sources={len(report.sources)}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
