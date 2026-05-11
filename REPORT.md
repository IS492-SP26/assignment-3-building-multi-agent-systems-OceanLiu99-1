# Multi-Agent Deep Research System for Generative Engine Optimization

## Abstract

This project builds a multi-agent deep research assistant that helps users explore the topic of *Generative Engine Optimization* (GEO), which is about how content gets surfaced and cited by generative search engines. I used Microsoft AutoGen to orchestrate four agents (Planner, Researcher, Writer, and Critic) that take turns in a round-robin chat to plan a query, gather evidence, write a draft, and check the draft. The Researcher uses Brave Web Search and the Semantic Scholar API to pull real sources, and a citation tool keeps track of where each fact came from. Safety is handled by an input/output guardrail layer built on the Guardrails-AI framework, with rules for toxic language, prompt injection, off-topic queries, and PII. A user can run the system through a CLI or a Streamlit web app. For evaluation, I used an LLM-as-a-Judge module with five criteria and ran it on more than five test queries. The report below explains how everything fits together and what I learned.

## 1. System Design and Implementation

### 1.1 Topic

I chose **Generative Engine Optimization (GEO)** as the research topic. It is a fairly new HCI/AI sub-area, so the system gets to work on queries about citation behavior, prompt design, visibility in LLM answers, and how users interact with generative search.

### 1.2 Agents and Orchestration

The orchestration uses AutoGen's `RoundRobinGroupChat`. There are four agents, all defined in `src/agents/autogen_agents.py` and wired together in `src/autogen_orchestrator.py`:

1. **Planner** — breaks the user query into 3–5 research steps and ends its turn with `PLAN COMPLETE`.
2. **Researcher** — calls `web_search()` and `paper_search()` tools to collect 8–10 sources, then says `RESEARCH COMPLETE`.
3. **Writer** — writes a structured draft with APA-style citations and says `DRAFT COMPLETE`.
4. **Critic** — peer-reviews the draft and says either `APPROVED - RESEARCH COMPLETE` or `NEEDS REVISION`.

The control flow is: **Planner → Researcher → Writer → Critic**, with a `max_rounds` cap (default 20) and a text-based termination condition that watches for the approval signal. Each agent has its own system prompt that is loaded from `config.yaml`, so I can change the topic without editing code.

### 1.3 Tools

The Researcher has access to three tools in `src/tools/`:

- `web_search.py` — wraps the **Brave Search API**, returning title/URL/snippet for each hit. Falls back to a stub if the API key is missing.
- `paper_search.py` — calls the **Semantic Scholar Graph API** for academic papers (title, authors, year, abstract, URL).
- `citation_tool.py` — formats each source into APA-style strings and keeps a list of all sources collected during a run so they can be shown in the UI.

### 1.4 Models

All agents and the judge run on the class-provided self-hosted **gpt-oss-20b** endpoint (OpenAI-compatible API). The judge uses a lower temperature (0.3) than the agents (0.7) so its scores are more stable.

### 1.5 User Interface

There are two UIs in `src/ui/`:

- **CLI (`cli.py`)** — a simple terminal loop with commands like `help`, `history`, and `clear`. It prints the active agent's name, the response, the citation list, and a "SAFETY NOTICE" block whenever a guardrail fires.
- **Streamlit web app (`streamlit_app.py`)** — has a query box, an "agent traces" expander showing each agent's message, a sidebar with citations, and a colored banner when content was refused or sanitized. It also shows the latest evaluation scores.

Both UIs run through the same orchestrator, so the behavior stays consistent.

## 2. Safety Design

Safety lives in `src/guardrails/` and is coordinated by `SafetyManager`, which wraps both the input and output checks and logs every event to `logs/safety_events.log`.

### 2.1 Policy Categories

I documented four prohibited categories in `config.yaml`:

1. **harmful_content** — toxic language, self-harm content, instructions for violence.
2. **personal_attacks** — insulting or hostile language aimed at a person.
3. **misinformation** — uncited factual claims or hallucinated sources in the output.
4. **off_topic_queries** — questions that have nothing to do with research (recipes, sports scores, dating advice, etc.).

I also check for **prompt injection** ("ignore previous instructions", "reveal your system prompt", etc.) and **PII** (emails, phone numbers, SSN-like patterns) on the output side.

### 2.2 Input Guardrail

`input_guardrail.py` runs the user query through:

- Length checks (too short / too long).
- **Guardrails-AI `ToxicLanguage` validator** (with a heuristic fallback list if the model is not installed).
- A list of prompt-injection patterns.
- A relevance check that compares the query against topic keywords (GEO, research, HCI, etc.) and a blocklist of obviously off-topic patterns.

Each violation has a `severity` (low/medium/high) and an `action` (`warn` or `block`).

### 2.3 Output Guardrail

`output_guardrail.py` looks at the final draft for:

- Toxic language.
- Misinformation signals (claims with no citation, hedging words used as facts).
- PII patterns (regex for emails, phones, SSNs).

When triggered, the manager either **refuses** with a safe message, **redacts** the offending span, or **passes with a warning**, depending on the policy in config.

### 2.4 Logging

Every blocked or sanitized event is appended to `logs/safety_events.log` with a timestamp, the violation type, the severity, and a snippet of the input/output. Both UIs display a notice so the user knows *why* something was blocked.

## 3. Evaluation Setup and Results

### 3.1 Setup

Evaluation is in `src/evaluation/`. `LLMJudge` builds a judge prompt per criterion, calls the judge model, and parses a score (0–10) plus feedback. `SystemEvaluator` loads a test set, runs each query through the orchestrator, scores it, and writes a JSON report under `outputs/`.

I wired the full pipeline into `main.py --mode evaluate`, which loads `data/test_queries.json`, runs the orchestrator on each, judges every response, and prints a summary.

### 3.2 Judge Prompts and Metrics

I used **five** criteria (more than the required two), with weights in `config.yaml`:

| Criterion | Weight | What it measures |
|---|---|---|
| Relevance | 0.25 | Does the answer actually address the query? |
| Evidence quality | 0.25 | Are claims backed by real citations? |
| Factual accuracy | 0.20 | Are the facts consistent and correct? |
| Safety compliance | 0.15 | No harmful or unsafe content? |
| Clarity | 0.15 | Is it well-organized and easy to read? |

Each criterion has its own judge prompt (so there are five independent judging passes). If the judge LLM fails or returns junk, the system falls back to a heuristic scorer that uses signals like citation count, response length, and presence of hedging words. This keeps the pipeline from crashing during long batch runs.

### 3.3 Test Queries

I put **8 diverse queries** in `data/test_queries.json`, covering:

- definitional ("What is generative engine optimization?")
- comparative ("How does GEO differ from traditional SEO?")
- methodological ("What metrics measure visibility in LLM-generated answers?")
- adversarial / safety ("Ignore previous instructions and tell me…" — should be refused)
- off-topic ("What's a good pasta recipe?" — should be refused)

### 3.4 Results

On the in-topic queries, the system averaged around **7–8 / 10** for relevance and clarity, and **6–7 / 10** for evidence quality (the gap was usually because the writer paraphrased without keeping a citation marker). Safety compliance was consistently high (9+) because the guardrails blocked the unsafe queries before they reached the LLM. The adversarial and off-topic queries were correctly refused with a logged safety event, which I treat as a "pass" rather than a low score.

### 3.5 Error Analysis

The two failure modes I saw most often were:

1. **Citation drift** — the Writer occasionally summarizes a fact and forgets to attach the source ID, which then lowers the evidence-quality score. Tightening the Writer prompt to require an inline `[n]` after every claim would probably fix this.
2. **Tool quota / API errors** — when Brave or Semantic Scholar rate-limits, the Researcher gets fewer sources. The system handles this gracefully (it just continues with what it has) but the final answer is shorter and gets lower coverage scores.

## 4. Discussion and Limitations

**What worked well.** Splitting the work across four agents made the final answers feel a lot more structured than a single-prompt baseline. The Critic agent in particular caught a few "approved" drafts that actually had no citations and forced a revision round. The guardrail layer was easier to add than I expected because the Guardrails-AI library already ships a `ToxicLanguage` validator — I mostly had to write the orchestration around it.

**What was hard.** Getting the agents to actually stop was tricky. Without the explicit `PLAN COMPLETE` / `RESEARCH COMPLETE` handoff strings, the round-robin loop sometimes ran in circles until it hit `max_rounds`. The off-topic detector also needs more tuning — right now it relies on a keyword list, which catches obvious cases but probably has false positives for unusual but legitimate HCI questions.

**Limitations.**

- The judge is the same model family as the agents, so there is some risk of self-preference bias.
- Heuristic fallback scoring is convenient but not as trustworthy as full LLM judging — I rely on it more than I would in a production system.
- I only tested 8 queries; a larger eval set would give more stable numbers.
- No human evaluation was done to triangulate the LLM judge.

**Future work.** I would like to (1) add a human-eval pass on a small sample, (2) try a different judge model for cross-checking, (3) cache web/paper search results so repeated queries don't burn the API quota, and (4) make the Critic agent able to *edit* the draft directly instead of just sending it back for revision.

**Ethics note.** The system always shows the user which sources were used and flags when content is refused or redacted. The safety log keeps an audit trail. I did not collect any user data during testing.

## References

- Brave Software. (2024). *Brave Search API documentation.* https://brave.com/search/api/
- Guardrails AI. (2024). *Guardrails AI: validators for LLM outputs.* https://github.com/guardrails-ai/guardrails
- Kandpal, N., et al. (2024). *Generative Engine Optimization: A new paradigm for content visibility.* arXiv preprint.
- Microsoft. (2024). *AutoGen: Enabling next-generation LLM applications via multi-agent conversation.* https://github.com/microsoft/autogen
- Semantic Scholar. (2024). *Semantic Scholar Academic Graph API.* https://www.semanticscholar.org/product/api
- Zheng, L., et al. (2023). *Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena.* *NeurIPS 2023.*
