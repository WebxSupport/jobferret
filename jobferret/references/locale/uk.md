# Locale: United Kingdom (and Ireland)

Load when `config.toml` locale is `uk`, or the target employer and job are UK-based. Source: (03 §2.3, §2.5, §6). Ireland follows the same conventions in practice; confirm with the user. If the CV's spelling or page size disagrees with the configured locale, ask which market the user is applying to.

## Document and length

| Item | Rule |
|---|---|
| Name for the document | CV (résumé is the US word; "CV" in the UK is the normal job-application document) |
| Paper | A4 (`cv_render.py --locale uk`: A4, 2 cm margins, Calibri 10.5, name 18 bold) |
| Margins | 1.8 to 2.5 cm; below about 1.5 cm looks crammed and may clip on printing |
| Length | 2 pages maximum. 1 page is acceptable early career. 3 for senior, academic or executive. Two pages are not penalised when earned (03 §2.3) |
| Order | Experienced: contact, profile, core skills, Experience, Education, Certifications, Projects. Graduates and recent graduates: Education first |
| Format | Reverse-chronological or hybrid; never functional |

Evidence note: the UK 2-page norm is consensus from university careers services and councils (Manchester, Birmingham City Council), not an experiment (03 §2.3). The one study on length (ResumeGo) is a US vendor simulation. Say "convention" rather than "proven".

## Personal details

**Include:** name, phone, email (a professional firstname.lastname address), town or city (or "London, open to hybrid"), LinkedIn URL, portfolio or GitHub if relevant. Add a right-to-work line where it may be in doubt: "Full UK right to work, no sponsorship required" or "Graduate visa valid to 08/2027".

**Exclude:** photo, date of birth or age, marital status, nationality (except as right to work), full postal address, National Insurance number, gender, religion, health (03 §2.3). Photos also shift callbacks by appearance and gender (03 §2.3, Ruffle and Shtudiner 2015).

Never put salary on the CV. Put it in the form field only if the form requires it (03 §2.4).

## References and photo

- Drop "References available on request": it is assumed in the UK.
- Do not list referees on the CV. Collect them in the application form if asked.
- No photo, ever, unless the user insists for a specific reason. Then warn them once.

## Spelling and terminology

Use British spelling throughout. Mixed spelling is a credibility tell (03 §2.5).

| UK | US (avoid on a UK CV) |
|---|---|
| organised, optimised, prioritised, specialised | organized, optimized, prioritized, specialized |
| programme (but "computer program") | program |
| centre | center |
| licence (noun), license (verb) | license |
| analyse | analyze |
| modelling, labelled | modeling, labeled |
| colour, behaviour | color, behavior |
| CV | résumé |
| university, sixth form, placement year or sandwich year | college, high school, internship or co-op |
| mobile, annual leave, postcode | cell, vacation, zip code |

The full pair list for the linter is `voice/lists/uk-us-spelling.txt`.

## Education and grades

| Item | Rule |
|---|---|
| Degree | Give classification and institution: "BSc Computer Science (2:1), University of Manchester, 2016 – 2019". Classes: First, 2:1, 2:2, Third |
| A-levels | Early career only (e.g. "A*AA"). Drop after the first couple of years in work |
| GCSEs | Only if the employer asks, or maths and English are a stated requirement |
| Predicted grades | Label "predicted" for current students |
| Graduation years | Omitting for age reasons is legitimate if done consistently (03 §2.3) |
| Professional bodies | ACA, ACCA, CIMA, SRA admission and PQE, NMC/GMC/HCPC numbers: show the registration number under the name or in a Certifications line |

## Dates and file naming

- Dates as `Mar 2022 – Present`: month and year, en dash with spaces, one format throughout. Years alone suggest hidden gaps except for roles over 15 years old (03 §2.3).
- Label any gap of more than about 6 months in one line (03 §2.3).
- File name `Firstname-Lastname-CV.pdf`, optionally `Firstname-Lastname-CV-Role.pdf`. Never `CV_final_v3_ACME.docx`.
- Send a text-based PDF unless the posting says otherwise. Keep a DOCX twin for Taleo, legacy Workday and agencies (03 §2.2). `cv_render.py` produces both.

## UK public sector (statement decides)

- **NHS:** the application form plus the supporting information, written against the person specification, does most of the work. Include band, ward or service type and registration (03 §2.6).
- **Civil Service:** CVs are often anonymised and sometimes read only after behaviours are scored. Behaviour examples are usually 250 words each; personal statements commonly 750 to 1,250 words per the advert. Assessors stop reading at the limit. Pitch examples to the grade (03 §2.6, §2.8).
- Statements are structured by the person specification's criteria in order, one STAR example per criterion, "I" not "we". These are separate documents from the CV; offer to draft them.

## What UK recruiters flag

Photo, date of birth, marital status, NI number, full address (03 §2.7); US spelling; Letter-size layout; "References available on request"; unexplained gaps; objective statements; clichés; typos (a few errors cut interview probability by about 7 points; 03 §2.7); right-to-work absent where doubtful.

## Pre-flight checklist (UK)

1. Spelling is British throughout (`voice_lint` and `uk-us-spelling.txt` clean), including the profile and skills.
2. Paper A4, margins at least 1.8 cm; length 2 pages or fewer unless the user is senior or academic.
3. Contact line has name, phone, professional email, town or city and LinkedIn; no postal address.
4. No photo, date of birth, age, marital status, NI number, nationality (unless as right to work), gender, religion or health.
5. No salary and no "references available on request".
6. Right-to-work line present if the user's status may be unclear to the employer.
7. Degree has classification and years; A-levels only if early career; GCSEs only if requested.
8. Dates are `Mon YYYY – Mon YYYY`, consistent; every gap over about 6 months is labelled.
9. Registrations, tickets or PINs (NMC, SRA, ACA, CSCS, Gas Safe) are shown where the sector expects them.
10. File named `Firstname-Lastname-CV[-Role].pdf`, text-extracted and checked; no other employer's name in the text.
