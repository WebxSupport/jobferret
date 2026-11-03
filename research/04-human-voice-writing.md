# Writing applications that sound like the candidate

Reference for JobFerret. Read it before drafting anything a recruiter or hiring manager will see, and run section 7 on every draft before the user sees it.

Researched 2 November 2026. Labels: **[evidence]** has a measurement behind it, linked. **[judgment]** is my call from the sources and from how hiring works. **[folklore]** is widely repeated and weakly supported, or true once and stale now.

One rule sits above the rest. **Every fact in a draft comes from the user.** The examples in section 6 use invented people and fictional companies to show technique. In real use, if a detail isn't in the user's fact sheet, ask for it or leave it out. A specific detail that turns out to be made up is far worse than a vague one.

---

## 1. TL;DR: the 15 rules

Ranked by how much each changes whether a reader believes a person wrote the thing.

| # | Rule | Confidence |
|---|---|---|
| 1 | Use only facts the user gave you. Never invent a number, name, project or feeling. | High. Employers treat invention as misconduct ([Civil Service](https://www.gov.scot/publications/recruitment-candidate-guide/pages/use-of-ai-tools/), [Anthropic](https://www.anthropic.com/candidate-ai-guidance)). |
| 2 | Put a checkable detail in every paragraph: a named system, number, date, place or person. | High. Generic, unverifiable claims are the most cited tell ([Wikipedia](https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing), recruiter commentary). |
| 3 | Include one sentence no other applicant could write. | High [judgment]. |
| 4 | Swap test: if the "why this company" part still works with a competitor's name in it, rewrite it. | High. Cheap tailoring has lost its signal value ([Galdin & Silbert 2025](https://arxiv.org/abs/2511.08785)). |
| 5 | Open with substance, never with the writer's feelings or the act of writing. | High. |
| 6 | Zero hits on the banned list (section 4). | Medium-high. The words are measured, but the list drifts as models change. |
| 7 | Ration the stock structures: three-item lists, "not X but Y", setup-colon-payoff, "matters because", the recap paragraph. One of each per document at most. | Medium-high ([Graphite 2026](https://graphite.io/research/ai-tells), Wikipedia). |
| 8 | End on a concrete next step or a plain sign-off. Never a summary. | Medium. |
| 9 | Vary sentence length and include a short one. Don't overcorrect into all-short. | Medium. |
| 10 | Prefer verbs to nouns and cut trailing "-ing" clauses. | Medium ([Reinhart et al. 2025](https://arxiv.org/abs/2410.16107)). |
| 11 | Learn the voice from the user's real writing, not from adjectives like "warm but professional". | Medium ([Wang et al. 2025](https://arxiv.org/abs/2509.14543)). |
| 12 | Keep the user's locale. British spelling, idiom and understatement for UK roles. | High. |
| 13 | No bold, headers, bullet lists, emoji or template signature blocks in letters and messages. | High. |
| 14 | Ignore detector scores. Write for a tired recruiter who uses ChatGPT daily and can smell it. | High ([Russell et al. 2025](https://aclanthology.org/2025.acl-long.267)). |
| 15 | Follow the employer's AI policy and answer "did you use AI?" truthfully. | High. |

---

## 2. Evidence review

### 2.1 What marks text as AI-written

**Lexical tells are real, and they move.** [Kobak et al. (Science Advances, 2025)](https://arxiv.org/abs/2406.07016) tracked word frequencies across 15 million PubMed abstracts and found a surge in style words after ChatGPT: *delves*, *showcasing*, *underscores*, *crucial*. They estimate at least 13.5% of 2024 abstracts went through an LLM [evidence]. [Liang et al. (Patterns, 2025)](https://arxiv.org/abs/2502.09747) found LLM-assisted text in up to 10–15% of job postings from small, young firms by late 2024, so employers do it too [evidence]. [Juzek & Ward (COLING 2025)](https://arxiv.org/abs/2412.11385) found mixed evidence that preference tuning causes the overuse.

The list changes with each model generation. [Wikipedia's "Signs of AI writing"](https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing) is the best practical tracker. GPT-4-era text leaned on *delve, tapestry, testament, pivotal, intricate, meticulous*. GPT-4o moved to *align with, enhance, fostering, showcasing*. The newest models add *leverage, multifaceted, prioritize, dependable, steady, quietly, matters*, while "delve" fell away in 2025 [evidence, community-curated]. A list frozen in 2024 is already half wrong.

[Graphite's September 2026 study](https://graphite.io/research/ai-tells) compared 90,000 articles from nine models with 10,000 pre-ChatGPT human articles. Most tells (65%) belong to one model family and shift between versions. GPT overuses "not simply" (157× the human rate) and "matters because" (357×). **Claude**, which JobFerret runs on, overuses "matters because" (132×), says "the single most" where humans almost never do, likes "less like a ___ and more like a ___" (about 100×), and scores about 2.5× human on mannered prose [evidence; one vendor study]. The agent has to watch its own family's habits, not just ChatGPT's.

**Structural tells.** Wikipedia lists the rule of three, negative parallelism ("not just X, but also Y", "Y rather than X"), inflated significance, trailing "-ing" clauses that add unearned importance, bold-lead-in bullets, title case headings, emoji and chatbot pleasantries [evidence, observational]. [Reinhart et al. (PNAS, 2025)](https://arxiv.org/abs/2410.16107) found instruction-tuned models write a noun-heavy style, with nominalisations at about 1.5–2× the human rate and far more present participial clauses [evidence]. That's "the implementation of a streamlined process, ensuring alignment across teams" where a person writes "I changed how we booked jobs".

What recruiters actually describe is sameness. An agency director told [LeadDev](https://leaddev.com/hiring/cover-letters-used-to-mean-something) that about 40 of every 50 cover letters read as machine-written: "Same wording, same structure, same 'I am excited to apply' tone" [anecdote]. [Agarwal et al. (CHI 2025)](https://arxiv.org/abs/2409.11360) showed AI suggestions pulling Indian writers towards American style [evidence]. For a UK user, the drift sounds like "I'm thrilled" and "reach out".

**Statistical tells.** Perplexity is how predictable each word is to a language model, and AI text scores low. Burstiness is how much that varies between sentences. People write a flat sentence, then an odd one, then a short one. Models hold steady. GPTZero built its first detector on these signals and now uses them as one input among several ([GPTZero](https://gptzero.me/news/perplexity-and-burstiness-what-is-it/)) [evidence]. Uniform sentence length sounds mechanical to people too. But Wikipedia notes the newest models have swung to short 8–20-word sentences, so an all-short draft is now its own tell. Aim for variance.

**Em dashes, the meme and the data.** The em dash was a real ChatGPT habit, with one widely cited comparison putting GPT-4.1 at about three times the human rate [evidence, secondary]. Vendors then suppressed it. Wikipedia dates the tell "2022–September 2026", and Graphite found GPT and Gemini now use fewer dashes than humans, with Claude near the human rate [evidence]. On its own, in 2026, the dash is [folklore]. Ration it to one per document anyway, because the reader has heard the meme. If the user's samples are full of dashes, follow the user.

**What isn't a tell.** Wikipedia calls perfect grammar, formal prose, a lone "Additionally" and curly quotes weak evidence. [Jakesch et al. (PNAS, 2023)](https://pmc.ncbi.nlm.nih.gov/articles/PMC10089155) found people judge text as human when it has first-person pronouns, contractions and family topics. Models fake those easily, and 4,600 participants did no better than chance on AI-written self-presentations, including job profiles [evidence]. Adding "I" and "don't" doesn't make a draft human. A real detail from the user does.

### 2.2 Detection and how far to trust it

- OpenAI withdrew its own classifier in July 2023 for its "low rate of accuracy". It caught 26% of AI text and flagged 9% of human text ([OpenAI](https://openai.com/blog/new-ai-classifier-for-indicating-ai-written-text/)) [evidence].
- [Liang et al. (2023)](https://arxiv.org/abs/2304.02819) found seven detectors labelled more than half of non-native writers' TOEFL essays as AI (61%, per [Stanford HAI](https://hai.stanford.edu/news/ai-detectors-biased-against-non-native-english-writers)), with 97% flagged by at least one [evidence]. Plain, low-variety English gets flagged.
- Vendors claim about 99% accuracy and false positives at or under 1% ([GPTZero](https://gptzero.me/news/ai-accuracy-benchmarking)). Independent figures are lower and vary widely [thin evidence; mostly vendor-adjacent blogs].
- [Russell et al. (ACL 2025)](https://aclanthology.org/2025.acl-long.267) found that people who use LLMs heavily for writing are excellent detectors. Five of them, voting, got 299 of 300 articles right and beat every automatic detector, including on "humanised" text. Non-users did badly and were overconfident [evidence].

**Do employers run detectors on applications?** Some do. [Unleash](https://www.unleash.ai/artificial-intelligence/news/greenhouse-25-of-hiring-managers-use-ai-to-screen-applicants-yet-8-are-unsure-what-the-ai-prioritizes) reports Greenhouse's November 2025 survey (4,136 people in the US, UK, Ireland and Germany) as finding 61% of US and 59% of European hiring managers use software to detect AI in applications. That figure isn't in [Greenhouse's own release](https://www.greenhouse.com/newsroom/an-ai-trust-crisis-70-of-hiring-managers-trust-ai-to-make-faster-and-better-hiring-decisions-only-8-of-job-seekers-call-it-fair), which says 65% of US hiring managers have caught deceptive AI use and 22% have found hidden prompt injections in CVs [release: evidence; 61%: unverified]. I couldn't confirm any major ATS that documents an AI-authorship score [thin evidence].

So don't try to beat detectors. "Humaniser" tools make text worse, and Russell et al.'s experts caught humanised text anyway. The reader who counts is a recruiter with 140 applications per vacancy (the UK graduate average in the [ISE 2025 survey](https://ise.org.uk/_userfiles/pages/files/reports/student_recruitment_survey_2025.pdf)) who probably uses ChatGPT at work. Write so that person believes a specific human wrote it.

### 2.3 What recruiters and hiring managers say

**Usage is near-universal.** Greenhouse found 74% of US job seekers use AI and 41% admitted trying prompt injection [evidence, vendor survey]. LinkedIn reported about 11,000 applications a minute in mid-2025, up 45% on the year ([eWeek, citing the NYT](https://www.eweek.com/news/ai-job-applications-linkedin/)).

**Few reject AI use outright. They reject obvious, generic AI.** In [TopResume's May 2025 survey](https://topresume.com/career-advice/ai-in-hiring-survey) of 600 US hiring managers, 19.6% would reject an AI-generated CV or cover letter, and 52% accept AI help with proofreading or drafting if the final product is the person's own. In the same survey's test, 33.5% picked out the AI-written CV; if they were choosing one from four, guessing gets 25%. [CV Genius (2024)](https://cvgenius.com/blog/career-advice/ai-for-job-application) reports 80% view obviously AI-generated applications negatively and 74% claim they can spot them, naming "dynamic landscape", "fostering" and sentences that keep starting with "By…" [self-report]. The [ISE](https://educationbusinessuk.net/node/10667) found about half of UK early-careers employers worry AI misrepresents candidates' abilities.

The gap between "74% can spot it" and test results near chance is telling. Recruiters can't reliably detect polished AI text. They can detect generic text, and they assume generic means AI. The fix is the same either way.

**Outcome evidence.**

- [Wiles, Munyikwa & Horton (Management Science, 2025)](https://pubsonline.informs.org/doi/10.1287/mnsc.2024.04528): in a field experiment with nearly 500,000 jobseekers, writing assistance on CVs raised hiring by about 8% with no drop in employer satisfaction. The gain came from fewer spelling and grammar errors and went mostly to weaker writers [evidence]. This was error correction, not generated content, so it supports polishing and says nothing for generating claims.
- [Galdin & Silbert (2025)](https://arxiv.org/abs/2511.08785), on Freelancer.com: employers paid a premium for tailored proposals before LLMs. Once tailoring became cheap the premium vanished, and their model predicts less meritocratic hiring [evidence, working paper]. "I admire your mission" carries no signal now. Specifics that cost something do: a product the candidate actually used, a real conversation, a real result.
- A Tilburg study in [ESB (2026)](https://ioplus.nl/en/posts/ai-improves-cover-letters-not-hiring-chances), with recruiters from Philips, PwC, VodafoneZiggo and Rabobank: AI-assisted letters scored higher, mainly on the generic opening and closing, but won no more interviews. The motivation section, which recruiters weigh most, barely changed. [Earlier reporting](https://universonline.nl/nieuws/2025/02/19/chatgpt-in-job-applications-is-using-ai-the-key-to-success-or-a-pitfall/) says recruiters were at chance identifying AI letters, and a related thesis found letters were marked down once ChatGPT was suspected [evidence for the main result; thinner for the penalty].

Put together, AI polish doesn't win interviews, generic text loses the motivation argument, and suspicion costs points. I found no rigorous study showing generic AI letters directly cause rejection. The suspicion penalty is the nearest thing [thin evidence].

**Employer policies vary.** Anthropic told candidates in early 2025 not to use AI assistants at all ([Fortune](https://fortune.com/2025/02/04/anthropic-tells-job-candidates-dont-use-ai-employer-trend)). Its current [candidate AI guidance](https://www.anthropic.com/candidate-ai-guidance) says write the first draft yourself, use Claude to refine it, never invent experience, and keep live interviews "all you". The UK Civil Service [allows AI](https://www.civil-service-careers.gov.uk/artificial-intelligence-in-recruitment) for research, structure and clarity, but bans invented or inflated experience and pasted generic answers. Statements must be "truthful, factually accurate and taken directly from your own experience" ([PublicTechnology](https://www.publictechnology.net/2025/10/31/education-and-skills/what-new-civil-service-guidance-on-ai-for-job-applicants-tells-us-about-shifts-in-recruitment/)). [DWP](https://dwpjobs-eorecruitment-microsite.co.uk/process-overview) and the [Scottish Government](https://www.gov.scot/publications/recruitment-candidate-guide/pages/use-of-ai-tools/) treat AI content presented as your own as plagiarism and withdraw the application. NHS rules are set by each trust. [Bolton](https://boltonft.nhs.uk/join-our-team/use-of-artificial-intelligence-ai-when-writing-job-applications) discourages relying on AI for supporting statements, some trusts ask for disclosure, and one [trust guide](https://static.trac.jobs/docs-employer/854/2971/Applicants%20Guide%20to%20the%20Use%20of%20Generative%20AI%20in%20%20Applications.pdf) won't reject for AI help alone but may withdraw an application that doesn't match the person's real experience.

### 2.4 What human applicant writing has

Pre-LLM writing advice works as an anti-AI checklist, because models are trained towards the average and good writing has always moved away from it.

- **Checkable details.** Model text drifts to "generic, positive, important-sounding prose" (Wikipedia). People write "Power BI", "March 2024", "£38,000". Alison Green has long argued a cover letter should add what the CV can't and show rather than assert ([Ask a Manager](https://www.askamanager.org/2018/05/how-to-write-a-great-cover-letter.html)) [judgment].
- **One story** beats any number of asserted qualities.
- **Talk-like phrasing.** Paul Graham's test: would you say this sentence to a friend? ([Write Like You Talk](https://paulgraham.com/talk.html); [Write Simply](https://paulgraham.com/simply.html)). Orwell's rules still hold ([Politics and the English Language](https://www.orwellfoundation.com/the-orwell-foundation/orwell/essays-and-other-works/politics-and-the-english-language/)).
- **Plain English.** The [GOV.UK A to Z](https://guidance.publishing.service.gov.uk/writing-to-gov-uk-standards/style-guides/a-to-z-style-guide/) bans much of the LLM vocabulary (*leverage, robust, foster, facilitate, streamline, empower, utilise, key, going forward*) and flags sentences over 25 words. It prefers "cannot" to "can't", a useful register cue for Civil Service forms [judgment].
- **Admitting a limit.** "I haven't managed a budget this size" reads as human because models default to relentless positivity.
- **A direct ask**, such as "Could we talk on Thursday?"
- **No wrap-up.** People stop when they've finished.
- **Regional understatement.** A British writer says "it went fine".

On Strunk & White: "omit needless words" is good, but much of their grammar advice is wrong ([Pullum](https://www.chronicle.com/article/50-years-of-stupid-grammar-advice/)), and real people use the passive. Hemingway-style cutting helps until everything is short.

---

## 3. The tells: a catalogue

### Lexical

| Tell | Example | Fix |
|---|---|---|
| AI vocabulary | "leverage my robust skill set to foster collaboration" | Say what happened, in plain verbs. |
| Feelings as openers | "I am thrilled / excited / passionate…" | Delete. Show interest through a detail. |
| Self-labels | "results-driven, detail-oriented team player" | Replace with the result. |
| Puffery | "pivotal role", "a testament to" | State the role and what changed. |
| Copula avoidance | "serves as", "boasts" | Use "is" and "has". |
| Vague attribution | "industry experts agree" | Name the source or cut it. |
| Claude's own tics | "matters because", "the single most", "less like X and more like Y", "quietly", "genuinely" | Cut on sight. |

### Structural

| Tell | Example | Fix |
|---|---|---|
| Tricolon | "creative, analytical and collaborative" | Keep one quality and prove it. |
| Negative parallelism | "It's not just about data, it's about people." | Keep only the second half. |
| Setup-colon-payoff | "The result: a 30% drop." | "Errors fell by 30%." |
| Trailing "-ing" clause | "…, ensuring seamless delivery for stakeholders." | Cut, or give it its own sentence with a fact. |
| Nominalisation | "the implementation of process improvements" | "I changed how we…" |
| Connector chains | "Moreover… Furthermore… Additionally…" | Delete. Order carries the logic. |
| Recap ending | "In conclusion, my skills make me an ideal fit." | End on the ask. |
| Mirror paragraphs | Every paragraph is claim, example, link to role | Let one paragraph be two sentences. |
| Challenge-then-triumph | "Despite challenges, I successfully…" | Say what went wrong and what you did. |

### Rhythmic

| Tell | Example | Fix |
|---|---|---|
| Uniform sentences | Five sentences of 18–22 words | Make one four words long. Let one run to 30. |
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
| Bold lead-in bullets | "**Leadership:** Led a team of…" | Prose in letters and messages. Bullets belong on the CV. |
| Headers in an email | "Why I'm a fit" | Remove. |
| Title Case subject | "Exciting Opportunity To Connect" | "Data analyst role (ref 4471)". |
| Emoji | "🚀 Excited to connect!" | None. |
| Template signature | "[Your Name] [Your Title]" | Name, phone, one link. Never leave a bracket in. |
| Dash doing a comma's job | "My work — focused on impact — has…" | Commas, or two sentences. |

---

## 4. Banned and rationed list

Case-insensitive, matched on stems ("leverag" catches leveraged and leveraging). A hit means fix before the user sees it. Literal uses are exempt ("landscape gardener", "navigate" in a satnav job).

### Never use: words

```
delve
tapestry
testament
realm
multifaceted
robust
seamless
pivotal
crucial
foster
underscore
leverag
landscape (figurative)
navigat (figurative)
synerg
spearhead
cutting-edge
game-chang
innovative
dynamic (about yourself)
passionate
thrilled
meticulous
intricate
vibrant
bolster
garner
showcas
highlighting
enhance
elevate
unlock
empower
holistic
paradigm
ever-evolving
fast-paced
harness
embark
journey (career sense)
resonat
invaluable
transformative
utilis
utiliz
facilitat
streamlin
quietly
nestled
honed
adept
proactive
```

### Never use: phrases

```
i am writing to express my interest
i am writing to apply
i am excited to apply
i was excited to see
i hope this email finds you well
i hope this message finds you well
i hope you are doing well
in today's fast-paced world
in today's competitive
proven track record
results-driven
detail-oriented
team player
hit the ground running
think outside the box
wear many hats
unique blend of
aligns with my values
align perfectly
deeply resonates
i am confident that i would be
i believe i would be a great fit
ideal candidate
i would welcome the opportunity
thank you for your time and consideration
please do not hesitate to contact me
rest assured
it is worth noting
it's important to note
plays a vital role
serves as a testament
at the end of the day
in conclusion
to summarise
overall,
moreover
furthermore
additionally,
matters because
the single most
less like a
not simply
not just about
circle back
touch base
add value
make an impact
```

### Rationed: at most once per document

```
a list of exactly three items (adjectives, nouns or clauses)
a dash used as punctuation (em dash or spaced en dash)
a "not X, but Y" / "it's not X, it's Y" / "X rather than Y" antithesis
a colon that sets up a punchline
an intensifier: really, very, truly, genuinely, incredibly, extremely
a rhetorical question (zero in formal forms)
an exclamation mark (zero in cover letters and forms)
"i believe" / "i feel"
"excited" / "keen" / "eager"
"look forward to"
"reach out" (prefer "get in touch")
"dear hiring manager" (only if no name can be found)
a semicolon in a message under 150 words
```

### Openers to avoid

Anything starting with the writer's emotions, the act of writing, the job title read back, or a pleasantry: "I am writing…", "I'm excited…", "As a [adjective] professional…", "With X years of experience…", "Hi! I hope…", "My name is…", "I came across your profile and was impressed…", "Are you looking for…?"

### Closers to avoid

"In conclusion…", "Overall…", "Thank you for your time and consideration", "I look forward to discussing how I can contribute to your team's success", "Please don't hesitate…", "Let me know if you have any questions!", and any final paragraph that restates the letter.

---

## 5. Voice-capture protocol

The aim is a short profile plus real samples, so the model writes like this user and not like a model's idea of a professional.

### 5.1 Samples (at least three, ideally five)

1. Two or three **work emails** they wrote themselves, ideally including one where they pushed back or explained a problem.
2. Anything they wrote for a job **before 2023**, such as an old cover letter or application answer.
3. An **informal message** (Slack, Teams or WhatsApp, names redacted) for rhythm and humour.
4. A **LinkedIn post**, with caution, since LinkedIn has its own house style and may already be AI-assisted.
5. A **voice-note transcript** of two minutes answering one interview question. Spoken phrasing is the most "them" material you'll get.

Drop any sample an AI helped with.

### 5.2 The interview (eight questions)

Ask one at a time and keep their exact words. The answers become both the fact sheet and voice material.

1. What piece of work from the last two years would you most like a stranger to know about? What was the problem, what did you do, and what number changed?
2. Tell me about something that went wrong at work and what you did next.
3. What are you properly good at that never makes it onto your CV?
4. Why this role and this organisation, in the words you'd use down the pub? Have you used their product, met their people or read something of theirs?
5. What would a former manager say is the annoying thing about working with you?
6. What part of this job haven't you done yet, and how would you handle it?
7. Which words do you hate seeing in applications, and which do you overuse?
8. How do you open and sign off emails?

For public-sector forms, add: "Give me two examples for each behaviour on the advert, with dates and numbers."

### 5.3 Idiolect markers to extract

Measure, don't guess:

- **Sentence length**: median and standard deviation in words.
- **Contractions** per 100 words.
- **Locale**: -ise/-ize, "CV" or "résumé", date format, words like "rota", "sorted", "Mum".
- **Greeting and sign-off**, exactly as written.
- **Pet phrases**: anything used twice or more across samples.
- **Never-used words**: if they never write "passionate", neither does the agent.
- **Formality** (1–5), judged from emails rather than old cover letters, which are already stiff.
- **Humour** (none, dry, self-deprecating), with one example.
- **Punctuation habits**: dashes, brackets, semicolons, exclamation marks per 100 words.
- **Hedging**: "I think" and "probably", or flat statements.

### 5.4 Profile schema

```json
{
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
  "samples": ["<verbatim 1>", "<verbatim 2>", "<verbatim 3>"],
  "facts_file": "facts.json"
}
```

Keep facts in a separate `facts.json` (employers, dates, numbers, stories in the user's own words). The profile governs how things are said and must never supply facts.

### 5.5 Prompting with the profile

- **Show, don't describe.** Put two or three verbatim samples in the prompt. [Wang et al. (EMNLP Findings 2025)](https://arxiv.org/abs/2509.14543) found models imitate everyday writers poorly from descriptions and better from examples, though still imperfectly, especially in informal writing [evidence]. Adjectives like "confident, professional" pull straight back to house style.
- **Give numeric targets** from the profile: "median sentence about 14 words, at least one under 6, no exclamation marks".
- **Lock the facts**: "Use only facts from FACTS. Where a paragraph needs a missing fact, write [ASK: …]."
- **Talk first, tidy second.** Ask for the version the user would say to a friend, then adjust register. Talk-first drafts keep more of the user's phrasing.
- **Reuse their sentences.** A good line from the interview should survive close to verbatim. That's the most honest voice match available, and it's what strict employers require.
- **Run section 7**, then ask the user to rewrite at least one sentence in their own words before sending.

### 5.6 Risks

- **Caricature.** Told the user says "to be fair", the model will say it in every paragraph. Cap pet phrases at one per document.
- **Copying mistakes.** Imitate rhythm and word choice, not typos. Error correction helps (Wiles et al.).
- **Register mismatch.** WhatsApp voice isn't cover-letter voice. Take rhythm from informal samples and formality from emails.
- **Drift.** Diff the user's edits to each draft and update the profile. Their edits are the best voice data you'll get.

---

## 6. Format rules and before/after pairs

The examples use invented people and fictional organisations (Calder Valley Homes, Ferncroft Energy, Lumen Tickets). Every specific in an "after" stands for something the user must supply.

### 6.1 Cover letter

250–400 words in three to five paragraphs of uneven length. The spine is what I've done (with a number), why you specifically (something unswappable), and what happens next. Open on the strongest fact. No bullets. Name the reader if you can find them, otherwise "Dear Hiring Manager" is fine. Don't restate the CV.

**Opening**

> Before: I am writing to express my interest in the Data Analyst position at Ferncroft Energy. As a passionate, results-driven professional with a proven track record of leveraging data, I am excited to contribute to your innovative team.

> After: Last year I got the average wait on our empty homes down from 41 days to 29, mostly by building one dashboard and persuading fourteen housing officers to open it on Monday mornings. Your advert mentions a smart-meter fault backlog, which sounds like the same kind of problem.

Cut: the writing-about-writing opener and six banned phrases. Added: a number, a timeframe, a link to the advert.

**Why us**

> Before: Ferncroft's commitment to sustainability deeply resonates with me, and I am inspired by your mission to transform the energy landscape.

> After: I've been a Ferncroft customer since 2023. When my meter stopped sending readings last winter it took three calls to fix, and the third person told me the fault list was "still a spreadsheet". I'd like to be the one who sorts that spreadsheet out.

Cut: "commitment to", "deeply resonates", "transform the energy landscape". Passes the swap test.

**Evidence**

> Before: I possess strong analytical skills, excellent communication and keen attention to detail. Moreover, I have experience in stakeholder management, data visualisation and process improvement, ensuring seamless delivery.

> After: The work I'm proudest of was dull. Reconciling contractor invoices against completed jobs in 2024, I found 212 duplicates worth £38,000. Finance had missed them because the two systems used different property codes. I wrote the matching rules down, and the check now runs monthly without me.

Cut: two tricolons, "Moreover", "seamless", the trailing "-ing" clause. Added: a short sentence, figures, a year, a plain cause.

**Close**

> Before: In conclusion, my unique blend of skills makes me an ideal candidate. I would welcome the opportunity to discuss how I can contribute. Thank you for your time and consideration.

> After: I'm free for a call any weekday after 4pm, and happy to walk you through the dashboard with the tenant data taken out.
>
> Yours sincerely,
> Sam Adeyemi

Cut: the recap and four banned phrases. Added: a specific offer.

### 6.2 Recruiter cold email

Under 120 words. A subject line naming the role or the reason, in sentence case. A first line saying why them. One proof point, one ask, a plain sign-off, and a link rather than an attachment.

**Subject lines**

> Before: "Exciting Opportunity: Passionate Data Professional Seeking New Challenges!" / "Quick Question"

> After: "Data analyst, housing and energy background (Leeds)" / "Your Ferncroft data analyst role" / "Referred by Priya Shah"

Cut: Title Case, exclamation mark, self-labels, vague hooks.

**Opening line**

> Before: Hi Hannah, I hope this email finds you well! I came across your profile and was really impressed by your extensive experience in the energy sector.

> After: Hi Hannah, you posted the Ferncroft data analyst role on Tuesday, so I'm guessing it's yours to fill.

Cut: pleasantry, exclamation mark, generic flattery.

**Full email**

> Before: I am a highly motivated data professional with five years of experience leveraging analytics. I believe I would be a valuable asset to any organisation and would love to explore potential opportunities. Please find my CV attached!

> After: Hi Hannah, you posted the Ferncroft data analyst role on Tuesday, so I'm guessing it's yours to fill.
>
> I'm a data analyst at Calder Valley Homes in Halifax. Short version: I built the dashboard that cut our empty-home wait from 41 to 29 days, and found £38k of duplicate invoices along the way.
>
> I've applied through the site. Would a 10-minute call this week help you decide whether to put me forward?
>
> Thanks,
> Sam
> 07700 900123 · linkedin.com/in/samadeyemi

Cut: "highly motivated", "leveraging", "valuable asset to any organisation" (which fails the swap test by its own wording), the attachment. About 75 words.

**The ask**

> Before: Please do not hesitate to reach out if there are any roles that may potentially be a good fit for my background.

> After: Are you hiring for anything in data or reporting in the next couple of months? If not, no need to reply.

Cut: "do not hesitate", "reach out", "may potentially". Added: an easy yes or no.

### 6.3 LinkedIn connection note (300 characters)

Under 300 characters including spaces. How you know of them and why you're connecting. No pitch, no CV, no "pick your brain".

**Recruiter**

> Before: Hi Hannah! I'm a passionate data professional excited to connect with like-minded individuals in the energy space. I'd love to explore synergies! 🚀

> After: Hi Hannah, I applied for the Ferncroft data analyst role this week. Connecting so you've got a face to the name. I'm in Leeds and can come in any day. (151 characters)

**Hiring manager, after their post**

> Before: Hi Tom, I really enjoyed your insightful post about data quality. It truly resonated with me. I'd love to connect and learn more about your journey!

> After: Hi Tom, your post about meter reads arriving with the wrong timestamps made me laugh. We had the same thing with repair dates. I'm applying for your analyst role and wanted to say hello first. (196 characters)

**Through a contact**

> Before: Hello! I noticed we have mutual connections and would be delighted to expand my professional network with someone of your calibre.

> After: Hi Jo, Priya Shah suggested I get in touch. She said you moved from housing data to Ferncroft last year, and I'm trying to do the same. (139 characters)

**After an event**

> Before: Great to meet you at the event! Looking forward to staying connected and collaborating in the future.

> After: Hi Amir, we talked at the Leeds Data Meetup on Thursday about whether Power BI is worth the licence fee. Still thinking about your answer. (143 characters)

Cut across all four: "passionate", "excited", "synergies", "insightful", "resonated", "journey", emoji, exclamation marks, generic networking language. Added: the post's actual content, a named referrer, the event and day.

### 6.4 Hiring-manager message

60–150 words, sent after applying, not instead of it. Lead with something specific to their team, give one result, ask one easy question.

**After applying**

> Before: I recently applied for the Data Analyst role and wanted to reach out to express my strong enthusiasm. I am confident my skills make me an excellent fit for your team.

> After: I applied for your data analyst role yesterday. One thing my CV doesn't show: I've spent two years getting people who hate spreadsheets to use a dashboard, which I suspect counts for as much as the SQL in your team.

**A question about the role**

> Before: Could you please provide some additional insight into the key responsibilities and day-to-day expectations of the role?

> After: Is the fault-backlog work mostly reporting, or would the analyst be fixing the data at source as well?

**Replying to their post**

> Before: Fantastic post, Tom! This is such an important topic and you've articulated it brilliantly. Data quality is truly the foundation of everything.

> After: Your point about timestamps is the bit nobody budgets for. We lost about a month of repair dates when a contractor changed time zones in their export. Did you fix it upstream or clean it on your side?

**Referral**

> Before: I was referred to you by a mutual connection who believes I would be a valuable addition to your organisation.

> After: Priya Shah, who worked with me at Calder Valley until March, said you were the person to ask about the analyst role. She's happy to vouch for me.

Cut across all four: "reach out", "strong enthusiasm", "excellent fit", "additional insight", "key responsibilities", "articulated it brilliantly", "truly", a truism, "valuable addition". Added: something the CV can't say, a question only an advert-reader would ask, a matching story, a named referrer with dates.

### 6.5 CV profile

Three or four lines, 40–70 words. Dropping "I" is the UK convention, though either works. What you do, one or two lines of proof, what you're after. If it could go on a colleague's CV unchanged, rewrite it.

**Data analyst**

> Before: Results-driven data analyst with a proven track record of leveraging cutting-edge tools to deliver actionable insights. Passionate about data storytelling and adept at collaborating with cross-functional stakeholders in fast-paced environments.

> After: Data analyst at a 6,000-home housing association. Built the repairs dashboard that cut empty-home turnaround from 41 to 29 days, and found £38k in duplicate contractor invoices. Power BI, SQL, Excel. Looking for a larger dataset and a team where analysts fix data at source.

**Nurse moving into operations**

> Before: Compassionate and dedicated healthcare professional with extensive experience in fast-paced clinical settings, seeking to leverage transferable skills in a dynamic operational role.

> After: Band 6 ward sister, eight years in acute medicine on a 30-bed ward. Ran the ward rota for three years and cut agency shifts from 40 a month to 12. Moving into NHS operations or patient-flow management.

**Bootcamp developer**

> Before: Motivated junior software engineer with a strong foundation in modern web technologies, eager to contribute to innovative projects within a collaborative team.

> After: Junior developer, formerly a retail manager. Since a 16-week bootcamp in 2025 I've built and kept running a booking app for my sister's dog-grooming business (React, Node, about 90 bookings a month). Want a team that does code review properly.

**Operations director**

> Before: Strategic and visionary operations leader with a holistic approach to driving transformational change and fostering high-performing teams across complex, multifaceted organisations.

> After: Operations director, logistics. Ran three warehouses (420 staff) through the 2024 move to a new warehouse system without missing a peak-season dispatch. Better at fixing broken processes than inventing new ones.

Cut across all four: self-labels, "proven track record", "leverage", "cutting-edge", "passionate", "adept", "fast-paced", "dynamic", "innovative", "holistic", "fostering", "multifaceted". Each "after" has numbers, a setting and an aim.

### 6.6 Application-form answers

Answer the question asked, in the order asked. Use the employer's criterion wording once so the shortlister can tick it off. In UK public-sector forms use STAR order with most words on Action, and "I" rather than "we". Labels are optional and prose usually reads better [judgment]. Drop most contractions in Civil Service and NHS forms to match the register. Civil Service behaviour answers are commonly capped at 250 words; check the advert.

**UK Civil Service behaviour, "Delivering at Pace" (250 words, STAR)**

> Before (excerpt): I spearheaded a transformative initiative to streamline our void management process, leveraging data-driven insights to foster collaboration across stakeholders. Moreover, I proactively identified key bottlenecks and implemented robust solutions, which serves as a testament to my commitment to excellence.

> After (242 words): In April 2024, 63 homes at Calder Valley Homes were empty and waiting for repairs, and the average wait before re-letting was 41 days. Every empty week cost about £95 in lost rent, and families on our waiting list were in temporary accommodation. My manager asked me to find where the time was going and bring the average down within six months.
>
> I matched a year of job records from our housing and repairs systems, which used different property codes. The repairs themselves were not the main delay. Homes waited an average of nine days for the first inspection to be booked, because requests went to a shared inbox that nobody owned. The repairs manager and I agreed inspections would be booked within two working days, with one named person responsible.
>
> I built a Power BI dashboard listing every empty home by days waiting, oldest first. I ran four half-hour sessions so all 14 housing officers could use it, and every Monday I went through it with the repairs manager and chased any home over 20 days. When the contractor's data feed failed in July, I updated the figures by hand for three weeks so the Monday meeting kept going.
>
> By October the average wait was 29 days, and it has stayed under 31 since. If I did it again, I would fix the inspection booking first and build the dashboard second, because that is where most of the time came from.

Cut: eleven banned words and phrases and the self-assessment. Added: dates, numbers, the named tool, what the candidate personally did, a setback and an honest reflection. Contractions dropped for register.

**NHS supporting statement paragraph** (criterion: "Experience of analysing and presenting data to improve services")

> Before: I have extensive experience in analysing and presenting data to improve services. I am passionate about using data to drive meaningful change and enhance patient outcomes, and I am adept at presenting complex information to stakeholders in a clear and concise manner.

> After: Experience of analysing and presenting data to improve services. At Calder Valley Homes I produce the weekly performance pack for the senior leadership team and five area managers. In 2024 I analysed a year of repairs data and found that most of the delay in re-letting empty homes came from inspection booking, not the repairs. I presented this to the repairs manager on a one-page chart, we changed the booking process, and the average wait fell from 41 to 29 days. I have not worked with patient data yet. The closest is tenant vulnerability data, which taught me to handle sensitive records under UK GDPR and to check who really needs to see what.

Cut: "extensive experience", "passionate", "drive meaningful change", "enhance", "adept", "clear and concise manner". Added: the criterion as a signpost, an honest gap and how it's bridged.

**"Why do you want to work for us?"**

> Before: Lumen Tickets is an industry leader known for its innovative approach and customer-centric values. I am drawn to your dynamic culture, and this role represents the perfect opportunity to grow my career while making a meaningful contribution.

> After: I've bought tickets through Lumen for about thirty gigs, and twice the queue page told me I was "number 1" for ten minutes before kicking me out. Your engineering blog post from June explained why: the queue counter and the payment service disagree under load. My current job is mostly reconciling two systems that disagree about the same houses. I'd like to do it somewhere a few seconds matter, and where I can see the result as a customer.

Cut: "industry leader", "innovative", "customer-centric", "dynamic culture", "perfect opportunity", "meaningful contribution". Added: first-hand experience nobody else has. (The blog post must be real and the user must have read it.)

**"Tell us about a mistake you made"**

> Before: While I strive for excellence in all that I do, I once encountered a challenge where a minor oversight occurred. I took full ownership, learned valuable lessons, and now ensure meticulous attention to detail.

> After: In my first month I sent the board pack with last year's arrears figures in one table. A board member spotted it in the meeting. I owned up that afternoon, sent a corrected page within the hour, and added a check that compares every table's date stamp before anything goes out. It hasn't happened since, but I still check that table by eye.

Cut: "strive for excellence", "encountered a challenge", a tricolon of virtues, "meticulous". The mistake is named, and so is the fix.

### 6.7 Follow-up email

40–90 words, in the same thread. One new fact or one clear question. Wait 7–10 working days after applying, or a day or two past any date they gave.

**No response after applying**

> Before: I just wanted to follow up on my application and reiterate my strong interest in the position. I remain very excited about the opportunity and would love to hear about next steps!

> After: Hi Hannah, I applied for the data analyst role on 14 October. Since then our dashboard has gone live in a second region, so the 41-to-29-day figure now covers 9,000 homes. Is the role still open?

**After interview, past their date**

> Before: I hope you are well. I wanted to touch base regarding the status of my candidacy following our recent interview.

> After: Hi Tom, you mentioned you'd decide by Friday, so I'm checking whether there's any news. Still very keen.

**Asking for feedback after rejection**

> Before: Although I am disappointed, I would greatly appreciate any feedback you could provide to help me grow and develop professionally.

> After: Thanks for letting me know, Tom. If you have two minutes, it would help to know whether it came down to experience or the case study. I'd like to apply again next time you hire.

**A recruiter who went quiet**

> Before: Just circling back on my previous email. Please let me know if there is any additional information I can provide!

> After: Hi Hannah, I've now got an offer elsewhere with a deadline of 7 November. Ferncroft is still my first choice, so I wanted you to know before I decide.

Cut across all four: "reiterate", "strong interest", "excited", "touch base", "candidacy", "grow and develop", "circling back", exclamation marks. Each "after" carries a date or a new fact. (Use the last one only if the offer is real.)

### 6.8 Thank-you note after interview

50–120 words, same or next working day. Refer to one specific moment and add anything you'd answer better now. Thank-you notes are less expected in the UK than in the US, so keep it short, and skip it for formal anonymised panels such as Civil Service boards [judgment].

**Opening**

> Before: Thank you so much for taking the time to meet with me today. I truly enjoyed learning more about the role and your amazing team!

> After: Thanks for this morning, Tom. I hadn't realised how much of the backlog comes from the old Elster meters.

**Middle**

> Before: Our conversation further solidified my enthusiasm for the position, and I am more confident than ever that my skills align perfectly with your needs.

> After: I gave you a vague answer on the timestamp problem. A better one: I'd start by counting how many reads arrive out of order each day, before anyone fixes anything, so we know whether it's 2% or 20%.

**Close**

> Before: I look forward to hearing from you regarding next steps. Please don't hesitate to contact me should you require any further information.

> After: Either way, good luck with the migration in January.

**Full note after an informal chat**

> Before: Dear Jo, I wanted to extend my heartfelt thanks for taking the time out of your busy schedule to speak with me. Your insights were incredibly valuable as I navigate the next steps in my career journey.

> After: Hi Jo, thanks for the half hour yesterday. Your tip about asking for the fault-list data in the interview worked. I did, and Tom said he'd send a sample. I owe you a coffee next time you're in Leeds.
>
> Sam

Cut across all four: "so much", "truly", "amazing", "solidified my enthusiasm", "align perfectly", "don't hesitate", "heartfelt", "incredibly valuable", "navigate", "career journey". Each "after" refers to one real moment.

---

## 7. Self-review checklist

Run on every draft, in order, before the user sees it. Log the results so the user can see what was checked.

1. **Fact trace.** Every number, name, date and claim maps to the fact sheet or the user's interview answers. Anything else is cut or becomes `[ASK: …]`. *Fail = must fix.*
2. **Banned scan.** Grep against section 4's never-use lists. *Any hit = fix.*
3. **Rationed count.** Three-item lists, dashes, antitheses, colon payoffs, intensifiers, exclamation marks, "I believe", "excited/keen". *More than one of any = cut back. Three or more categories over = rewrite from the facts instead of editing.*
4. **Specificity count** (proper nouns, numbers, dates). Cover letter at least 6, with one in every paragraph. Cold email or hiring-manager message at least 2. Connection note at least 1. CV profile at least 3. Form answers at least 1 per 50 words.
5. **Swap test.** Put a competitor's name in. If the "why us" sentences still hold, rewrite them.
6. **Only-me test.** Point to the sentence no other applicant could have written. If there isn't one, the draft isn't ready.
7. **Rhythm.** For anything over 100 words: at least one sentence of 6 words or fewer, one of 20 or more, a standard deviation of at least 5 words, and no run of three sentences within 3 words of each other in length. If the median is under 9 words, join some up. Paragraph lengths must not all sit within 20% of each other.
8. **Ends.** The first sentence isn't about feelings, the act of writing, or a pleasantry. The last sentence is an ask, an offer, a plain fact or a sign-off, never a summary.
9. **Read-aloud test.** Read it at speaking pace. Would this user say each sentence to the hiring manager's face? Rewrite any sentence they'd stumble on or wince at.
10. **Voice match.** Correct spelling locale. Contraction rate within about half of the profile figure, unless the register shift applies. Profile greeting and sign-off. Each pet phrase at most once. Nothing from `never_uses`.
11. **Formatting.** No bold, headers, emoji, template brackets, or bullets outside the CV. Subject line in sentence case. Within the word or character limit.
12. **Agent fingerprints.** A last pass for this model's own habits: "matters because", "the single most", "less like… more like", "quietly", "genuinely", "here's the thing", "real" as an intensifier, and any sentence that explains why the previous sentence was significant.

**Rewrite or ship?** Fails 1, 5 or 6: rewrite the paragraph from the facts rather than patching words. Fails only 2, 3, 11 or 12: edit in place and re-scan. Fails only 7 or 9: fix the rhythm and re-run. Passes everything: ship it, and ask the user to put at least one sentence into their own words. That improves the voice and makes the "is this your own work?" answer cleaner.

---

## 8. Disclosure guidance

**Check the policy first.** Before drafting for a specific employer, look for an AI policy in the advert, careers page and form, and tell the user what it says in one line.

**Where the employer bans AI-written content** or calls it plagiarism (the Civil Service, some NHS trusts, any form with a "no AI" checkbox), switch to coach mode. Run the interview, help the user choose examples and put them in STAR order, and let them write the draft in their own words. Then give feedback: missing criteria, word count, vague sentences. Point at problems instead of rewriting them. Fix spelling and grammar where proofreading is allowed, which it usually is ([Civil Service](https://www.gov.scot/publications/recruitment-candidate-guide/pages/use-of-ai-tools/), [Anthropic](https://www.anthropic.com/candidate-ai-guidance)). Don't produce full answers to paste, and tell the user why: the Civil Service withdraws applications for it, and Anthropic and others ask for the candidate's own first draft.

**Where the employer says nothing**, recruiter surveys suggest AI help with drafting and polishing is broadly accepted if the content is true and the person's own ([TopResume](https://topresume.com/career-advice/ai-in-hiring-survey): 52%). The voice-capture process is what keeps the content theirs.

**"Did you use AI in this application?"** Answer truthfully. Suggested wording, adjusted to what actually happened:

- Light help: "Yes. I used an AI tool to check spelling and grammar and tighten the wording. The examples and content are my own."
- Drafting help: "Yes. I used an AI assistant to structure and draft from my notes, then edited it myself. Every example and figure is mine and I'm happy to talk through any of them."
- None: "No."

Never advise ticking "No" when the answer is yes. Getting caught misstating it is worse than any AI penalty, and Civil Service and NHS guidance both treat misrepresentation as grounds for withdrawal or later dismissal.

**Interviews and assessments.** No live AI help unless the employer explicitly allows it. Take-home tasks follow the employer's instructions. If it's unclear, the user should ask.

**Prompt injection.** Never hide text in a CV or letter (white-on-white keywords, "ignore previous instructions"). Greenhouse found 22% of US hiring managers have caught it, and it reads as deception.

---

## 9. Sources

Corpus and style research
- Wikipedia, [Signs of AI writing](https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing) (WikiProject AI Cleanup), read November 2026
- Kobak et al. (2025), [Delving into LLM-assisted writing in biomedical publications through excess vocabulary](https://arxiv.org/abs/2406.07016), Science Advances; [data and code](https://github.com/berenslab/llm-excess-vocab)
- Liang et al. (2025), [The widespread adoption of LLM-assisted writing across society](https://arxiv.org/abs/2502.09747), Patterns
- Juzek & Ward (2025), [Why does ChatGPT "delve" so much?](https://arxiv.org/abs/2412.11385), COLING
- Reinhart et al. (2025), [Do LLMs write like humans?](https://arxiv.org/abs/2410.16107), PNAS
- Graphite (September 2026), [AI Tells](https://graphite.io/research/ai-tells)
- Agarwal, Naaman & Vashistha (2025), [AI suggestions homogenize writing toward Western styles](https://arxiv.org/abs/2409.11360), CHI
- Wang et al. (2025), [Catch Me If You Can? Not Yet](https://arxiv.org/abs/2509.14543), EMNLP Findings
- Jakesch, Hancock & Naaman (2023), [Human heuristics for AI-generated language are flawed](https://pmc.ncbi.nlm.nih.gov/articles/PMC10089155), PNAS

Detection
- GPTZero, [Perplexity and burstiness](https://gptzero.me/news/perplexity-and-burstiness-what-is-it/); [AI detection benchmarking](https://gptzero.me/news/ai-accuracy-benchmarking)
- OpenAI (2023), [New AI classifier for indicating AI-written text](https://openai.com/blog/new-ai-classifier-for-indicating-ai-written-text/) (with withdrawal note)
- Liang et al. (2023), [GPT detectors are biased against non-native English writers](https://arxiv.org/abs/2304.02819); [Stanford HAI summary](https://hai.stanford.edu/news/ai-detectors-biased-against-non-native-english-writers)
- Russell, Karpinska & Iyyer (2025), [People who frequently use ChatGPT for writing tasks are accurate and robust detectors of AI-generated text](https://aclanthology.org/2025.acl-long.267), ACL

Hiring evidence and surveys
- Wiles, Munyikwa & Horton (2025), [Algorithmic writing assistance on jobseekers' resumes increases hires](https://pubsonline.informs.org/doi/10.1287/mnsc.2024.04528), Management Science; [NBER version](https://www.nber.org/papers/w30886)
- Galdin & Silbert (2025), [Making Talk Cheap: Generative AI and Labor Market Signaling](https://arxiv.org/abs/2511.08785)
- IO+ (2026), [AI improves cover letters, not hiring chances](https://ioplus.nl/en/posts/ai-improves-cover-letters-not-hiring-chances); Univers (2025), [ChatGPT in job applications](https://universonline.nl/nieuws/2025/02/19/chatgpt-in-job-applications-is-using-ai-the-key-to-success-or-a-pitfall/)
- Greenhouse (November 2025), [2025 AI in Hiring report release](https://www.greenhouse.com/newsroom/an-ai-trust-crisis-70-of-hiring-managers-trust-ai-to-make-faster-and-better-hiring-decisions-only-8-of-job-seekers-call-it-fair); [Unleash coverage](https://www.unleash.ai/artificial-intelligence/news/greenhouse-25-of-hiring-managers-use-ai-to-screen-applicants-yet-8-are-unsure-what-the-ai-prioritizes)
- TopResume (June 2025), [Where employers draw the line on AI in hiring](https://topresume.com/career-advice/ai-in-hiring-survey)
- CV Genius (2024), [AI for job applications](https://cvgenius.com/blog/career-advice/ai-for-job-application)
- LeadDev (December 2025), [Cover letters used to mean something](https://leaddev.com/hiring/cover-letters-used-to-mean-something)
- eWeek (2025), [LinkedIn applications at 11,000 a minute](https://www.eweek.com/news/ai-job-applications-linkedin/)
- Institute of Student Employers, [Student Recruitment Survey 2025](https://ise.org.uk/_userfiles/pages/files/reports/student_recruitment_survey_2025.pdf); [Education Business coverage](https://educationbusinessuk.net/node/10667)

Employer AI policies
- Anthropic, [Candidate AI guidance](https://www.anthropic.com/candidate-ai-guidance); [Fortune (February 2025)](https://fortune.com/2025/02/04/anthropic-tells-job-candidates-dont-use-ai-employer-trend)
- UK Civil Service, [AI in recruitment](https://www.civil-service-careers.gov.uk/artificial-intelligence-in-recruitment); [PublicTechnology (October 2025)](https://www.publictechnology.net/2025/10/31/education-and-skills/what-new-civil-service-guidance-on-ai-for-job-applicants-tells-us-about-shifts-in-recruitment/); [Scottish Government candidate guide](https://www.gov.scot/publications/recruitment-candidate-guide/pages/use-of-ai-tools/); [DWP process overview](https://dwpjobs-eorecruitment-microsite.co.uk/process-overview)
- NHS: [Bolton NHS FT](https://boltonft.nhs.uk/join-our-team/use-of-artificial-intelligence-ai-when-writing-job-applications); [NHS trust applicant guide to generative AI](https://static.trac.jobs/docs-employer/854/2971/Applicants%20Guide%20to%20the%20Use%20of%20Generative%20AI%20in%20%20Applications.pdf)

Writing guidance
- Paul Graham, [Write Like You Talk](https://paulgraham.com/talk.html) (2015); [Write Simply](https://paulgraham.com/simply.html) (2021)
- George Orwell, [Politics and the English Language](https://www.orwellfoundation.com/the-orwell-foundation/orwell/essays-and-other-works/politics-and-the-english-language/) (1946)
- GOV.UK, [A to Z style guide](https://guidance.publishing.service.gov.uk/writing-to-gov-uk-standards/style-guides/a-to-z-style-guide/)
- Geoffrey Pullum, [50 Years of Stupid Grammar Advice](https://www.chronicle.com/article/50-years-of-stupid-grammar-advice/) (2009)
- Alison Green, Ask a Manager, [How to write a great cover letter](https://www.askamanager.org/2018/05/how-to-write-a-great-cover-letter.html)
