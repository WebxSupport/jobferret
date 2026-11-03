# Sectors quick reference

Distilled from `../research/02-sector-application-playbooks.md` (Part 4 table, standing rules, §1.5, §1.7, §1.9). Cite `(02 §x)` when you rely on it. Most numbers are vendor or self-reported (02 weight tags); treat them as defaults, not laws. **The advert's own instructions always win** over this table (word limits, required documents, "no agencies").

## Contents

1. How to use this table inside `apply`
2. Standing rules
3. Decision table (22 rows)
4. Cover-letter decision
5. Ghost-job signals
6. Screening questions
7. Agencies
8. Where the full playbooks live

## 1. How to use this table inside `apply`

1. **Pick the sector** from the job title, employer and industry in the extracted posting JSON. Mixed cases: use the row whose *application route* matches (an in-house accountant at a charity uses Finance for CV and Charity for the statement). Overlays that can apply on top of any row: Graduate, Career changer, Contractor, Remote-first.
2. **Read off the cover letter** (§4). Required or Statement means write one; Optional means write a short one unless §4 says skip; No means do not generate one.
3. **Set CV length and links** from the CV length and Portfolio columns, within the locale rules in `locale/uk.md` or `locale/us.md`.
4. **Screen dealbreakers.** Compare the Top dealbreakers column and the posting's must-haves against `profile.json` and the ledger. Report each as met, unmet, or unknown, with the evidence. Hard criteria (right to work, licences, registrations, clearance, nationality limits) unmet = recommend skipping and ask the user. Soft criteria (years of experience) = advise, do not auto-skip (02 §1.5).
5. **Check timing and outreach.** If the row says outreach is welcome, offer a short draft note for the user to send (never send). If it says "named contact only" or "events", do not draft cold messages. Dates change yearly: re-read the advert.
6. **Run the ghost-job score** (§5) and screen agencies (§7).
7. Tell the user the sector you chose and why, in one line, so they can correct it.

## 2. Standing rules (02 standing rules)

1. The advert's instructions override this file.
2. Never invent experience, qualifications, right-to-work status or references. Forms are declarations; NHS and Civil Service roles run employment checks.
3. No auto-submit on LinkedIn or Indeed. Prepare materials; the human clicks. Per-platform automation rules in `playbooks/` and `gates-and-limits.md` govern if documents differ.
4. Quality beats volume. Rank roles and recommend; do not spray. Apply within about 7 days of posting to genuine roles matching more than 70% of requirements; never trade tailoring for speed (02 §1.1).

## 3. Decision table (02 Part 4)

02 §2.1–2.21 are 21 sector playbooks; the table has 22 rows because 02 splits §2.10 Education & academia into Teaching and Academia. Timelines are first application to offer [judgment]. "Outreach OK" means you may draft a direct approach for the user to send.

| Sector | Cover letter? | CV length | Portfolio / links | Outreach OK? | Timeline | Top boards | Top dealbreakers |
|---|---|---|---|---|---|---|---|
| Software / IT | Optional | 1 (US) / 1–2 (UK) | GitHub, projects | Yes | 4–8 wks | LinkedIn, company ATS, Wellfound | No right to work; no code evidence |
| Data / AI / ML | Optional; research roles yes | 1–2 | GitHub, papers | Yes | 4–8 wks | LinkedIn, company ATS, lab pages | No SQL / production evidence |
| Product / UX / design | Short | 1 + portfolio | Portfolio essential | Yes | 3–6 wks | LinkedIn, Otta, company ATS | Bloated or locked portfolio |
| Marketing / comms / creative | Yes | 2 | Work samples | Yes | 3–6 wks | LinkedIn, Indeed, The Drum | Typos; vague metrics |
| Sales / BD | Optional | 2 | LinkedIn, numbers | Yes, encouraged | 2–5 wks | LinkedIn, agencies, Wellfound | Unquantified quota; spam |
| Finance / accounting | Forms; rarely a letter | 1 (grad) / 2 | LinkedIn | Agencies; events for grads | 4–8 wks; grad 2–4 mths | Employer sites, LinkedIn, eFinancialCareers | Missed deadline; failed tests; qualification overstated |
| Legal | Forms or letter | 2 UK / 1 US | No | Events; agencies for laterals | TC 3–6 mths | Firm sites, Legal Cheek, LinkedIn | Wrong firm name; application limits |
| Healthcare / NHS | No; statement mandatory | Form | No | Informal contact only | 6–12 wks | NHS Jobs, trust sites | Missing essential criterion; gaps |
| Civil Service / public | Statement + behaviours | 2 + form | No | Contact point only | 6–12 wks + vetting | Civil Service Jobs, council sites | Over limit; "we"; nationality rules |
| Teaching | Application letter | 2 | No | Visit head | Jan–May peak | Teaching Vacancies, TES, Eteach | Missed resignation date |
| Academia | Statement / cover letter | Academic CV | Publications | PI / supervisor yes | 2–8 mths | jobs.ac.uk, HigherEdJobs | Missing statements; wrong deadlines |
| Engineering | Optional | 2 | Project list | Moderate | 4–8 wks | LinkedIn, Indeed, institutions | Registration / clearance unclear |
| Trades / logistics | No | 1 | Cards / tickets | Phone / visit | 2–14 days | Indeed, Find a Job, agencies | Expired card / licence |
| Hospitality / retail | No | 1 | No | In person (small employers) | 1–3 wks | Indeed, employer sites, Caterer.com | No availability |
| Executive | Statement to pack | 2–3 | Board bio | Search firms | 3–6 mths | Search firms, LinkedIn | Mass mailing; vague impact |
| Graduate | Form answers | 1 | LinkedIn | Events | 2–4 mths | TARGETjobs, Bright Network | Missed deadlines; tests |
| Career changer | Yes | 1–2 | Projects / certs | Yes (info chats) | 3–6+ mths | Target-sector boards | No proof of skill |
| Contractor (UK) | Covering email | 2 | Client list | Agencies | Days–2 wks | Jobserve, CWJobs, LinkedIn | Wrong IR35 / rate; double submission |
| Remote-first | Yes | 1–2 | Writing samples | Yes, short | 3–6 wks | LinkedIn, WWR, Wellfound | Time-zone / country mismatch |
| Management consulting | Short motivation statement where asked | 1 (grad) / 2 (exp.) | No | Alumni chats; referrals | Grad 2–4 mths; exp. 4–8 wks | Firm portals, Bright Network, LinkedIn | Failed online test; wrong office; rejection lock |
| Charity / third sector | Statement vs person spec (mandatory) | 2 | Volunteering / trustee roles | Informal contact OK | 3–8 wks | CharityJob, Guardian Jobs, Third Sector | Generic statement; no values evidence |
| Pharma / biotech / regulated | Optional; R&D yes | 2 (+ publications) | Publications / patents | Recruiters; managers (experienced) | 6–12 wks | PharmiWeb, LinkedIn, agencies / CROs | Vague GxP claims; status overstated |

Row-specific cautions worth carrying into `apply`:
- **NHS, Civil Service, charity, local government:** the supporting statement is the scored application. Map it to the person specification or Success Profile behaviours, one real example per criterion, STAR, "I" not "we", within the word limit. Draft only from the user's real examples (02 §2.8, 2.9, 2.20). Portals are usually `assist` tier.
- **Graduate, finance, consulting, legal:** online tests and application limits matter; a failed test can lock you out 6–12 months. Never apply twice to barred divisions or offices (02 §2.6, 2.7, 2.19).
- **Teaching:** England teacher resignation deadlines are 31 Oct, 28 Feb and 31 May; check which is next against today's date (02 §2.10).
- **Contractor:** state IR35 stance and day rate from `profile.json`; one agency per client (02 §2.17).
- **Remote-first:** state time zone and right to work at the top; many "remote" roles are country-restricted (02 §2.18).

## 4. Cover-letter decision (02 §1.4)

| Table says | Do |
|---|---|
| Yes / Required / Statement / Application letter | Write one. 250–350 words (statements: to the limit, mapped to the person spec). Tailored, two facts only true of this employer, two evidenced achievements. |
| Optional | Write 150–250 words if any of: career change, gap, relocation, small employer, writing-heavy or startup role, user asks. Otherwise skip. Skip for high-volume hourly, trades and most engineering roles. |
| Short | 150–250 words tied to one product or brand observation. |
| Forms / Form answers | No letter; write the form answers (`voice_lint --format form-answer`). |
| Covering email | 3–5 lines: availability, rate or salary bracket, right to work. |
| No | None; at most a one-line message with availability and cards or licences. |

Every letter stays within 150–400 words, the range `voice_lint.py --format cover-letter` accepts; the targets above sit inside it. A posting's own word limit overrides both.

Never generic or visibly AI-templated: about 20% of surveyed hiring managers would reject AI-generated materials (02 §1.4). Every claim carries a ledger citation (G4).

## 5. Ghost-job signals (02 §1.7)

Prevalence is large: Greenhouse put it at 18–22% of 2024 US postings and up to 34% of UK roles never actively recruited (02 §1.7). Score each posting as **low / medium / high** ghost risk by counting signals present; 0–1 low, 2 medium, 3 or more high. Show the signals, not a number. Judgment, not measured.

Signals:
1. Posted or refreshed more than 30 days ago, or reposted with identical content.
2. No company name ("our client"), or recruiter/agency advert with no client.
3. No salary **and** generic requirements.
4. Not on the employer's own careers page or ATS (check via the public feeds in `playbooks/`).
5. No named hiring manager, team or contact.
6. Recent layoffs or a hiring freeze reported by the company.
7. Salary band absurdly wide, or title/level mismatched with the duties.

High risk: tell the user before spending effort; prefer roles on the employer's own page.

**Scam flags** (stop and warn; never proceed): pay-to-apply or "training fees" (UK agencies cannot charge work-seekers for finding work, Conduct Regulations reg. 10); WhatsApp/Telegram-only contact; free-email recruiter address; instant offer without interview; cheque for equipment; ID or bank details requested before an offer.

## 6. Screening questions (02 §1.5)

- **Knockouts** ("X years of Y?", "authorised to work?", "notice period?"): answer truthfully. Years-of-experience is soft; right to work, licences and certifications (CSCS, GMC, SRA, Driver CPC, clearance) are hard.
- **Work authorisation:** state the exact status. "Will you now or in future require sponsorship?" is yes if it ever applies. Never guess.
- **Salary:** see `gates-and-limits.md` §8. Anchor in the advertised range; blank or "Negotiable" when optional; never volunteer current salary.
- **"Why us?":** 3–5 sentences: one specific company fact, one link to the user's evidence, one forward-looking line. No "passionate about".
- **Diversity monitoring and EEO:** voluntary; never infer protected characteristics; leave to the user (G3). Disability Confident: flag the scheme, never tick.
- **AI-use declarations and policies:** the user answers. JobFerret proposes truthful wording in the review package and never fills the field.
- Unknowns go to the user, with an offer to save the answer to the answer bank.

## 7. Agencies

(02 §1.9) Agencies are paid by employers; they cannot charge you for finding work.

- **Right to represent (RTR):** permission for one agency to submit you to a named client for a named role. Clients generally honour the first documented submission, and a direct application can outrank a later agency one. Agencies need your permission before sending your CV to a client (REC).
- **Rules for `apply`:** keep a log (agency, recruiter, client, role, date, written permission). No client name, no permission. Grant RTR per role, in writing, never blanket. Check the user has not applied directly or via another agency to the same client before any submission. Never let two agencies submit the same person to the same firm.
- **Speculative adverts:** ask for the client and role confirmation before sending the full CV; send a short CV without address or DOB (02 §1.7 CV-fishing note).
- **CV for agencies:** .docx or ATS-parsable PDF, two pages, plain headings; notice period and salary bracket in the email, not on the page.
- If a role appears both on an agency advert and on the employer's own ATS, apply direct only if the user has not already given an agency RTR for it.

## 8. Where the full playbooks live

The full per-sector playbooks (where posted, what the CV leads with, process quirks, outreach, timing, pitfalls, UK/US/EU differences) are in `../research/02-sector-application-playbooks.md` (Part 2 §2.1–2.21, Part 3 outreach norms) until they are distilled into this skill. Read the relevant §2.x section when the user applies in a sector whose row above leaves a question open, and cite it `(02 §2.x)`. Do not copy long passages into the user's documents.
