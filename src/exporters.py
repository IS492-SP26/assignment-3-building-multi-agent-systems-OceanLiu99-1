"""Helpers for exporting session transcripts and synthesized answers."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def export_session_json(result: Dict[str, Any], output_dir: str = "outputs/sessions") -> str:
    """Save a full session (query, transcript, metadata) as JSON."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"session_{_timestamp()}.json"
    with open(path, "w") as f:
        json.dump(result, f, indent=2, default=str)
    return str(path)


def export_answer_markdown(
    result: Dict[str, Any],
    sources: Optional[List[Dict[str, Any]]] = None,
    output_dir: str = "outputs/artifacts",
) -> str:
    """Save the final synthesized answer as a Markdown artifact."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"answer_{_timestamp()}.md"

    query = result.get("query", "")
    response = result.get("response", "")
    metadata = result.get("metadata", {}) or {}
    sources = sources or metadata.get("sources") or []

    lines = [f"# Research Answer\n", f"**Query:** {query}\n", "## Response\n", response, "\n## Sources\n"]
    if sources:
        for i, s in enumerate(sources, 1):
            if isinstance(s, dict):
                title = s.get("title", "Untitled")
                url = s.get("url", "")
                lines.append(f"{i}. {title} — {url}")
            else:
                lines.append(f"{i}. {s}")
    else:
        lines.append("_No structured sources captured (see transcript for inline references)._")

    with open(path, "w") as f:
        f.write("\n".join(lines))
    return str(path)


def export_safety_events(events: List[Dict[str, Any]], output_dir: str = "outputs/safety") -> str:
    """Save a list of safety events for one session."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"safety_{_timestamp()}.json"
    with open(path, "w") as f:
        json.dump(events, f, indent=2, default=str)
    return str(path)
