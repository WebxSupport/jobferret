# JobFerret: research brief and build plan

*Compiled 2 November 2026 from the four research tracks in this folder. Read this first; go to the numbered documents for the evidence.*

| Doc | What it is | Becomes, in the skill |
|---|---|---|
| [01-landscape-and-architecture.md](01-landscape-and-architecture.md) | Teardown of `job-applier-agent` and LoopCV, competitor failures, what each job board and ATS actually permits, technical approach, risks, recommended architecture, name check | `SKILL.md` router, `references/gates-and-limits.md`, `references/browsers.md`, per-platform playbooks, data model |
| [02-sector-application-playbooks.md](02-sector-application-playbooks.md) | Universal application rules plus 21 sector playbooks (UK/US/EU), outreach norms, decision table | `references/sectors/*.md`, the posting-quality scorer, the outreach policy |
| [03-cv-best-practices.md](03-cv-best-practices.md) | Evidence on how CVs are read and parsed, a 10-dimension critique rubric, the honesty boundary, rewrite rules, 15 before/after bullets, sector × region table, myths | `cv-audit` mode, `ledger_check.py`, locale files, the DOCX/PDF templates |
| [04-human-voice-writing.md](04-human-voice-writing.md) | What marks text as machine-written and what to do instead; banned and rationed lists; voice-capture protocol; 32 before/after pairs; self-review checklist; AI-disclosure guidance | `references/voice.md`, `voice_lint.py`, the voice-profile schema, coach mode |

---

## 1. What the research changed about the idea

The brief was: tell it what you want, it fixes your CV, finds every matching job on Indeed and the other boards, applies to as many as it can, and emails recruiters. Most of that survives. Two things don't, and one gets bigger.

**You can't auto-submit on Indeed or LinkedIn.** Indeed's Job Seeker Terms, updated 29 September 2026, prohibit "any automation, scripting, or bots to automate the Indeed Apply process". LinkedIn's User Agreement bans automated methods and its help pages say accounts using automation extensions risk restriction or shutdown. The author of AIHawk (the best-known open-source LinkedIn bot) was banned and threatened with legal action. The skill therefore never clicks submit on either site. It does everything up to that click: finds the job, scores it, tailors the CV, drafts every screening answer, and hands over. And it has a better move available: many Indeed and LinkedIn postings are syndicated from, or link through to, the employer's own ATS (the share is unquantified; no source measures it). The agent resolves that canonical posting and applies *there*, where the tailored CV can be uploaded and automation is a grey area rather than a ban.

**"As many jobs as it can find" is the wrong target.** Hosted auto-apply products score 1.7 to 2.1 on Trustpilot; the dominant complaint is invented qualifications. Assist tools score above 4. Huntr's 598,000-application dataset shows people sending 11 to 20 tailored applications got interviews at 8.1%, against 2.9% for people sending over 100. Employers now receive about 258 applications per posting. The scarce signal is a specific, true, well-matched application, so the skill ranks and recommends, applies at a human pace (10 to 15 a day, hard cap 25), and reports cost per interview honestly.

**The CV and writing work gets bigger.** The predecessor treats tailoring as word substitution and, in its `formatting_rules.md`, tells the model to insert "99.9% uptime" or "reduced latency by X%" whenever the advert mentions reliability. That is fabrication by instruction. The research replaces it with a *fact ledger*: the CV is parsed into facts, each tied to its source line, and every generated sentence must cite ledger IDs or it fails validation. Every piece of prose then goes through a voice lint built from measured AI tells, not folklore.

## 2. Design decisions

Numbered to match doc 01 §"Decisions & Recommendations"; the other docs are cited where they add evidence.

1. **An honest copilot that earns autonomy.** Autonomous for discovery, scoring, tailoring and form-filling up to the review page. Per-item confirmation before any submit or send. An opt-in `--auto` mode with a daily cap exists only for employer ATS forms, and only after the user has reviewed 20 applications by hand with zero uncited claims (Phase 1 exit criterion).
2. **Never click submit on LinkedIn or Indeed.** Prepare everything; the user clicks. Resolve to the employer's ATS first.
3. **Discovery through APIs and feeds first, browser second.** Adzuna and Reed APIs; Greenhouse, Lever, Ashby and SmartRecruiters public job-board feeds; Workday's `cxs` JSON; NHS Jobs RSS; Indeed's official MCP server where the user has connected it; the user's own job-alert emails. Browser search only for boards with no feed.
4. **Browser: the user's real Chrome via Claude in Chrome by default.** Existing logins, no stored passwords. Fallbacks: Playwright MCP in `--extension` mode (the Codex default), then the desktop browser pane. The skill never creates accounts or solves CAPTCHAs.
5. **Fabrication impossible by construction.** The fact ledger plus `ledger_check.py`. Unconfirmed figures ship as `[CONFIRM: …]` and block submission until resolved. The honesty boundary is doc 03 §4.1; its test is "could the candidate say this aloud to the hiring manager with their former line manager in the room?"
6. **Voice from the user's own writing.** Three to five writing samples and an eight-question interview produce a voice profile (doc 04 §5). Every draft runs the 12-step self-review (doc 04 §7). Where an employer bans AI-drafted content, the skill switches to coach mode and the user writes.
7. **Outreach is one-to-one, low volume, and drafted for approval.** Only published or verified addresses; no guessed email patterns. One or two contacts per application, three touches maximum over three weeks, suppression list, retention limit. GDPR and PECR notes are in doc 01 §E.
8. **Local data in SQLite under `~/.jobferret/`.** Each application archives exactly what was submitted. Stats are derived, never hand-maintained. One-command export.
9. **Follow the open Agent Skills spec** so the same folder works in Claude Code and Codex. `name` and `description` in frontmatter; Codex extras in `agents/openai.yaml`; browser tools referenced by capability, not hard-coded `mcp__` names.
10. **Job suggestions come from data the user gives the skill.** A skill cannot read claude.ai memory or chat history. It can read Claude Code's project memory, a pasted or exported memory summary (the `import-memory` flow), the user's profile, and its own outcome data (which role families got replies). `suggest` shows its evidence for every recommendation.
11. **UK-first locale defaults, US and EU supported.** A4, two pages, no photo or date of birth, UK spelling; Letter and one page for early-career US; DACH photo norms handled by asking. Equality-monitoring questions are never auto-answered.
12. **The name is JobFerret.** The working name "Jobbernaut" turned out to be an active open-core job platform on GitHub, and "JobHound" is an existing Claude Code job MCP server. Of six fresh candidates, JobFerret was the only one clean on GitHub, npm, PyPI and the obvious domains (doc 01 §H). Trademark registers have not been searched.

## 3. What each track found that the skill depends on

**Landscape (doc 01).** The predecessor's tailored CV is never actually uploaded; the original PDF is. It tells users to install `@anthropic/mcp-playwright`, a package that does not exist on npm, which is a supply-chain hole. It defaults the veteran and disability questions to "No". Two skills in the repo share the name `apply-job`, one still carrying "AUTO-PROCEED / JUST DO IT" wording. LoopCV supports at most 20 boards on paid tiers, scores 3.8 on Trustpilot from 16 recent reviews, and its CEO's blog warns against tools that drive a logged-in LinkedIn session, which is what its own extension does. The *Amazon v Perplexity* appeal weakens computer-misuse claims against user-directed agents but does nothing about account bans, which are the real risk.

**Sectors (doc 02).** Referrals are about 1% of applications but roughly 40% of referred candidates reach interview, against 3% for cold applicants (Ashby, 38m applications). Two-page CVs out-converted one-page in Huntr's sample. Up to 34% of UK postings in Greenhouse's December 2025 survey were never actively recruited for, so the skill scores ghost-job risk and prefers roles on the employer's own page. UK specifics the predecessor had no idea about: NHS shortlisting is scored against the person specification; Civil Service uses Success Profiles with word limits set per advert and assessors stop reading at the limit; agencies need a logged right-to-represent per role and two agencies submitting you to one firm can disqualify you; umbrella-company joint liability started 6 April 2026. The "apply in the first 24 hours or lose 8x" statistic traces only to blog reposts.

**CV (doc 03).** The "75% of CVs are rejected by ATS" figure is a 2012 sales claim from a defunct vendor. Knock-out questions and humans reject; AI *ranking* is real (Mobley v. Workday was certified as a collective action in May 2025). A 445-recruiter experiment put the cost of a few typos at about 7 percentage points of interview probability, and many typos at 18.5. Ladders' 7.4-second figure is triage, not reading; shortlisted CVs get two to four minutes. Non-generative AI editing raised hires 8% in a 500,000-person field experiment, while about 20% of hiring managers say they would reject generic AI prose, so the policy is: edit for errors, clarity and keyword gaps, keep the content specific and human.

**Voice (doc 04).** The five tells that matter: generic claims with no names, numbers, dates or places; a why-us paragraph that survives swapping in a competitor's name; openers about the writer's feelings or the act of writing; stock structures (three-item lists, "not X but Y", trailing "-ing" clauses); and the model's own habits. A September 2026 corpus study found Claude overuses "matters because", "the single most" and "less like X, more like Y", so the checklist has a step for the agent's fingerprints. The em dash was a real ChatGPT habit until 2025 and is now near the human rate in Claude, but recruiters have heard the meme, so it's rationed to one per document. Civil Service guidance treats AI-written answers as grounds for withdrawal; Anthropic's own candidate guidance asks for a human first draft. The disclosure wording for "did you use AI?" is in doc 04 §8 and never advises ticking "No" when the answer is yes.

## 4. Build plan

```
jobferret/                         # the skill; never holds user data
  SKILL.md                       # frontmatter, mode router, gate policy (<300 lines)
  agents/openai.yaml             # Codex metadata and MCP dependencies
  references/
    modes/        cv-audit, profile, hunt, apply, outreach, track, prep, suggest
    playbooks/    greenhouse, lever, ashby, workday, smartrecruiters,
                  linkedin-assist, indeed-assist, generic
    sectors/      distilled from doc 02
    locale/       uk-cv, us-resume, eu-cv
    voice.md  gates-and-limits.md  injection.md  outreach-law.md  browsers.md
  scripts/
    db.py  cv_extract.py  cv_render.py  ledger_check.py  voice_lint.py
    discover_{adzuna,reed,ats,nhs}.py  ats_detect.py  dedupe.py  memory_import.py
  assets/templates/   cv-uk.docx  cv-us.docx  cover-letter.docx
~/.jobferret/                      # user data: config.toml, jobferret.db, applications/<id>/
```

**Phase 1: the CV engine and single-URL apply.** `setup`, `cv-audit`, `profile`, `apply <url>`. The fact ledger and validator, DOCX and PDF rendering, SQLite store, both browser back-ends, voice capture and lint. Playbooks for Greenhouse, Lever, Ashby and generic forms; assisted Workday. UK and US locales. Every submit confirmed. *Exit: 20 real applications, zero uncited claims, zero wrong fields.*

**Phase 2: discovery and the daily loop.** `hunt` over Adzuna, Reed, ATS feeds, NHS Jobs, Indeed MCP where connected, and job-alert emails; canonical-posting resolution; ghost-job and quality scoring; a scheduled digest with reasons; the question queue for unanswered screening questions; capped `--auto`; LinkedIn and Indeed assist modes.

**Phase 3: outreach, memory, analytics.** `outreach` with address verification, suppression and retention; reply parsing into `track`; funnel analytics by role family, CV variant and source; `suggest` with memory import; `prep`.

## 5. Open items and decisions for you

- **Name.** JobFerret, subject to a UK IPO / USPTO / EUIPO search before anything is published. jobferret.com appears parked; .dev and .ai were free at the time of checking.
- **Terms of service not verified:** Glassdoor, Totaljobs/StepStone, CV-Library, ZipRecruiter, Jobserve. Treat as "assist tier" until checked.
- **Feed endpoints not confirmed:** Workable, Teamtailor, Recruitee, Personio, Pinpoint.
- **Whether Claude Code can use claude.ai connectors** (Indeed MCP, Gmail send) needs a hands-on test.
- **Your own inputs the skill will need:** a master CV, three to five writing samples, target roles and hard exclusions, Adzuna and Reed API keys (both free), and whether you want UK-only or UK plus US discovery to start.
- **Evidence quality.** Most quantitative hiring data comes from vendors with something to sell; every such figure is tagged in the docs. UK and EU numbers are thinner than US ones because the search tooling is US-centric.

## 6. Spend

Four research agents plus three follow-up passes: about 930,000 tokens of subagent work. Sector sweep on Sonnet (243k including its gap-fill), the other three on Opus at high effort (landscape 229k including two follow-ups, CV 244k, voice 211k). The gap-fills were continuations of the same agents, so their context was cached rather than rebuilt.
