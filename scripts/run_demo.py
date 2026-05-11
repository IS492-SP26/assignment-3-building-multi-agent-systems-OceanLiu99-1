"""One-shot end-to-end demo: query -> agents -> synthesis -> judge -> exports.

Usage:
    python scripts/run_demo.py
    python scripts/run_demo.py --query "What is generative engine optimization?"
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import yaml
from dotenv import load_dotenv

from src.autogen_orchestrator import AutoGenOrchestrator
from src.evaluation.judge import LLMJudge
from src.exporters import export_answer_markdown, export_session_json


DEFAULT_QUERY = "What is Generative Engine Optimization (GEO) and how does it differ from SEO?"


async def main(query: str) -> None:
    load_dotenv()
    with open("config.yaml") as f:
        config = yaml.safe_load(f)

    print(f"\n[1/3] Running multi-agent workflow on:\n  {query}\n")
    orchestrator = AutoGenOrchestrator(config)
    result = orchestrator.process_query(query)

    print(f"[1/3] done. Got {len(result.get('conversation_history', []))} messages, response len={len(result.get('response',''))}", flush=True)

    print("[2/3] Judging the response (5 criteria, ~15-25s)...", flush=True)
    judge = LLMJudge(config)
    import time
    j0 = time.time()
    evaluation = await judge.evaluate(
        query=query,
        response=result.get("response", ""),
        sources=result.get("metadata", {}).get("sources", []),
    )
    print(f"[2/3] judging done in {time.time()-j0:.1f}s", flush=True)
    result.setdefault("metadata", {})["evaluation"] = evaluation

    print("[3/3] Exporting artifacts...")
    session_path = export_session_json(result)
    answer_path = export_answer_markdown(result)

    print("\n=== DEMO COMPLETE ===")
    print(f"Session JSON:  {session_path}")
    print(f"Answer (MD):   {answer_path}")
    print(f"Overall score: {evaluation.get('overall_score', 'n/a')}")
    print("\nResponse preview:\n" + (result.get("response", "")[:600] or "(empty)"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", default=DEFAULT_QUERY)
    args = parser.parse_args()
    asyncio.run(main(args.query))
