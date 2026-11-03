# JobFerret

A job-hunting copilot for the UK market, for Claude Code and Codex. It reads your CV the way a parser and a tired recruiter would and tells you what's wrong. It interviews you for the numbers that are missing and rewrites the CV with every claim traceable to something you actually said. It finds jobs from the sources that allow it, screens them with reasons you can check, tailors the CV to each one, writes letters and answers in your voice, fills the form, and waits for your yes before anything is submitted. Afterwards it keeps the follow-ups, the recruiter messages and the funnel in order, and writes your interview notes.

What it refuses to do is the point. It will not invent or inflate a claim: every claim must cite a fact from your CV or your own confirmed answers, and a validator rejects uncited claims and numbers that don't appear in the cited fact. It will not click submit without you seeing the review page. It will not automate LinkedIn or the Totaljobs family of boards, because their terms prohibit it and accounts get locked; their jobs reach it through your own alert emails, and wherever possible it finds the employer's own application page and applies there. Indeed it reads in your own browser during a hunt, a few pages a day and never by script, and Indeed Apply stays your click. It never fills equality or diversity fields, never handles passwords, and ignores instructions hidden in job adverts.

## Status

The current scope is UK support. EU locale support is deferred.

All ten modes are built: `start`, `setup`, `profile`, `cv-audit`, `apply`, `hunt`, `track`, `outreach`, `suggest` and `prep`. On 3 November 2026 the path from `hunt` to `apply` and the never-fetch rule were reviewed and fixed. No live application has been made yet. That first one, on a real employer form, will teach the most, and the playbooks mark what they could not check against a live form. See `SKILL.md` for the modes and `ARCHITECTURE.md` for how the parts fit.

## Install

Requirements: Python 3.11+ and `pip install -r scripts/requirements.txt`. For PDF export, Microsoft Word (Windows or macOS) or LibreOffice. For form filling, one of: the Claude in Chrome extension (your real browser, your logins), a Playwright MCP server, the Codex Chrome extension, or a built-in browser pane for reading.

For a repository checkout or extracted repository ZIP, use the offline installer from the repository root: `python install.py --host codex` or `python install.py --host claude`. It defaults to a project-local install and prints the next steps. See the [repository installation guide](../README.md#install) for downloading, choosing a project, personal installation, ZIP packaging and restricted-session recovery. The installer is a repository tool; it is not included in the skill-only ZIP.

Copy or symlink this whole folder:

- Claude Code: `~/.claude/skills/jobferret/` (personal) or `<project>/.claude/skills/jobferret/`.
- Codex: `~/.agents/skills/jobferret/` or `<repo>/.agents/skills/jobferret/`. Some bundled installers use `$CODEX_HOME/skills`; use their documented destination or pass an explicit project destination rather than assuming that folder must exist.

`references/platforms.md` has the one-line commands for each OS, how to check the skill loaded, and what differs between the two hosts.

## First run

```
/jobferret start            (Claude Code)
$jobferret start            (Codex)
```

`start` checks your computer, reads your CV, drafts a profile from it, asks four questions (or opens a short preferences page on your own machine), gives you a quick verdict on the CV, and offers the next step. The rule throughout is four questions before anything useful, never more than five in one message, every question with a default and `skip`. Then:

```
cv-audit                    the full critique, the metric interview, the rewrite
hunt                        find and screen jobs, shortlist with reasons, apply to your picks
apply <url>                 one job you found yourself
track · outreach · prep     after you've applied
```

Or just talk: "audit my CV", "find me jobs", "apply to this <url>", "write to the recruiter for this role", "what should I prepare for Thursday".

## Where jobs come from

Adzuna and Reed (free API keys, entered once on the preferences page or in `config.toml`), NHS Jobs and the DfE Teaching Vacancies service (no key), the public job boards of employers you name (Greenhouse, Lever, Ashby, Workable, Teamtailor, Recruitee, Personio, Pinpoint, SmartRecruiters), any RSS feed, Indeed UK, and job-alert emails you save into `~/.jobferret/inbox/` from LinkedIn, Totaljobs, GOV.UK Find a job, Civil Service Jobs and the rest (Indeed's too, if you like). Indeed is read in your own browser while `hunt` runs in a session that has one: a few search pages at a human pace, by default at most 4 searches a hunt and 20 pages a day, and never fetched by script. If Indeed shows a check page or asks you to sign in, JobFerret stops reading it for the day. If you are signed in to Indeed in that browser, the searches are on your account and the risk of a flag is yours. `references/sources/uk.md` says how each source is reached, which are never fetched and why, and which boards are worth keeping a CV profile on. `python scripts/hunt_cron.py` runs discovery, screening and the daily digest with no model at all, so it can sit in Task Scheduler or cron; it has no browser, so it skips Indeed.

## Where your data goes

Nothing about you is stored inside the skill folder. Everything lives under `~/.jobferret/`: your config and API keys, profile, voice profile, master CV and its fact ledger, the run state and question queue, one folder per application with exactly what was submitted and screenshots, the daily digests, your saved alert emails and the Indeed pages read in your browser, a cache of API responses with the count of Indeed pages read today, the signals file from any chat export you chose to import, and a small SQLite database. Delete the folder and it's gone. Delete `~/.jobferret/RUN` and the skill stops.

## How it's built

`SKILL.md` is the router and the gate policy. `references/` holds the distilled rules the model reads per task: the guided-experience rules, the CV rubric and rewrite rules, voice rules and banned lists, the UK source table, per-ATS playbooks, interview questions by sector, outreach law, the browser guide and the gates. `scripts/` holds the enforcement layer: CV extraction into a fact ledger, the citation validator, the voice linter, the DOCX/PDF renderer with post-render verification, the preferences page, the source modules and screening, the database, tracking and outreach. `ARCHITECTURE.md` is the contract between them; `scripts/README.md` is the usage reference; `evals/` holds the test cases for the skill itself. The research the rules come from is in `../research/`, every claim tagged by evidence quality; `05-uk-job-market.md` is the UK market study the discovery loop is built on.

The `../research/` links throughout the skill point to the sibling `research/` folder. They are for maintainers; the skill doesn't need that folder at runtime.

## Honesty, in one paragraph

Every bullet and every sentence with a number in anything JobFerret writes ends with a citation to a fact in your ledger. Facts come from your CV or from answers you gave and confirmed. The validator, `ledger_check.py`, checks that each cited fact exists and is confirmed, that every number in a cited sentence appears in a cited fact, and that nothing unconfirmed ships. It can't judge whether the wording is faithful to the fact; the model is held to that by the rewrite rules, and every change is listed in the change log for you to check. If it can't source a claim, it writes `[CONFIRM: …]` and the file won't render until you resolve it. The test for every sentence is whether you could say it aloud to the hiring manager with your former line manager in the room.
