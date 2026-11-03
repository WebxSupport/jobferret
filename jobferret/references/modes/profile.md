# Mode: profile

Optional, deeper enrichment of `~/.jobferret/profile.json` and `~/.jobferret/voice-profile.json`, after `start` has saved the essentials. The richer the answer bank, the fewer questions `apply` has to stop and ask; the voice profile is what keeps generated prose sounding like the user. Nothing here blocks anything else: `apply` asks what it needs at the moment it needs it, and this mode just gets those answers in early.

Read `references/ux.md` first. Here it means:

- Batches of five questions or fewer, numbered, each with its default. `skip` keeps the default; `later` queues it (`qa.py add`) and moves on.
- Prefill every answer the CV or the saved profile already gives, and ask the user to confirm it rather than type it.
- One progress line per batch (`Batch 2 of 5 · The answer bank`). After each batch, save, then ask "Next batch, or stop here?" Stopping is always fine.
- `python scripts/state.py set --mode profile --step <batch> --of 5 --name "<batch name>"` before each batch, so `profile` can resume.

If `profile.json` doesn't exist, run `start` first. It builds the draft and the essentials in a few minutes.

Never ask for passwords. Never ask about protected characteristics (gender, ethnicity, disability, religion, orientation, age); those fields are the user's alone on every form (gate G3).

Start with `python scripts/qa.py pending --json`. Queued questions come first, as their own batch.

## Batch 1: who and where (confirm)

Show what's saved and ask for corrections only: name as it should appear on documents, phone, email (flag an unprofessional handle and suggest `firstname.lastname@`), town and country, LinkedIn URL, portfolio or GitHub. Then, if not already set: current employment status (employed, notice served, between roles, student) and notice period. Most users answer this batch with "go".

## Batch 2: what you want

Most of this came from `start` or the preferences page; ask only what is still empty or worth refining:

1. Sectors or industries you want, and any to avoid (`targets.sectors`, `targets.avoid_sectors`).
2. Alternate titles recruiters use for your role (adds to `targets.titles`; two to five in all).
3. Hard exclusions: named companies (`exclusions.companies`), shift patterns, travel, clearance requirements, anything that is an automatic no (`exclusions.dealbreakers`).
4. Which of those are dealbreakers (skip without asking) and which are preferences (score down but show it). Store them in `exclusions.dealbreakers` and `exclusions.preferences_against`.
5. Contract types and, for contracts, day rate and IR35 stance (`targets.contract_types`, `targets.salary_floor` with `period: "day"`, `targets.ir35`).

The salary floor is the number below which the user would rather not apply. It never goes on a CV.

## Batch 3: the answer bank, part one

Common screening questions, answered once in the user's words:

1. Why are you looking, or why did you leave?
2. Willing to relocate? Travel you'd accept, as a percentage of the week?
3. Earliest start date, and when you can do interviews (for example "weekdays after 4pm").
4. "How did you hear about us?" default (for example "company careers page"; corrected per application).
5. Salary wording when a field is mandatory. Show the default from `references/gates-and-limits.md` §8 (anchor in the advertised range; never current salary) and ask whether it's fine.

## Batch 4: the answer bank, part two

1. Years with your main skills or tools, with a one-line proof each. Prefill the list from `history.skills` (the top five by how often the ledger mentions them) and ask only for the years and the proof. These become ledger facts with `provenance: profile`.
2. Driving licence; languages and level.
3. Professional registrations or tickets with numbers and expiry (NMC PIN, GMC, SRA, CSCS, CIMA and so on).
4. References: "available on request" is assumed in the UK and US; collect two or three names for later, never for the CV.
5. Any answer the user wants handled a fixed way (for example "always say 'company careers page' unless I tell you otherwise"). Legal declarations (criminal record, "the information is true") are not fixed answers: the user answers them on each form, like protected fields.

## Batch 5: voice capture

Follow the voice-capture protocol in `references/voice/voice.md` §4: ask for three to five writing samples in one message (counts as one question), then the eight interview questions in two batches of four. Extract the idiolect markers and write `voice-profile.json` in the schema given there. Read the profile back in plain words ("You write short sentences, use 'keen' not 'excited', sign off 'Best', British spelling, one joke per email at most") and ask what's wrong.

If the user has no samples to hand, write the profile from the interview alone and mark `"samples": []` so the self-review knows to lean on the interview answers. This batch takes the longest; offer it last and accept "later".

## Working preferences

Cover letter default, the AI-disclosure stance and chattiness are set in `start` (the preferences page, or their defaults). Change them here when asked:

- `preferences.cover_letter`: `ask` (default), `always`, `required` (only when the employer asks for one) or `never`. The sector table in `references/sectors-quick-reference.md` is the fallback when the answer is `ask` and the user isn't around.
- `preferences.ai_disclosure`: `drafting` (default), `light` or `coach` (`references/voice/disclosure.md`). JobFerret never fills the "did you use AI?" field; this sets the wording it proposes and, for `coach`, makes coach mode the default.
- `preferences.confirm_via`: write `[CONFIRM]` questions into the CV draft, or ask in chat (default `chat`).
- `config.toml [ux] chattiness`: `brief` or `normal`.

## Output

`~/.jobferret/profile.json`. Every field exists from the start (`jf_common.empty_profile()`); write answers into these names. `answer_bank`, `targets`, `eligibility`, `exclusions` and `preferences` are what `apply` reads, so don't rename them.

```json
{
  "version": 1,
  "updated_at": "ISO date",
  "personal": {"name": "", "phone": "", "email": "", "location": "", "country": "GB", "linkedin": "", "github": "", "links": []},
  "eligibility": {"right_to_work": "", "sponsorship_needed_ever": false, "notice_period": "", "earliest_start": "", "status": "",
                  "dbs": "", "security_clearance": "", "driving_licence": ""},
  "targets": {"titles": [], "seniority": "", "role_families": [], "sectors": [], "avoid_sectors": [], "locations": [],
              "radius_miles": 0, "remote": "hybrid", "work_modes": [],
              "salary_floor": {"amount": 0, "currency": "GBP", "period": "year"}, "contract_types": [], "ir35": ""},
  "exclusions": {"dealbreakers": [], "preferences_against": [], "companies": [],
                 "filters": {"no_agencies": false, "no_unpaid": true, "no_commission_only": true, "min_company_size": 0}},
  "answer_bank": {"why_looking": "", "skills_years": [{"skill": "", "years": 0, "proof": ""}], "licences": [],
                  "languages": [], "registrations": [], "relocate": "", "travel_max_pct": 0, "start_date": "",
                  "availability": "", "heard_about_us_default": "", "salary_phrasing": "", "fixed_disclosures": {}},
  "preferences": {"cover_letter": "ask", "ai_disclosure": "drafting", "confirm_via": "chat"},
  "current": {"title": "", "employer": ""},
  "history": {"roles": [], "education": [], "highest_qualification": "", "skills": [], "certifications": []},
  "meta": {"status": "draft", "prefilled_from": "", "prefilled_at": "", "prefill": {}}
}
```

`current`, `history` and `meta` are written by `profile_prefill.py`; `meta.prefill` records which values it guessed, so a later `--merge` never overwrites what the user changed. This is the only schema: every script, `discover.py` and `screen.py` included, reads these names (`ARCHITECTURE.md` §8.4).

To write answers, use `python scripts/qa.py answer <id> "<text>"` for queued questions, `python scripts/setup_ui.py --from-json <file>` for anything the preferences page covers, and a direct JSON edit only for the answer bank fields neither covers. Keep the file valid JSON.

Add each `skills_years` item and each registration to the ledger with `python scripts/ledger_add.py --ledger ~/.jobferret/cv/ledger.json --kind skill --provenance profile --confirmed --text "Python: 6 years; built the ETL for …"` (one call per fact; it prints the ID). If no ledger exists yet, keep them in `profile.json` only; `cv-audit` adds them.

Finish by summarising what was stored in six lines or fewer, `python scripts/state.py set --mode profile --step 5 --of 5 --status done`, and one line naming the next step (`cv-audit` if no master CV exists yet, otherwise `apply <url>` or `hunt`).
