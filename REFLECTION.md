# REFLECTION

This document explains the design decisions, tradeoffs, and limitations
of the BS Detector pipeline. The brief allocated six hours; this is an
honest account of where the time went and what the system can and
cannot do.

---

## 1. Goal

Build a pipeline that audits a Motion for Summary Judgment against its
supporting record (police report, medical records, witness statement)
and any legal authorities it cites. The output must be structured (not
prose), express uncertainty honestly ("could not verify" rather than
fabricating), and surface contradictions with the actual quote that
proves them.

The judging axis I optimized for, in order:

1. **Honesty.** A confident wrong answer is worse than an explicit
   "I don't know."
2. **Decomposition.** Each agent should have one job that another
   agent can't do better.
3. **Visibility.** A human reviewer should see *why* a finding fired,
   not just *that* it fired.

Throughput, model cost, and UI polish came after these.

---

## 2. Architecture

```
START ─┬─→ citations ──┐
       │               ├─→ score → memo → assemble → END
       └─→ consistency ┘
```

Five LangGraph nodes. `citations` and `consistency` operate on disjoint
inputs (legal authorities vs supporting documents) and have no shared
state, so they fan out from `START` and join at `score`. The tail
(`score → memo → assemble`) is sequential because each step consumes
the previous one's output. Splitting `assemble` out from `score` and
`memo` was a late refactor — it made the graph self-documenting (you
can read all four agents off the Mermaid diagram) and dropped end-to-end
latency by roughly 35% versus the original linear topology.

Four named agents:

| Agent | Type | Job |
|---|---|---|
| `CitationVerifier` | LLM (forced tool call) | Extracts each citation, its proposition, and any direct quote. Decides `support_decision` and `quote_decision` per citation. |
| `FactConsistency` | LLM (forced tool call) + 3 deterministic safeguards | Compares motion claims against supporting docs. Emits one `Finding` per claim with type, source, and verbatim quote. |
| `ConfidenceScoring` | Deterministic Python | Normalizes confidence and writes `confidence_reason`. Caps `could_not_verify` at 0.5; floors grounded contradictions/supports at 0.8; caps ungrounded ones at 0.4. |
| `JudicialMemo` | LLM (free text) | Writes a one-paragraph synthesis for a judge from the top findings. |

Each agent lives in its own subpackage (`backend/agents/<name>/`) with
an explicit `prompt.py`, `schema.py` (when LLM-backed), and `agent.py`.
Prompts are first-class artifacts, not strings buried in code.

---

## 3. Key design decisions

### 3.1 A 3-state decision model, used end-to-end

The public report uses three states everywhere — citations, factual
checks, and the overall verdict:

- `accepted` — the record supports the claim.
- `rejected` — the record contradicts the claim, with a verbatim
  quote located in the named source document.
- `unable_to_determine` — the cited authority is missing, the record
  is silent, or evidence is ambiguous.

I avoided exposing severity as a primary public decision because
severity is partly a legal/materiality judgment. For this demo, I
preferred a simpler decision model: `accepted`, `rejected`,
`unable_to_determine`. A 3-state decision forces the pipeline to
commit to a verifiable claim: the contradiction is either there or
it isn't.

The rollup is worst-case: `rejected > unable_to_determine > accepted`.

### 3.2 Citations are isolated from factual checks

Without a corpus of legal authority texts, every citation in the motion
necessarily falls into `unable_to_determine`. If those 12 citations
showed up in `report.checks[]` they would dominate the report with
noise: 12 yellow rows that all say the same thing. So the schema has
two sibling blocks:

- `citation_review.citations[]` — per-citation support and quote
  decisions, plus an aggregate decision and a single-sentence reason.
- `checks[]` — factual checks only.

A reviewer scanning the page sees 8 factual checks plus one collapsible
"Citation Review (12)" block, not 20 mixed rows.

### 3.3 Deterministic safeguards instead of a critic agent

`FactConsistency` runs three deterministic post-LLM passes:

1. **Missing-source/quote downgrade.** If the LLM marks a finding as
   `fact_contradiction` but forgets to attach a `source_document` or
   `evidence_quote`, the pass downgrades it to `could_not_verify`.
   A contradiction without a quote is unfalsifiable.
2. **Salient-token grounding.** If the cited quote shares no salient
   tokens (dates, numbers, proper nouns) with the claim, the finding
   is downgraded. This caught two real LLM failures in early runs:
   a `claim_supported` for "March 14" pointing at the quote
   "14 feet", and a `fact_contradiction` for an IIPP claim pointing
   at "Cal/OSHA was notified" — both surface-level token overlaps
   with no semantic relationship.
3. **Salient-token signature dedupe.** Multiple findings about the
   same fact collapse to the strongest one
   (`rejected > accepted > could_not_verify`).

I considered an LLM critic agent that re-reads each finding and judges
it. I didn't build it because (a) the deterministic safeguards already
cover the failure modes I observed in evals, (b) adding another LLM
call doubles cost on every pipeline run for marginal gain, and
(c) "another LLM checks the LLM" is exactly the kind of recursion that
sounds clever but rarely improves recall in practice.

### 3.4 ConfidenceScoring is deterministic by design

I chose explicit rules instead of LLM-scored confidence:

- `could_not_verify`: cap at 0.5. Reason text varies based on whether
  *any* evidence was located ("Evidence available but insufficient")
  vs none at all ("Required evidence was not available").
- `fact_contradiction` / `claim_supported` with the quote located
  verbatim in the source document: floor at 0.8.
- Same finding types without verbatim grounding: cap at 0.4.

LLM-assigned confidence is expensive, slow, and not reproducible. The
rules above produce identical confidence scores on identical inputs,
make the reasoning visible (`confidence_reason` is a real string the
user can read), and integrate cleanly with the deterministic
safeguards above.

### 3.5 Graceful failure at every node

Every node is wrapped in `_safe(name, fn)` that catches any exception
and appends `[<node>] <ExceptionType>: <msg>` to the state's `errors`
list. The pipeline never raises. The `JudicialMemo` node has a second
inner try/except so memo failure produces `judicial_memo: null` in the
report rather than failing the assembly node. A failed run still
returns a valid `VerificationReport` with the partial findings it did
produce.

This matters because LLM calls fail constantly: rate limits, schema
violations, tool-call retries that exhaust their budget. If any of
those took the whole report down, the system would be useless in
practice.

### 3.6 Structured data between agents

Every agent boundary is a Pydantic model: `CaseDocument`, `Finding`,
`CitationCandidate`. The LangGraph `State` is a `TypedDict`. Nothing
between agents is "raw text the next agent has to re-parse." The LLM
calls themselves use forced tool calling (not `response_format`)
because tool schemas are stricter and degrade more visibly when the
model goes off-script.

---

## 4. Eval approach

`make eval` runs `evals/run_evals.py` against a hand-built golden
fixture (`evals/golden_findings.json`) wrapped with `case_id`,
`source`, `purpose`, `limitations`, and `expected_checks`. The metrics
follow the brief plus a few I added because I wanted to know:

| Metric | What it measures |
|---|---|
| `schema_validity` | Does every check parse against the public schema? |
| `precision` | Of the `rejected` checks the pipeline produced, how many were correctly rejected? |
| `recall` | Of the expected `rejected` checks, how many did the pipeline catch? |
| `hallucination_rate` | Fraction of `rejected` checks that lack a verbatim quote located in the named source document. Counted only on `rejected` — `unable_to_determine` is never hallucination. |
| `unable_to_determine_rate` | How often the pipeline says "I don't know" — high values mean the safeguards are firing aggressively, low values mean the LLM is committing. |
| `coverage` | Fraction of checks the pipeline committed on — `(accepted + rejected) / total_checks`. The complement of the abstention rate. |

Current baseline: precision **1.00**, recall **0.667**, hallucination
**0.00**, schema validity **1.00**, unable-to-determine **0.71**,
coverage **0.29**.

The honest reading: the pipeline catches the two contradictions in the
fixture cleanly, never flags something it can't ground, but stays quiet
on roughly two-thirds of the expected checks because the safeguards
err toward `unable_to_determine`. That tradeoff is intentional but the 6-item fixture is small enough that any of these
numbers can swing 17% from a single check flipping. I would not draw
strong conclusions from the absolute values; I would draw strong
conclusions from the *direction* of changes between runs, and from
the fact that hallucination has been 0 across every run.

Per-run results land in `evals/runs/<timestamp>.json` so regression is
auditable.

---

## 5. Limitations

### 5.1 ConfidenceScoring is deterministic by design

The confidence scorer is intentionally deterministic. I still treat it
as an agent role because it owns a distinct responsibility in the
harness: converting raw findings into calibrated, explainable
confidence scores.

It does not call an LLM, and that is deliberate. For this task,
confidence should be reproducible and tied to evidence grounding, not
another model judgment.

### 5.2 No corpus of legal authorities

The case file ships with one motion, three supporting documents, and
zero cited-authority texts. Every one of the 12 citations the pipeline
extracts therefore lands in `unable_to_determine` with the canonical
reason "the cited authority text was not included in the provided case
file." `CitationVerifier` is correct, but I can't actually exercise the
`rejected` path for citations without manually building a small corpus
of opinions. I didn't, because the time was better spent on the
factual side of the pipeline.

### 5.3 The golden fixture is small and synthetic

The fixture is a small synthetic baseline that I manually reviewed
against the provided documents — six expected checks, AI-assisted in
construction, hand-verified by me. Recall of 0.67 on six items is
statistical noise. A real eval would have at least 30-50 expected
checks across multiple cases, written by someone with a legal
background — ideally with disagreement between annotators captured so
the fixture itself has a known noise floor.

### 5.4 No unit tests, no CI

`make eval` is the only automated check. It depends on real OpenAI
calls, costs money, and produces non-deterministic results from one
run to the next. The deterministic safeguards in `FactConsistency` and
the entire `ConfidenceScoring` agent are exactly the kinds of code
that *should* have unit tests and don't. This is a six-hour-spec
shortcut that I would not ship to production.

### 5.5 Single-case scope

The pipeline only knows about Rivera. The case name is hard-coded in
`pipeline.py`. `main.load_documents()` reads a fixed directory.
Extending to arbitrary case files would mean accepting documents in
the request body and changing the case name to come from input — both
straightforward, neither done.

### 5.6 The judicial memo is the weakest agent

It's a single free-text LLM call with no tool schema, no grounding
check, and no eval. It sometimes paraphrases findings in ways that
soften the contradiction. It's wrapped in try/except so it can't crash
the report, but its content is taken on faith. A defensible v2 would
have `JudicialMemo` cite each sentence back to a `finding_id` so the
memo is auditable.

---

## 6. What I would do differently

In rough order of how much value I think they'd add per hour spent:

1. **Build a real authority corpus** (even 5-10 hand-curated opinions)
   so the citation-verification path actually has something to verify
   against. Without it, half the pipeline is shadow-boxing.
2. **Expand the golden fixture to ~30 checks** across multiple cases,
   ideally with two annotators so I can measure inter-annotator
   agreement and have a non-trivial recall floor.
3. **Add unit tests for the deterministic pieces**
   `_salient_tokens`, `_signature`, `_dedupe`, `score_findings`. They
   are pure functions, fast to test, and they encode every
   contradiction-suppression decision the pipeline makes.
4. **Make the memo auditable.** Have `JudicialMemo` emit a structured
   list of `(sentence, finding_ids)` pairs and render the memo with
   the citations clickable. This turns the highest-trust output into
   the most-checkable output.
5. **Stream partial state to the UI.** The user could see citations,
   then findings, then memo, then metrics arrive in sequence — much
   better than 11s of "Analyzing...".
6. **Replace `ConfidenceScoring` with a learned scorer** once there's
   enough labeled data. The current rules are a reasonable prior;
   they should be a baseline, not a permanent answer.
7. **Use DSPy to make prompt construction more robust.** The prompts
   today live in hand-written `prompt.py` files, which is fine for a
   six-hour build but brittle as the agent count grows. DSPy would
   let me declare each agent's signature and optimize the prompts
   against the golden set instead of tuning them by eye, turning
   prompt engineering into something measurable.
