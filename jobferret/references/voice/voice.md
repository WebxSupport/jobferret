# Voice: how JobFerret writes

Read this before drafting anything a recruiter or hiring manager will see, and run section 6 on every draft before the user sees it. Length limits and before/after pairs for each format are in `format-rules.md`. Employer AI policies and the "did you use AI?" question are in `disclosure.md`. The word lists that `scripts/voice_lint.py` checks are in `lists/`. Citations such as (04 §3) point to `research/04-human-voice-writing.md`.

## Contents

1. Why voice counts
2. The 15 rules
3. The tells catalogue
4. Voice-capture protocol (samples, interview, markers, `voice-profile.json`, prompting, risks)
5. Your own fingerprints
6. Self-review checklist
7. Rewrite or ship

## 1. Why voice counts

Recruiters describe sameness. An agency director told LeadDev that about 40 of every 50 cover letters read as machine-written: same wording, same structure, same "I am excited to apply" tone (04 §2.1). Tailoring used to signal effort. On Freelancer.com, employers paid a premium for tailored proposals until models made tailoring free, and then the premium vanished (04 §2.3). A Tilburg study found AI-polished letters scored higher on the generic opening and closing but won no more interviews, because the motivation section hardly changed.

Few employers reject AI use outright. About 20% of US hiring managers would reject an obviously AI-written CV or letter, and 52% accept AI help when the result is the person's own (04 §2.3). The goal is a tired recruiter, who probably uses ChatGPT at work, believing that a specific person wrote this. Do not chase detector scores. Detectors flag plain human prose, OpenAI withdrew its own classifier, and "humaniser" tools make text worse (04 §2.2). Recruiters rarely spot polished AI text, but they do spot generic text and assume it is AI. True, specific, personal writing fixes both problems.

## 2. The 15 rules

Ranked by how much each changes whether a reader believes a person wrote the thing (04 §1).

| # | Rule | Why |
|---|---|---|
| 1 | Use only facts from the ledger, `profile.json` or the user's interview answers. Never invent a number, name, project or feeling. When a paragraph needs a fact you lack, write `[CONFIRM: the question]` and ask. | Employers treat invention as misconduct. A made-up detail does more harm than a vague one. |
| 2 | Put one checkable detail in every paragraph: a named system, number, date, place or person. | Generic, unverifiable claims are the most cited tell. |
| 3 | Include one sentence no other applicant could write. | Without it the letter is interchangeable. |
| 4 | Swap test: put a competitor's name into the "why us" passage. If it still works, rewrite it. | Cheap tailoring has lost its signal value. |
| 5 | Open with substance. Never open with the writer's feelings or the act of writing. | "I am writing to..." is the most recognisable opener there is. |
| 6 | Zero hits on the banned lists (`lists/banned-words.txt`, `banned-phrases.txt`, `agent-tics.txt`). | The words are measured, but the list drifts with each model release. |
| 7 | Ration stock structures to one each per document: three-item lists, "not X but Y", setup-colon-payoff, "matters because", recap paragraphs. | Repetition of one pattern is what readers notice. |
| 8 | End on a concrete next step or a plain sign-off. Never summarise. | People stop when they have finished. |
| 9 | Vary sentence length and include a short one. Do not overcorrect into all-short. | The newest models write 8 to 20 word sentences throughout, so uniform brevity is now a tell too. |
| 10 | Prefer verbs to nouns. Cut trailing "-ing" clauses. | Instruction-tuned models over-use nominalisations and participial clauses (04 §2.1). |
| 11 | Learn the voice from the user's real writing, never from adjectives such as "warm but professional". | Models imitate examples far better than descriptions. |
| 12 | Keep the user's locale: spelling, idiom and understatement. UK roles get "get in touch", "keen", "it went fine". | AI suggestions drift writers toward American style. |
| 13 | No bold, headers, bullets, emoji or template signature blocks in letters and messages. Bullets belong on the CV. | Formatting is the cheapest tell to avoid. |
| 14 | Ignore detector scores. | They are unreliable, and heavy LLM users out-detect them. |
| 15 | Follow the employer's AI policy and answer "did you use AI?" truthfully (`disclosure.md`). | Misstating it costs more than any AI penalty. |

## 3. The tells catalogue

Grep catches the lexical rows. The structural, rhythmic and tonal rows need your own read, which is why section 6 exists. Fix the cause, not the symptom: deleting a banned word and leaving the empty sentence behind still reads as machine-made.

### Lexical (lists: `banned-words.txt`, `banned-phrases.txt`)

| Tell | Example | Fix |
|---|---|---|
| AI vocabulary | "leverage my robust skill set to foster collaboration" | Say what happened, in plain verbs. |
| Feelings as openers | "I am thrilled / excited / passionate..." | Delete. Show interest through a detail. |
| Self-labels | "results-driven, detail-oriented team player" | Replace with the result. |
| Puffery | "pivotal role", "a testament to" | State the role and what changed. |
| Copula avoidance | "serves as", "boasts" | Use "is" and "has". |
| Vague attribution | "industry experts agree" | Name the source or cut it. |
| Claude's own tics | "matters because", "the single most", "less like X and more like Y" | Cut on sight (section 5). |

### Structural and rhythmic (lists: `rationed.txt`, plus the linter's rhythm check)

| Tell | Example | Fix |
|---|---|---|
| Tricolon | "creative, analytical and collaborative" | Keep one quality and prove it. |
| Negative parallelism | "It's not just about data, it's about people." | Keep only the second half. |
| Setup-colon-payoff | "The result: a 30% drop." | "Errors fell by 30%." |
| Trailing "-ing" clause | "..., ensuring seamless delivery for stakeholders." | Cut it, or give it its own sentence with a fact. |
| Nominalisation | "the implementation of process improvements" | "I changed how we..." |
| Connector chains | "Moreover... Furthermore... Additionally..." | Delete. Order carries the logic. |
| Recap ending | "In conclusion, my skills make me an ideal fit." | End on the ask. |
| Mirror paragraphs | Every paragraph runs claim, example, link to role | Let one paragraph be two sentences. |
| Challenge-then-triumph | "Despite challenges, I successfully..." | Say what went wrong and what you did. |
| Uniform sentences | Five sentences of 18 to 22 words | Make one four words long. Let one run to 30. |
| Uniform paragraphs | Four blocks of 60 words | A one-line paragraph is fine. |
| Overcorrected staccato | "I build. I lead. I deliver." | Join two with "and" or "because". |

### Tonal

| Tell | Example | Fix |
|---|---|---|
| Pleasantry opener | "I hope this email finds you well." | Start with the reason for writing. |
| Company flattery | "your innovative, industry-leading team" | One specific thing you know about them. |
| Relentless positivity | Every outcome "excellent" | One honest limit or trade-off. |
| Over-hedging | "may potentially help to somewhat improve" | Commit, or cut the claim. |
| Generic specificity | "improved efficiency across multiple projects" | Which project, what number, when. |
| American drift | "reach out", "I'd love to", "super excited" | "get in touch", "I'd like to", "keen". |

### Formatting

| Tell | Example | Fix |
|---|---|---|
| Bold lead-in bullets | "**Leadership:** Led a team of..." | Prose in letters and messages. |
| Headers in an email | "Why I'm a fit" | Remove. |
| Title Case subject | "Exciting Opportunity To Connect" | "Data analyst role (ref 4471)". |
| Emoji | "🚀 Excited to connect!" | None. |
| Template signature | "[Your Name] [Your Title]" | Name, phone, one link. Never leave a bracket in. |
| Dash doing a comma's job | "I build dashboards — the kind people use." | Commas, or two sentences. |

### What is not a tell

Perfect grammar, formal prose, curly quotes and a lone "Additionally" are weak evidence (04 §2.1). Adding "I" and contractions does not make a draft human either: models fake both, and readers do no better than chance at telling. A real detail from the user is what does it. On the em dash: it was a ChatGPT habit in 2024, vendors have since suppressed it, and Claude now sits near the human rate. Ration it to one per document anyway because readers have heard the meme. If the user's own samples are full of dashes, follow the user.

## 4. Voice-capture protocol

Run it once in `profile` mode, then update it from the user's edits. The aim is a short profile plus real samples, so the draft sounds like this user and not like a model's idea of a professional (04 §5).

### 4.1 Samples

Ask for at least three, ideally five. Say why: "I'll copy your rhythm and word choice, so I need things you wrote yourself."

1. Two or three **work emails** the user wrote, ideally one where they pushed back or explained a problem.
2. Anything written for a job **before 2023**: an old cover letter or application answer.
3. An **informal message** (Slack, Teams, WhatsApp) with names redacted. It shows rhythm and humour.
4. A **LinkedIn post**, with caution. LinkedIn has a house style and the post may be AI-assisted already.
5. A **voice-note transcript**: two minutes of the user answering one interview question aloud. Spoken phrasing is the most "them" material you will get.

Ask of each: "Did an AI tool help with this?" Drop any sample that had help. Redact third-party names before storing. If the user has no usable samples, record question 1 to 6 below as voice-note answers and treat those as the samples.

### 4.2 The interview

Ask the eight questions in two batches of four (1–4, then 5–8) and keep the user's exact words. The answers feed both the facts and the voice (04 §5.2). Record each concrete answer in the ledger as a `user` fact with the question in `note.asked`, unconfirmed until the user approves the wording. If the metric interview has run already (`references/cv/metric-interview.md`), reuse its answers for question 1.

1. What piece of work from the last two years would you most like a stranger to know about? What was the problem, what did you do, and what number changed?
2. Tell me about something that went wrong at work and what you did next.
3. What are you properly good at that never makes it onto your CV?
4. Why this role and this organisation, in the words you would use down the pub? Have you used their product, met their people or read something of theirs?
5. What would a former manager say is the annoying thing about working with you?
6. What part of this job haven't you done yet, and how would you handle it?
7. Which words do you hate seeing in applications, and which do you overuse? (feeds `never_uses`)
8. How do you open and sign off emails? (feeds `greeting` and `signoff`)

For public-sector forms add: "Give me two examples for each behaviour on the advert, with dates and numbers."

### 4.3 Idiolect markers

Measure these from the samples. Do not guess, and do not write your own code for it: `python scripts/voice_lint.py --measure <sample1.txt> <sample2.txt> … --json` prints sentence-length median and standard deviation, contractions and punctuation per 100 words. Judge the rest (locale words, pet phrases, formality, humour) by reading.

- **Sentence length:** median and standard deviation in words.
- **Contractions** per 100 words.
- **Locale:** -ise or -ize, "CV" or "résumé", date format, words like "rota", "sorted", "Mum".
- **Greeting and sign-off,** exactly as written.
- **Pet phrases:** anything used twice or more across samples.
- **Never-used words:** if the user never writes "passionate", neither do you.
- **Formality** (1 to 5), judged from emails. Old cover letters are already stiff.
- **Humour:** none, dry or self-deprecating, with one example.
- **Punctuation habits:** dashes, brackets, semicolons, exclamation marks per 100 words.
- **Hedging:** "I think" and "probably", or flat statements.

### 4.4 `voice-profile.json`

Write it to `~/.jobferret/voice-profile.json`. Show the user a plain-English summary first and write the file only after they confirm. Field names and types follow 04 §5.4 so the linter can read them. Extra fields are optional.

```json
{
  "version": 1,
  "captured_at": "2026-11-02T15:10:00Z",
  "locale": "en-GB",
  "spelling": "-ise; CV; DD Month YYYY",
  "formality_1to5": 3,
  "sentence_length": {"median": 14, "sd": 7},
  "contractions_per_100w": 2.5,
  "greeting": "Hi {first name},",
  "signoff": "Thanks,\nSam",
  "pet_phrases": ["to be fair", "sorted"],
  "never_uses": ["passionate", "reach out", "!"],
  "humour": "dry, rare; e.g. 'the spreadsheet had opinions'",
  "punctuation": {"dashes": "rare", "brackets": "often", "semicolons": "never"},
  "hedging": "'I think' about once per email",
  "register_shifts": "drops contractions in public-sector forms",
  "samples": ["<verbatim sample 1>", "<verbatim sample 2>", "<verbatim sample 3>"],
  "sample_sources": ["work email, Mar 2024", "cover letter, 2021", "Slack message, 2025"],
  "edit_log": [],
  "facts_source": "ledger.json"
}
```

- `locale` is `en-GB` or `en-US`. `contractions_per_100w`, `never_uses`, `pet_phrases`, `greeting` and `signoff` are what the linter's voice-match check compares against. The rest guides you.
- `never_uses` takes literal strings, including punctuation. Add to it whenever the user flags a phrase as sounding wrong.
- `edit_log` holds one entry per draft the user edited: `{"date": "...", "format": "cover-letter", "changed": "cut 'I believe', joined two sentences, swapped 'keen' for 'pleased'"}`.
- The profile governs how things are said. It never supplies facts. Facts live in `ledger.json` and `profile.json`.
- The file holds the user's private writing. Keep it in `~/.jobferret/` and never inside the skill folder.

### 4.5 Prompting yourself with the profile

Before drafting, assemble a brief and follow it. The brief has five parts (04 §5.5).

- **Show, do not describe.** Put two or three verbatim samples in front of you. Adjectives like "confident, professional" pull straight back to house style.
- **Numeric targets** from the profile: "median sentence about 14 words, at least one under 6, no exclamation marks, 2.5 contractions per 100 words".
- **Locked facts:** "Use only facts from the ledger and the interview. Where a paragraph needs a missing fact, write `[CONFIRM: ...]`."
- **Talk first, tidy second.** Draft the version the user would say to a friend, then adjust the register. Talk-first drafts keep more of the user's phrasing.
- **Reuse their sentences.** A good line from the interview should survive close to verbatim. That is the most honest voice match available, and it is what strict employers require.

Finish with section 6, then ask the user to rewrite at least one sentence in their own words before sending.

### 4.6 Over-imitation and other risks

- **Caricature.** Told that the user says "to be fair", a model will say it in every paragraph. Use each pet phrase at most once per document.
- **Copying mistakes.** Imitate rhythm and word choice. Do not copy typos. Error correction is the part of writing help with measured benefit (04 §2.3).
- **Register mismatch.** A WhatsApp voice is not a cover-letter voice. Take rhythm from informal samples and formality from emails.
- **Drift.** After each draft, diff the user's edits against your version and update the profile. Their edits are the best voice data you will get.
- **Profile as a crutch.** Matching the profile makes a draft sound like the user. It cannot make a vague draft specific. Facts do that.

## 5. Your own fingerprints

JobFerret runs on Claude, so check for Claude's habits and not only ChatGPT's. Graphite's 2026 study of 90,000 articles from nine models found that most tells (65%) belong to one model family and shift between versions (04 §2.1). Claude over-uses "matters because" (about 132 times the human rate), says "the single most" where humans almost never do, likes "less like a ___ and more like a ___" (about 100 times), and scores about 2.5 times human on mannered prose. This is one vendor's study, so treat the numbers as direction, not precision.

- Run `lists/agent-tics.txt` on every draft, in every format, CV bullets included.
- Watch for the habits no list catches: a sentence whose job is to say why the previous sentence was significant; a neat aphorism closing each paragraph; "real" as an intensifier ("real impact"); an even, balanced rhythm from sentence to sentence; a contrast that resolves too tidily.
- Cut any sentence that comments on the writing instead of adding a fact.
- A frozen word list ages fast. "Delve" fell away in 2025 while "quietly", "matters" and "steady" rose. Trust your read of the sentence over the list.
- When the user spots a tell, add it to `never_uses` in their profile.

## 6. Self-review checklist

Run every check, in order, before the user sees the draft (04 §7). Run `ledger_check.py` first when the draft carries `[F...]` markers, then lint the clean copy:

```
python scripts/voice_lint.py draft.md --format cover-letter --profile ~/.jobferret/voice-profile.json
```

The linter exits 0 on pass and 1 on fail, and prints the judgment checks as `manual` items. Show the user the log: one line per check, pass or fix.

| # | Check | Threshold | Who |
|---|---|---|---|
| 1 | **Fact trace.** Every number, name, date and claim maps to the ledger or an interview answer. | Anything else is cut or becomes `[CONFIRM: ...]`. Fail means fix. | You (`ledger_check.py` covers citations on CV text) |
| 2 | **Banned scan** against the banned and agent-tic lists. | Any hit means fix. | `voice_lint.py` |
| 3 | **Rationed count:** three-item lists, dashes, antitheses, colon payoffs, intensifiers, exclamation marks, "I believe", "excited/keen". | More than one of any means cut back. Three or more categories over means rewrite from the facts. | `voice_lint.py` (literals) and you (structural ones) |
| 4 | **Specificity count** of proper nouns, numbers and dates. | Cover letter 6 or more, with one in every paragraph. Email or hiring-manager message 2. Connection note 1. CV profile 3. Form answers 1 per 50 words. | `voice_lint.py` |
| 5 | **Swap test.** Put a competitor's name in. | If the "why us" sentences still hold, rewrite them. | You |
| 6 | **Only-me test.** Point to the sentence no other applicant could have written. | No such sentence means the draft is not ready. | You |
| 7 | **Rhythm,** for anything over 100 words. | One sentence of 6 words or fewer, one of 20 or more, standard deviation of 5 or more, and no run of three sentences within 3 words of each other. Median under 9 means join some up. Paragraph lengths must not all sit within 20% of each other. | `voice_lint.py` |
| 8 | **Ends.** | The first sentence is not about feelings, the act of writing or a pleasantry. The last sentence is an ask, an offer, a plain fact or a sign-off, never a summary. | `voice_lint.py` (openers and closers lists) |
| 9 | **Read-aloud test.** Read it at speaking pace. | Rewrite any sentence this user would stumble on or wince at saying to the hiring manager's face. | You |
| 10 | **Voice match.** | Right spelling locale. Contraction rate within about half of the profile figure, unless the register shift applies. Profile greeting and sign-off. Each pet phrase at most once. Nothing from `never_uses`. | `voice_lint.py` for the measurable parts; you for "sounds like them" |
| 11 | **Formatting and length.** | No bold, headers, emoji, template brackets or bullets outside the CV. Sentence-case subject line. Inside the limit in `format-rules.md`. | `voice_lint.py` |
| 12 | **Agent fingerprints** (section 5). | Zero hits, and your own read for the structural habits. | `voice_lint.py` (`agent-tics.txt`) and you |

Do the judgment checks even when the linter passes. A draft can clear every automated check and still fail 1, 5 or 6, and those three carry the most weight.

## 7. Rewrite or ship

- **Fails 1, 5 or 6:** rewrite the paragraph from the facts. Patching words cannot fix a missing fact, a swappable sentence or an absent personal one.
- **Fails only 2, 3, 11 or 12:** edit in place and re-scan.
- **Fails only 7 or 9:** fix the rhythm and run the checks again.
- **Three or more rationed categories over:** rewrite from the facts instead of editing (check 3).
- **Passes everything:** ship it to the user. Ask them to put at least one sentence into their own words. That improves the voice and makes the "is this your own work?" answer cleaner.
