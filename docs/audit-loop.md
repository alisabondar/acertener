name: "spec-audit-loop"
description: "Build numbered steps from a source spec/proposal, then run strict audit-and-fix loops until every item in the document is met. Use for '/goal build steps 1-7 against this doc', 'audit against the proposal', 'loop until it matches the spec'."
Spec Audit Loop
Build the requested steps (e.g. "steps 1-7") from a source document, then audit the build against that document and fix gaps, looping until nothing is left. The source document is the only definition of done.
Inputs
Source document: the proposal/spec (attached file, path in a connected folder, or link). Read it in full before doing anything.
Step range: which numbered steps/sections to build. If unstated, build all numbered steps.
Target: the repo/folder being built in.
If the source document or step range can't be found, ask once; otherwise proceed without check-ins. Complete the whole range in one run — never stop partway to ask whether to continue.
Phase 0 — Extract the checklist
Turn the in-scope steps into a numbered requirements checklist, quoting the document's exact wording for each item (S3.2: "Agents must write logs to ./logs"). One requirement per line. Only include what the text actually says — no inferred or implied extras. Save it as AUDIT.md in the target, with a section per round.
Phase 1 — Build
Implement the steps in order. Use parallel subagents for independent steps. Commit (or save) after each step, and post a short progress update after each step — not just one at the end. Never sleep/wait arbitrary durations; poll real signals or move on.
Phase 2 — Audit (one round)
For each checklist item, mark it MET, PARTIAL, or MISSING, with evidence (file:line, command output, test result). Prefer a fresh subagent as auditor so it isn't grading its own work; give it the checklist, the source document, and these rules:
Respect the exact language. An item is MET when the build does what the sentence says. Judge the words, not what the author might have wanted.
No speculation. Don't flag things that could break, hypothetical edge cases, or unstated requirements.
No improvement work. Once an item ticks the box, it's done. Do not raise findings about making it better, safer, faster, cleaner, or more isolated unless the document explicitly requires that property.
Anything not traceable to a quoted line of the document goes in a separate Out-of-scope list, not the findings.
Record the round in AUDIT.md: findings (traceable, PARTIAL/MISSING) and out-of-scope notes.
Phase 3 — Fix
Build every PARTIAL/MISSING finding. Ignore out-of-scope notes. Commit and post progress, then return to Phase 2.
Stopping rules
Done: an audit round returns zero PARTIAL/MISSING findings. Stop.
Scope-creep breaker: count "new items" per round — findings never mentioned in the source document or any previous audit round. If 3 consecutive rounds each surface more than 5 new items, the auditor is overly harsh: disregard it, clear the goal, and stop. Report this explicitly.
Repeated findings (same item failing again) are not "new"; keep fixing them. If the same item fails 3 rounds running, record the blocker and stop on that item rather than looping forever.
Final report
Short summary: steps built, rounds run, final checklist status (all MET, or which items are blocked and why), whether the scope-creep breaker fired, and where AUDIT.md lives. No list of suggested improvements.