# Locale: United States (and Canada)

Load when `config.toml` locale is `us`, or the target employer and job are US-based. Source: (03 §2.3, §2.5, §6). Canada broadly follows US layout (Letter, no photo); confirm spelling variety with the user, since Canadian spelling is mixed. If the CV's spelling or page size disagrees with the configured locale, ask which market the user is applying to.

## Document and length

| Item | Rule |
|---|---|
| Name for the document | Résumé or resume. "CV" means a full academic record |
| Paper | US Letter (`cv_render.py --locale us`: Letter, 0.75 in margins, otherwise as UK) |
| Margins | About 0.7 to 1 in; do not go under about 0.6 in (crammed, risks print clipping) |
| Length | 1 page for students and roughly the first 5 to 7 years. 2 pages at about 10+ years. Executives 2 (3 is rare). Academic CV: full record |
| Federal | USAJOBS résumés are longer and highly detailed: hours per week, grade level, supervisor details, duties. Use a different structure; ask the user and offer to build it separately |
| Order | Experienced: contact, summary, skills, Experience, Education. Students and recent graduates: Education first, GPA if 3.5 or higher |
| Format | Reverse-chronological or hybrid; never functional |

Evidence note: the "one page" rule is a norm for early career, not a law. A vendor simulation (ResumeGo, 2018) found reviewers chose two-page versions 2.3 times as often (1.4 times for entry level), but two-page versions had more content and the study sells CV writing (03 §2.3). Do not pad to two pages or cram to one.

## Personal details

**Include:** name, phone, email, city and state, LinkedIn URL, portfolio or GitHub if relevant. Add work authorisation where relevant ("Authorized to work in the US, no sponsorship required" or "OPT, valid to 05/2027, STEM extension eligible").

**Exclude:** photo (equal-opportunity risk; many employers discard them), date of birth, Social Security number, marital status, gender, religion, health, full street address (03 §2.3). Photos also shift callbacks by appearance and gender (03 §2.3).

Never put salary on the résumé; give it in the form field only if mandatory (03 §2.4). Work-authorisation questions are often knock-outs in the application form: answer truthfully (03 §2.2).

## References and photo

- Do not write "References available on request": it is assumed.
- Do not list referees on the résumé. Provide them on request, on a separate page.
- No photo.

## Spelling and terminology

Use American spelling throughout; mixed spelling is a credibility tell (03 §2.5).

| US | UK (avoid on a US résumé) |
|---|---|
| organized, optimized, prioritized, specialized | organised, optimised, prioritised, specialised |
| program | programme |
| center | centre |
| license (noun and verb) | licence (noun) |
| analyze | analyse |
| modeling, labeled | modelling, labelled |
| color, behavior | colour, behaviour |
| résumé / resume | CV |
| college, internship, co-op, high school | university, placement year, sixth form |
| cell phone, vacation, ZIP code | mobile, annual leave, postcode |

The full pair list for the linter is `voice/lists/uk-us-spelling.txt`.

## Education and grades

| Item | Rule |
|---|---|
| Degree | "BS Computer Science, University of Michigan, 2019" with GPA only if 3.5 or higher and early career (e.g. 3.7/4.0) |
| Honours | Dean's List, magna cum laude, summa cum laude, Phi Beta Kappa where applicable |
| Dropping GPA | Drop it after the first few years in work |
| High school | Omit once a degree is held |
| Graduation years | Omitting for age reasons is legitimate if done consistently (03 §2.3) |
| Licenses | CPA, CFA, Bar admission (state and year), nursing license number and state, BLS/ACLS with dates |
| Certifications in progress | "(expected Mar 2027)" |

## Dates and file naming

- Dates as `Mar 2022 – Present`: month and year, en dash with spaces, one format throughout. Label any gap of more than about 6 months in one line (03 §2.3).
- File name `Firstname-Lastname-Resume.pdf`, optionally with the role. Never `resume_final_v3_ACME.docx`. (03 uses `-CV`; in the US the word "resume" is the expected term. This is a judgment call by the skill authors.)
- Send a text-based PDF unless the posting says otherwise. Keep a DOCX twin for Taleo, legacy Workday and agencies (03 §2.2).

## US-specific content notes

- Use a short summary or headline, not an objective (03 §2.4).
- Quantify aggressively: US hiring managers expect numbers (sales attainment, revenue, cost, scale). Use `metric-interview.md`.
- Sales: attainment percentage, rank, President's Club or equivalent. A sales résumé without attainment fails (03 §2.6).
- Healthcare: license number and state, certifications (BLS/ACLS), unit type and ratios.
- Veteran, disability, gender and ethnicity questions on application forms are never filled by the skill (gate G3).
- Cover letters: send when required, optional but the role matters, or when changing career, relocating, explaining a gap (03 §2.8).

## What US recruiters flag

Photo, date of birth, marital status, SSN (03 §2.7); British spelling; A4 layout (prints oddly on Letter); an objective statement; typos (a few cut interview probability by about 7 points; 03 §2.7); clichés and generic summaries; hidden keywords or white text (recruiters and tools catch them; 03 §2.2); unexplained gaps (audit-study and survey evidence of penalties; 03 §2.4); a long résumé for early career; missing work authorisation where it is in doubt.

## Pre-flight checklist (US)

1. Spelling is American throughout (`voice_lint` and `uk-us-spelling.txt` clean), including the summary and skills.
2. Paper US Letter; length 1 page for early career, 2 pages at about 10+ years.
3. Contact line has name, phone, email, city and state, LinkedIn; no street address.
4. No photo, date of birth, SSN, marital status, gender, religion or health.
5. No salary and no "references available on request".
6. Work-authorisation line present if the user's status could be unclear.
7. Education has degree, institution, year; GPA only if 3.5 or higher and early career.
8. Dates are `Mon YYYY – Mon YYYY`, consistent; every gap over about 6 months is labelled.
9. Licenses and certifications (CPA, Bar, RN license, BLS) show number or state where the sector expects them.
10. File named `Firstname-Lastname-Resume[-Role].pdf`, text-extracted and checked; no other employer's name in the text.
