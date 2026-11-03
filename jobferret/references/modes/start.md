# Mode: start

The entry point for a new user, and the one command a returning user can always type. Goal: from nothing to a saved profile and a first verdict on the CV in about ten minutes, with at most four questions asked before the verdict. Read `references/ux.md` first; every rule there applies here.

Six announced steps, then a menu. Each step writes the run state first (`ux.md` §5), so the user can leave at any point and say `start` again to continue.

**Count the questions.** In the normal case a new user meets exactly four before the verdict: the four in step 4. Everything else is conditional or is not a question. The CV question (step 2) comes only when no file is found. "Replace the ledger?" comes only when the user names a different CV from the one already read. The titles retry in 4a asks question 1 again; it replaces that question, it doesn't add one. The assumptions screen in step 5 is a confirmation the user answers with "go", not a question. If you find yourself asking anything else before step 6, it belongs in the queue (`qa.py add`) instead.

## 0. On entry

Run `python scripts/state.py show` and check for `~/.jobferret/profile.json`.

- **Unfinished `start` run:** "Last time you stopped at step 3 of 6 (Draft profile). Continue, or start again?" Continue skips to that step.
- **Returning user** (`profile.json` exists with `meta.status` `confirmed`, no unfinished run): don't repeat onboarding. Show:

  ```
  Welcome back, Hannah.
  Last run: apply, finished on 2026-11-02.
  3 questions are waiting (say "questions" to answer them).
  What next?
  1. hunt: find new jobs that match your profile
  2. apply <url>: apply to one job
  3. cv-audit: the full CV audit and rewrite
  4. profile: add more detail (answers to common questions, your writing voice)
  ```

  The questions count comes from `python scripts/qa.py pending --json`. Leave out lines that don't apply. Stop here.
- **New user:** go to step 1. Say the stop line from `ux.md` §7 once, in the first message.

## 1. Toolchain and folder

```
Step 1 of 6 · Checking your computer (a few seconds)
```

`python scripts/state.py set --mode start --step 1 --of 6 --name "Toolchain"`, then follow `modes/setup.md` §1–2: `python scripts/setup_check.py --create --json`, then detect the browser back-end per `browsers.md` and record it with `python scripts/setup_check.py --set browser.preferred=<chrome|playwright|pane|none>`. Locale defaults to `uk`; don't ask unless the user or the CV points elsewhere (a US phone number, Letter page size, "resume").

End line, for example: "Ready. Python and the CV libraries are installed; PDF export works through Word; browser: Claude in Chrome." If a required library is missing, show the `pip install` line and offer to run it; this is the one thing that blocks.

## 2. Find the CV

```
Step 2 of 6 · Reading your CV (about a minute)
```

Look in this order, and stop at the first hit:

1. A path or attachment in the user's message. Copy it into `~/.jobferret/cv/source/` under its own name.
2. A file already in `~/.jobferret/cv/source/` (the newest, if several; say which you picked).
3. Ask one question: "Where's your CV? Give me the file path (for example `C:\Users\you\Documents\CV.pdf` or `~/Documents/CV.docx`), or paste the text here." Pasted text is saved as `~/.jobferret/cv/source/pasted-<YYYY-MM-DD>.md` and read from there.

Then:

```
python scripts/cv_extract.py <file> --out ~/.jobferret/cv/ledger.json --text ~/.jobferret/cv/source.txt --json
```

If a ledger already exists from this same file (same `source.sha256`), skip extraction. If it came from a different file and the user named the new file in this run, ask once whether to replace it (`--force` keeps a backup). Otherwise keep the existing ledger and say in the end line which file it came from.

End line, from the report: "Read 2 pages: 3 roles, 18 bullets, 36 facts. One warning: your contact details are in the page header, which some parsers skip." Exit 1 means an unreadable file or a fragment; handle it exactly as `modes/cv-audit.md` §1 says, then carry on with what there is. No CV at all ("I don't have one yet") is fine: skip to step 4 and say the verdict will wait.

## 3. Draft the profile

```
Step 3 of 6 · Drafting your profile from the CV (a few seconds)
```

```
python scripts/profile_prefill.py --ledger ~/.jobferret/cv/ledger.json --out ~/.jobferret/profile.json --merge --json
```

`--merge` is safe on a new or an existing profile: it never overwrites a value the user entered. Don't show the field list it prints. Keep it for the assumptions screen in step 5. End line: "Drafted from the CV: name, contact details, Leeds, Senior Finance Analyst at Northgate Foods. Four things I can't tell from a CV come next."

## 4. Preferences

```
Step 4 of 6 · Your preferences (two minutes)
```

Do not ask "form or chat?" as a question of its own; that would be a fifth question before anything useful. Put the offer on the last line of the four-question message, so the user can answer the questions or say `form` in one reply. Leave the offer out when no browser can show the page.

### 4a. Chat: the four questions

Defaults come from the draft profile. One message:

```
Four questions. Reply by number; skip keeps the default, later saves it for another time.
1. What jobs should I look for? (default: Senior Finance Analyst, from your CV)
2. Where and how? Town, how far you'd travel, and remote / hybrid / office. (default: Leeds, 20 miles, hybrid or remote)
3. Lowest pay you'd consider, per year or per day? Never shown to employers. (default: no floor)
4. Do you have the right to work in the UK, and will you ever need visa sponsorship? (default: not set; I'll ask when a form needs it)
Or say "form" and I'll open a short page with all of this prefilled.
```

Write the answers through the same validation the form uses. Put them in a temporary JSON file and run `python scripts/setup_ui.py --from-json <file>`:

```json
{"targets": {"titles": ["Finance Business Partner", "Senior Finance Analyst"]},
 "where": {"town": "Leeds", "radius_miles": 20, "work_modes": ["hybrid", "remote"]},
 "pay": {"amount": 45000, "period": "year"},
 "eligibility": {"right_to_work": "citizen", "sponsorship_needed": false}}
```

These are the page's own field names; `setup_ui.py` maps them onto the profile (`where.town` → `targets.locations`, `pay` → `targets.salary_floor`, `sponsorship_needed` → `eligibility.sponsorship_needed_ever`). Allowed values: `work_modes` ⊂ `remote, hybrid, office`; `period` is `year` or `day`; `right_to_work` is `citizen`, `settled`, `visa`, `none` or empty. The full field list is in `scripts/setup_ui.py` (`build_rules`). Exit 1 prints what failed; fix it or ask the user that one thing again. A skipped question keeps its default; a `later` goes in the queue, for example `python scripts/qa.py add --key eligibility.right_to_work --question "Do you have the right to work in the UK?" --mode start`.

Target titles are the only thing that can't default to nothing. If the user skips question 1 and the CV gave no title, ask question 1 again in a sentence, in place of the original rather than as a fifth question: "I need at least one job title to search for. What would you type into a job board?"

### 4b. The form

Start the page and keep it running in the background:

```
python scripts/setup_ui.py --timeout 1200
```

- **Claude Code:** run it as a background command. Its first output line is `URL: http://127.0.0.1:PORT/?t=TOKEN`. Read that line, then open the URL in the browser pane with `mcp__Claude_Browser__preview_start` and `url` (or `navigate` if the pane is already open). If there is no pane but Claude in Chrome is connected, open it in a new Chrome tab. Otherwise print the URL.
- **Codex:** start it detached with its output in a log in the user folder, then read the URL from the log. When `JOBFERRET_HOME` is set the log goes there (`%JOBFERRET_HOME%\ui.log` on Windows, `$JOBFERRET_HOME/ui.log` elsewhere), not under `~/.jobferret`, because the scripts write everything else there too:
  - Windows (PowerShell): `$jf = if ($env:JOBFERRET_HOME) { $env:JOBFERRET_HOME } else { "$HOME\.jobferret" }; Start-Process python -ArgumentList 'scripts/setup_ui.py','--timeout','1200' -RedirectStandardOutput "$jf\ui.log" -NoNewWindow`
  - macOS and Linux: `nohup python scripts/setup_ui.py --timeout 1200 > "${JOBFERRET_HOME:-$HOME/.jobferret}/ui.log" 2>&1 &`

  Print the URL on its own line: "Open this in your browser, fill it in and press Save: <URL>". In the Codex desktop app the user clicks it and the in-app browser opens.

Then `python scripts/state.py set --mode start --step 4 --name "Preferences" --status waiting --context '{"ui": "page"}'` and wait. Say: "Tell me when you've saved it, or say chat to answer here instead."

The process exits by itself. Exit 0 with `SAVED profile=… config=…` means done. Exit 2 with `TIMEOUT nothing saved` (20 minutes), a dead URL, or the user saying chat: fall back to 4a with the same defaults. Don't wait on a process that has gone; under Codex a server may not outlive the turn, so if the user says "done", check `profile.json` `meta.status` is `confirmed` rather than trusting the log.

The page is safe to leave open: it listens on 127.0.0.1 only, refuses any request without the token or with a foreign `Host` or `Origin`, accepts one JSON save under 64 KB, and serves nothing but itself. API keys typed into it go to `config.toml` and are never shown back.

## 5. Save and show the assumptions

```
Step 5 of 6 · Saving your profile
```

Both routes have already written `profile.json` and `config.toml`. Read them back and show one screen (`ux.md` §4):

```
Saved. Here's what I'm working from:
- Looking for: Finance Business Partner, Senior Finance Analyst (senior, permanent)
- Leeds within 20 miles, hybrid or remote; £45,000 a year minimum
- Right to work: British or Irish citizen; no sponsorship needed
- Sources: Adzuna and Reed (keys still needed), NHS Jobs, Teaching Vacancies, employer boards, alert emails, Indeed (in your browser)
- At most 15 applications a day; every one needs your yes before it's sent
- UK locale; cover letters: ask me each time
Change any of these, or say go.
```

This screen is a confirmation, not a question: "go" or silence accepts it, and it doesn't count towards the four. Corrections go through `setup_ui.py --from-json` again. The form and `--from-json` both set `meta.status` to `confirmed` when they save; a user who leaves before saying go is still recognised on the next run by the unfinished `start` entry in `state.json` (§0 checks that before the returning-user branch), so the flag alone never skips onboarding.

## 6. Quick CV verdict

```
Step 6 of 6 · Scoring your CV (about two minutes)
```

Skip this step if there is no CV. Otherwise score the CV once against `references/cv/rubric.md`, all ten dimensions, using the extraction report from step 2 and the target titles from the profile as the target. Write the full scoring to `~/.jobferret/cv/audit-<YYYY-MM-DD>.md` in the rubric's template, so `cv-audit` can pick it up without rescoring an unchanged CV.

Show only this:

```
Your CV scores 58 out of 100 for Finance Business Partner roles.
The three changes that would help most:
1. 11 of 14 bullets at Northgate describe duties, not results. Each needs a number or an outcome.
2. Your profile paragraph doesn't name the role you want, so a recruiter has to guess.
3. Contact details sit in the page header; some applicant tracking systems never read them.
The full audit and a rewrite take about 20 minutes, with a few questions about your numbers.
```

Blunt about the CV, never the person (`rubric.md` §1). Don't start the rewrite here.

## 7. What next

`python scripts/state.py set --mode start --step 6 --of 6 --name "Done" --status done`, then the menu:

```
What next?
1. cv-audit: the full audit and the rewrite (hunt and apply need it)
2. hunt: find jobs that match your profile
3. apply <url>: apply to one job you've found
```

`hunt` and `apply` need the rewritten master CV, so if the user picks either first, say that the rewrite comes first and why: every claim in a tailored CV is traced to the master. Mention once that `profile` adds answers to common screening questions and a sample of their writing, and that it can wait.
