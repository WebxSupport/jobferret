# Sector Application Playbooks (reference for the JobFerret agent)

Compiled 2026-11-02. Audience: an AI agent deciding *how* to apply for a given role. Owner is probably UK-based ("CV"); rules cover UK, US and EU.

## How to read this file

Weight tags on every claim:

- **[evidence]** – linked dataset, official guidance or named survey. Most hiring "data" comes from vendors (ATS makers, CV builders, outreach tools) with something to sell, so check sample bias.
- **[evidence-lite]** – real source but secondary, vendor-run, self-reported or only seen via a search summary.
- **[judgment]** – my synthesis; sensible default, unproven.
- **[folklore]** – repeated career-blog advice with no traceable primary data. Tiebreaker only.
- **[stale]** – pre-2024, or dates conflict.

Limits: my search tool was US-centric; several primary pages (NHS Jobs, Civil Service Careers, Ask a Manager) returned HTTP 403, so they are cited via search summaries or trust/department guidance. UK/EU quantitative data is thinner than US. Dates change yearly; re-read every advert.

**Standing rules (apply before any sector rule):**

1. **RULE:** The advert's instructions override this file (word limits, required documents, "no agencies").
2. **RULE:** Never invent experience, qualifications, right-to-work status or references. Forms are declarations; NHS and Civil Service roles run employment checks.
3. **RULE:** Do not auto-submit via LinkedIn. LinkedIn says members using automation software [risk restriction or shutdown](https://www.linkedin.com/help/linkedin/answer/a1341387) [evidence]. Prepare materials; the human clicks submit. This rule is **platform-specific**: before automating anything on any platform (LinkedIn, Indeed, ATS portals, email), check the per-platform automation policy in `01-landscape-and-architecture.md`, which governs if the two documents ever differ.
4. **RULE:** Quality beats volume (data below). Rank roles and recommend; do not spray.

---

# PART 1 – UNIVERSAL RULES

## 1.1 Timing

- **Apply early, but "early" means days.** The "first 24–96 hours = up to 8x interview odds, decaying 28% a day" claim traces to blog reposts of Talent.Works/Ladders-style studies; I could not find the dataset [folklore, e.g. [TopResume](https://topresume.com/career-advice/the-early-bird-gets-the-job-the-best-time-to-submit-your-resume)]. Recruiters in an [Ask a Manager thread](https://www.askamanager.org/2025/08/does-it-really-matter-if-you-apply-within-the-first-hour-of-a-job-being-posted.html) say the first applicants are often weak and 500 can arrive in 72 hours; the site's view is first week or two beats week five [evidence-lite].
- Pipelines are slow, and Huntr reports two different measures that must not be conflated ([Huntr 2025](https://huntr.co/research/2025-annual-job-search-trends-report); self-reported, tech-skewed) [evidence-lite]. (a) *Per application that reaches interview*: mean ~5.6 days from application to first interview. This only counts the lucky applications, so it understates real waits. (b) *Per job seeker*: median 23 days until their first interview, with the 75th percentile above two months and the 90th above four months; the report does not state the start point (likely search start). Also: median 12 days interview-to-offer and median 57–83 days to first offer (Q1–Q4 2025). I rechecked the page: the figures are a mean for one population and a median for another, not swapped. Hours rarely matter; weeks often do.
- Day-of-week / time-of-day effects: no credible primary data found [folklore]. Do not delay a good application for a "golden hour".
- **Early genuinely matters** for rolling graduate/vacation schemes, NHS/Civil Service roles that close on volume, seasonal retail, and small employers with one recruiter [judgment].
- **Posting lifespan:** a crawl analysis suggests median live time ~20–30 days, a quarter still up at ~59 [evidence-lite]. Time to fill: Employ 2025 gives [63.5 days posting-to-accepted-offer and 257.6 applications per job (207.2 in 2024)](https://www.hrdive.com/news/hiring-benchmarks-report-employ-2025-more-applicants/809604/) [evidence]; UK ~4.9 weeks average, ~6 public sector, ~5.9 banking ([StandOut CV survey via NatWest Mentor](https://www.natwestmentor.co.uk/news/time-to-hire-in-the-uk)) [evidence-lite].
- **Seasons** [judgment]: Jan–Mar and Sep–Nov strongest; late Dec and August (UK/EU) slowest. Teaching and graduate cycles are fixed calendars (see sectors).
- **Agent rule:** apply within ~7 days of posting for genuine roles matching >70% of requirements; never trade tailoring for speed.

## 1.2 Volume vs quality

| Metric | Figure | Source |
|---|---|---|
| Applications per job (US ATS) | 257.6 (2025) vs 207.2 (2024) | [Employ/HR Dive](https://www.hrdive.com/news/hiring-benchmarks-report-employ-2025-more-applicants/809604/) [evidence] |
| Growth in applications per job | +102%, Q3 2022–Q4 2024 | [Greenhouse](https://www.greenhouse.com/newsroom/greenhouse-launches-dream-job-to-fix-job-hunting-and-boost-candidates-chances-of-getting-hired) [evidence] |
| UK graduate vacancies | 140 applications each (2024–25); 141 (2025–26), 172 in London | [ISE](https://ise.org.uk/knowledge/insights/492/apprenticeships_rise_as_graduate_vacancies_drop_8), [Wonkhe](https://wonkhe.com/wonk-corner/a-slightly-better-outlook-for-graduate-jobs) [evidence] |
| UK student hires per application | ~31,000 from ~1.8m (~1.7%, my arithmetic) | [ISE report](https://ise.org.uk/_userfiles/pages/files/reports/student_recruitment_survey_2025.pdf) [judgment] |
| Tailored vs untailored CV | 5.8% vs 3.73% reach interview/offer/hire | [Huntr](https://huntr.co/research/2025-annual-job-search-trends-report) [evidence-lite] |
| Interview rate by CV length | 2 pp 3.24%; 1 pp 3.06%; 3 pp 2.6%; 4+ pp 2.12% | Huntr [evidence-lite] |
| Response by site | Google Jobs 11.3%, GovernmentJobs 8.7%, Wellfound 6.0%, Glassdoor 5.5%, Indeed 4.5%, LinkedIn 3.1%, ZipRecruiter 2.8% | Huntr, 598k applications [evidence-lite] |
| Applications before offer | ~38% of successful seekers within 30; ~18% needed 100+ | Huntr [evidence-lite] |
| Volume vs hit rate (Q2 2026) | 8.1% interview rate (11–20 applications) vs 2.9% (100+) | [Huntr Q2 2026](https://huntr.co/research/job-search-trends-q2-2026) [evidence-lite] |

**Interpretation** [judgment]: plan on roughly 20–40 tailored applications per offer for a mainstream professional role (more in tech and early-career); cold-apply interview rates sit around 3–6%. Heavy volume correlates with lower per-application success, though causation is unclear.

**By channel:**

- Cold apply ~3% reach interview; referral ~40%, yet referrals are only ~1% of applications. Referred interviewees get offers at 16% vs 6% inbound (Ashby, 38m+ applications, 2021–24) [evidence: [Ashby](https://www.ashbyhq.com/talent-trends-report/reports/referrals)]. The 4x/7x/10x "hire multipliers" elsewhere are vendor claims with differing denominators [folklore].
- Recruiter-initiated LinkedIn messages get ~17% replies (vendor logs: [Pin](https://www.pin.com/blog/recruiting-outreach-benchmark-report/), [Noon](https://www.noon.ai/blog/articles/189-candidate-reply-rate-benchmarks-2026)) [evidence-lite]. That is employer-to-candidate, not the reverse.
- Candidate cold email to a hiring manager: "15–25% vs 2–5% for portals" comes from an outreach vendor ([FirstSales](https://firstsales.io/blog/cold-email-sales-job)) [folklore]. Direction plausible, size unproven.
- Employers are swamped: LinkedIn applications rose ~45% year on year with AI auto-apply (11,000 a minute reported) ([Semafor](https://www.semafor.com/article/06/24/2025/recruiters-swamped-with-ai-generated-job-applications), [ING](https://think.ing.com/articles/ai-monthly-how-ai-is-challenging-authenticity-in-recruitment/)) [evidence-lite]. Specific, genuine interest is the scarce signal.

## 1.3 Referrals

- Interview-odds evidence is strong (above); the mechanism is trust plus referral portals that skip first screen [judgment].
- **How to ask** [judgment]: pick a real contact (ex-colleague, alumnus, community member; weak ties work); first ask a low-cost question ("two questions about the team?"); ask for a referral only if it goes well; send role link, 3-line pitch and CV; make "no" easy. Employees often get referral bonuses, so many are glad to. In UK public sector, referrals matter little.
- **Agent rule:** before a cold private-sector application to a strong-fit role, search the user's 1st/2nd-degree LinkedIn contacts at the employer and draft (not send) an ask. Never request referrals from strangers.

## 1.4 Cover letters and supporting statements

- Readership splits by respondent. Resume Genius (625 US hiring managers): 83% read them, 45% before the CV, 36% under 30 seconds (year unclear, 2023–25) ([Resume Genius](https://resumegenius.com/blog/cover-letter-help/cover-letter-statistics)) [evidence-lite]. Novorésumé (recruiters/HR): ~52% never read them ([Novorésumé](https://novoresume.com/career-blog/cover-letter-statistics)) [evidence-lite]. Hiring managers read; first-line screeners often do not.
- **Rules** [judgment]:
  - *Required*: tailored, ≤1 page (250–350 words).
  - *Optional*: send a 150–250-word specific one, except high-volume hourly, trades and most engineering roles. It helps most for career changers, gaps, relocation, small employers, writing-heavy roles.
  - *Never* generic or visibly AI-templated: ~20% of 600 US hiring managers would reject AI-generated materials and a third say they can spot them ([TopResume, May 2025](https://topresume.com/career-advice/ai-in-hiring-survey)) [evidence-lite]. Include two facts only true of this employer and two evidenced achievements.
  - A **supporting/personal statement** (NHS, Civil Service, local government, education, charity) is not a cover letter: it is the scored application. Map it to the person specification.
- When emailing a CV to a person or agency, a 3–5 line body suffices.

## 1.5 Screening questions, salary, work authorisation, monitoring

- **Knockouts** ("X years of Y?", "authorised to work?", "notice period?"): answer truthfully. Years-of-experience requirements are soft; right-to-work, licences and certifications (CSCS, GMC, SRA, Driver CPC, clearance) are hard [judgment].
- **Work authorisation:** state exact status. "Will you now or in future require sponsorship?" is yes if it ever applies. Never guess.
- **Salary expectations** [judgment unless stated]:
  - Range advertised: anchor in the lower-middle to middle and say "in line with the advertised range, flexible on package".
  - Optional field: blank or "Negotiable". Mandatory numeric: a researched figure. Robert Half UK: "truthful but informed" ([Robert Half](https://www.roberthalf.com/gb/en/insights/finding-a-job/how-answer-what-are-your-salary-expectations)) [evidence-lite].
  - Never volunteer current salary. Many US states (e.g. CA, CO, NY, WA) restrict salary-history questions and require pay ranges in adverts (check state). The EU Pay Transparency Directive (2023/970) requires pre-interview pay information and bars pay-history questions; the deadline was 7 June 2026 but only Italy, Lithuania, Malta, Slovakia (and later Greece) had transposed by mid-2026, others targeting 2027 ([IUS Laboris](https://iuslaboris.com/insights/eu-pay-transparency-directive-which-countries-have-transposed/), [Lockton, Sept 2026](https://global.lockton.com/us/en/news-insights/eu-pay-transparency-directive-implementation-status)) [evidence for status; directive content is my reading]. The UK has no equivalent.
- **"Why us?"**: 3–5 sentences: one specific company fact, one link to the user's evidence, one forward-looking line. No "passionate about".
- **Diversity monitoring** (UK equality monitoring; US EEO self-ID): voluntary and, for US federal contractors, kept from decision-makers ([DirectEmployers](https://directemployers.org/2020/05/11/self-identification-best-practices-for-federal-government-contractors-subcontractors-eeo-1-reporting/)) [evidence-lite]. **Agent rule:** never infer protected characteristics; leave to the user.
- **Disability Confident (UK):** many public bodies and some private employers guarantee interviews to disabled applicants meeting essential criteria who opt in ([Civil Service Careers](https://www.civil-service-careers.gov.uk/disability-confident-scheme)) [evidence]. Opt-in is the user's call; flag it, do not tick it.

## 1.6 Follow-up and thank-yous

- Robert Half (via [Glassdoor](https://www.glassdoor.com/blog/rules-job-interview/)): 81% of 1,000 hiring managers want a follow-up within two weeks [evidence-lite, date unclear]. Recruiter advice: wait a few days, send one or two polite follow-ups at most ([Welcome to the Jungle, Dec 2024](https://www.welcometothejungle.com/en-GB/articles/messaging-recruiters-on-linkedin-tips)) [evidence-lite].
- **Cadence** [judgment]: 7–10 working days after closing date, one brief email to the named contact; one more 7 days later; stop.
- Thank-you notes: 68% of 358 recruiters said one affects decisions ([TopResume via Interview Guys](https://blog.theinterviewguys.com/?p=17265)) [evidence-lite]; other surveys are lower. Send 3 lines within 24 hours, citing one point discussed. Pointless for fixed-score public-sector panels; do not chase scored processes.

## 1.7 Ghost jobs and scams

- **Prevalence:** Greenhouse: 18–22% of 2024 US postings ([Fox 9](https://www.fox9.com/news/ghost-jobs-greenhouse-analysis)) [evidence-lite]. Greenhouse survey of 1,200+ employers (Dec 2025): up to 34% of UK roles never actively recruited, 22% across UK/US/Germany; reasons: talent pools, appearing to grow, gathering candidate data ([HR Review](https://hrreview.co.uk/?p=385524)) [evidence]. 24% of UK workers think they applied to a ghost job ([Employment Hero, Jan 2026](https://tools.prnewswire.com/en-us/live/20823/release/20260119EN65917)); 44% say ghost vacancies stalled their search ([Robert Walters via Workplace Journal](https://workplacejournal.co.uk/2026/02/ghost-job-listings-stalling-uk-job-searches-survey-finds/)) [evidence-lite]. StandOut CV's 34.4% UK figure uses 2023 data [stale]. ~40% of US hiring managers admitted fake listings in 2024 ([Fortune](https://fortune.com/2025/01/16/job-market-rife-fake-listing-ghosting-hiring-managers)) [evidence-lite, self-report].
- **Spotting rules** [judgment]: reposted/refreshed >30 days; no company name ("our client"); no salary plus generic requirements; not on the employer's own careers page; no named hiring manager; recent layoffs or freeze.
- **Scam flags:** pay-to-apply or "training fees"; WhatsApp/Telegram-only contact; free-email recruiter address; instant offer with no interview; cheque for equipment; ID or bank details before offer. UK agencies cannot charge work-seekers for finding work (Conduct Regulations reg. 10), with narrow entertainment exceptions ([Gov.uk](https://www.gov.uk/government/publications/conduct-regulations-2003-guidance-for-employment-agencies-and-employment-businesses/overview-of-the-conduct-regulations-2003), [REC](https://www.rec.uk.com/recruiters/legal/legal-guide/conduct-regulations-2003)) [evidence].
- **UK agency "CV fishing":** agencies advertise nonexistent or filled roles to build databases; described qualitatively, not quantified by any UK source I found [judgment]. Ask for client name and role confirmation before sending the full CV; send a short CV without address/DOB for speculative adverts.
- **Agent rule:** score each posting for ghost risk (age, repost, employer-site match, specificity, named contact); prefer roles on the employer's own page.

## 1.8 LinkedIn alignment

- Recruiters usually check the profile after the CV [judgment]; no primary survey measures mismatch rejections [folklore]. Huntr: interviewed CVs listed a LinkedIn URL more often (71.7% vs 64.3%), correlation only [evidence-lite].
- **Rule:** titles, employers, dates and degrees must match the CV exactly; wording may differ. Headline = target role + 2–3 keywords.
- Matters most for tech, sales, marketing, executive, contractors; little for NHS, Civil Service, graduate-scheme forms [judgment].

## 1.9 Agency recruiters (big in the UK)

- Agencies are paid by employers (contingent ~15–25% of salary; retained for senior roles) [judgment]. They cannot lawfully charge you for finding work; optional extras (e.g. CV writing) must be genuinely optional.
- **Right to represent (RTR):** permission for one agency to submit you to a named client for a named role. Clients generally honour the first documented submission, and a direct application can outrank a later agency one ([Irwin Mitchell terms](https://www.irwinmitchell.com/recruitment/recruitment-agencies), [Deloitte UK](https://www.deloitte.com/uk/en/careers/recruitment-agency-information.html), [BCL Legal](https://www.bcllegal.com/knowledge-base/from-the-team/sending-it-twice)) [evidence-lite]. The REC says agencies need permission before sending your CV to clients [evidence].
- **Never let two agencies submit you to the same firm** (can disqualify you). Agent rules: keep a log (agency, recruiter, client, role, date, written permission); grant RTR per role, in writing; check the user has not applied directly; no client name, no permission.
- **CV for agencies** [judgment]: .docx or ATS-parsable PDF, two pages, reverse chronological, plain headings (they parse into Bullhorn-type systems and often reformat). Put notice period and salary bracket in the email, not on the page.
- **Working with them:** reply within hours; be honest about salary, notice and other processes; ask for feedback within 48 hours of interviews; use 3–5 specialists, not 20 generalists. Never accept then renege.

## 1.10 Internal TA vs hiring managers

- **TA/recruiters** screen to spec and run compliance: give clean, keyword-aligned materials; be responsive; do not bypass structured processes.
- **Hiring managers** decide. Contact is welcome in startups, tech, sales, creative, senior hires; unwelcome in public sector, NHS, academia (pre-formal stage), law-firm graduate recruitment and graduate schemes [judgment].
- **Rule:** apply through the official channel and, where the sector allows, send one concise note to the hiring manager. Never message instead of applying.

---

# PART 2 – SECTOR PLAYBOOKS

Template: Where posted · CV leads with · Cover letter/statement · Process quirks · Outreach · Timing · Pitfalls · UK vs US vs EU.

## 2.1 Software engineering & IT

- **Where posted:** company ATS pages (Greenhouse, Ashby, Lever), LinkedIn, Wellfound (6.0% Huntr response), Otta/Welcome to the Jungle, Hacker News "Who is hiring", UK tech agencies (Harvey Nash, Hays, Robert Walters); Indeed for helpdesk/support. Dice 0.35% in Huntr's sample [evidence-lite].
- **CV leads with:** stack and level; 3–5 quantified impact bullets (latency, cost, users); GitHub/portfolio URL. One page US, one to two UK.
- **Cover letter:** rarely read; optional. A 4-sentence recruiter email suffices; startups reward a product-specific note [judgment].
- **Process:** ATS → recruiter call → technical screen → take-home (commonly 3–4 hours) or live coding → system design/behavioural loop; ~4–8 weeks (Gem 2026 ~62 days for engineering, secondary) [evidence-lite]. Market is tough: listings reportedly ~36% below Feb 2020 (vendor), new-grad postings -15% with applications per job +30% (Handshake) ([Pragmatic Engineer](https://newsletter.pragmaticengineer.com/p/state-of-the-job-market-2026)) [evidence-lite].
- **Outreach:** short technical notes to engineering managers or the posting's recruiter are welcome. Referrals pay most here.
- **Timing:** first week; Q1 and Sep–Oct peaks [judgment].
- **Pitfalls:** empty GitHub; AI-written READMEs not matching code; undisclosed right-to-work gaps; keyword stuffing; unpaid take-homes over ~4 hours.
- **UK/US/EU:** UK contractors use Jobserve/CWJobs (see 2.17); US sponsorship filtering is harsh; Germany expects a full Lebenslauf and certificates.

## 2.2 Data / AI / ML

- **Where posted:** LinkedIn, company ATS, AI-lab pages, Hugging Face jobs, jobs.ac.uk for research, agencies (Harnham, Hays).
- **CV leads with:** shipped models and metrics moved; SQL/Python/Spark/dbt/PyTorch/MLflow/cloud; 2–4 projects with live links; publications for research roles. For ML engineers, deployment and monitoring beat notebooks ([IT Job Board UK](https://www.itjobboard.co.uk/blog/210/data-scientist-jobs-uk-2026-%7C-salary,-skills-&-career-guide/)) [evidence-lite].
- **Cover letter:** optional; research roles add a research-fit paragraph [judgment].
- **Process:** SQL/Python screen → case study or take-home → stats/ML system design. Reviewers may spend only minutes on projects: lead with the best three [evidence-lite]. Many career-switchers realistically land analyst roles first [folklore].
- **Outreach:** as engineering; for labs, email the PI with a one-paragraph summary and paper link.
- **Timing:** industry year-round; research roles follow academic calendars.
- **Pitfalls:** Titanic-style projects only; no SQL; no business impact.
- **UK/US/EU:** US "scientist" titles often want master's/PhD; UK more flexible; EU wants documented degrees.

## 2.3 Product & UX/design (portfolio-led)

- **Where posted:** LinkedIn, company ATS, Otta/WTTJ, Dribbble/Behance (limited), UK digital agencies.
- **CV leads with:** portfolio URL at top; role, scope, outcomes; PMs: product, metrics moved, team size. One page.
- **Cover letter:** short, tied to a product observation; portfolio intro often substitutes [judgment].
- **Process:** "~30 seconds" is the most-cited portfolio review time ([UX Collective](https://uxdesign.cc/only-30-seconds-to-reject-your-portfolio-8cb14ac70674)) [folklore]. NN/g: managers rarely read whole portfolios, so choose strongest projects and make them scannable ([NN/g](https://nngroup.com/articles/ux-design-portfolios/)) [evidence]. Then portfolio presentation, design exercise, PM product-sense cases.
- **Outreach:** welcome if it carries a relevant case-study link; critique their product only if specific and constructive.
- **Timing:** year-round; startup funding cycles matter.
- **Pitfalls:** 8+ projects; no process or outcomes; locked case studies; unpaid large exercises.
- **UK/US/EU:** UK/EU often accept PDF portfolios; US prefers links; no photo outside DACH.

## 2.4 Marketing, comms & creative

- **Where posted:** LinkedIn, Indeed, The Drum/Campaign jobs, Creative Access, Charity Job (non-profit comms), specialist agencies (Major Players, Propel).
- **CV leads with:** channel plus results (CAC, ROAS, MQLs, coverage); tools (HubSpot, GA4, Meta Ads); work-sample link. Two pages.
- **Cover letter:** matters more than elsewhere: it is a writing sample. 200–300 words with a point of view on the brand [judgment].
- **Process:** writing/strategy test (2–4 hours), channel audit, presentation. Agencies hire in bursts after pitch wins [judgment].
- **Outreach:** welcome; open with a brand-specific idea. PR and internal comms value brevity.
- **Timing:** January and September [judgment].
- **Pitfalls:** typos (fatal), vague "increased engagement", no samples, generic AI copy.
- **UK/US/EU:** UK agencies lean on agency recruiters; US on LinkedIn/Handshake; EU adds language requirements.

## 2.5 Sales & business development

- **Where posted:** LinkedIn, Indeed, ATS pages; specialist agencies (Salesforce Search, Hays Sales); SaaS startups on Wellfound/Otta.
- **CV leads with:** quota attainment (e.g. 118% of £800k), rank, deal size, segment, tools (Salesforce, Outreach). Numbers on every role. Two pages.
- **Cover letter:** optional; the first message is your sales test [judgment].
- **Process:** recruiter screen → manager call → mock call/demo → presentation → references (often CRM-checked). Probe OTE: ramp, quota attainment of the team, accelerators.
- **Outreach:** welcomes hustle. Guides advise messaging the sales manager or VP, not generic HR inboxes, and showing prospecting skill in the note ([FirstSales](https://firstsales.io/blog/cold-email-sales-job), [Recruiter.com](https://www.recruiter.com/i/5-tips-to-help-you-craft-a-linkedin-message-sales-reps-will-respond-to/)) [folklore]. Three touches over two weeks on two channels is acceptable [judgment].
- **Timing:** quarter starts (Jan, Apr, Jul, Oct) and new-fiscal-year budgets [judgment].
- **Pitfalls:** unquantified claims, long messages, mass-messaging ten people at one company.
- **UK/US/EU:** US OTE-heavy, at-will; UK has notice, garden leave, restrictive covenants; Germany/France more structured; languages valuable.

## 2.6 Finance, banking & accounting

- **Where posted:** *Graduate:* employer sites (open Aug–Sept), Bright Network, TARGETjobs, Handshake. *Experienced:* LinkedIn, agencies (Michael Page, Robert Walters, Hays, Morgan McKinley), eFinancialCareers, ICAEW/ACCA boards.
- **CV leads with:** qualification status first (ACA, ACCA, CIMA, CFA level, CPA with the 150-credit-hour route in the US; say "part-qualified" explicitly); firms, deal sizes, systems (SAP, Excel/VBA). One page for early careers/IB; two for experienced [judgment].
- **Cover letter:** graduate forms ask "why this bank/division" in short boxes; letters rarely needed. Cover firm, division, a deal, a personal link [judgment].
- **Process:** online form → numerical/verbal/logical tests (SHL/Cappfinity-type) → recorded video → assessment centre/Superday. Test practice matters ([Cambridge](https://www.careers.cam.ac.uk/node/528), [Nottingham](https://www.nottingham.ac.uk/careers/students/applications/psychometrictests/)) [evidence-lite]. IB runs the earliest cycle: spring weeks and summer analyst forms open Aug–Sept, close from October, some filled on a rolling basis ([Prospect Rock Partners](https://prospectrockpartners.com/the-class-of-2029-investment-banking-recruiting-guide-bank-by-bank-timelines-deadlines-and-strategy-for-summer-2028-internships/), [Deutsche Bank](https://careers.db.com/students-graduates/your-application)) [evidence-lite]. Big 4 early-careers typically open Aug–Sept and close around spring; sources conflict, so check each firm ([Whali](https://whali.co.uk/blog/graduate-scheme-deadlines-2026-2027)) [evidence-lite].
- **Outreach:** alumni coffee chats and bank events help IB. Accountancy is process-led. Experienced hires go via agencies; cold messages to MDs rarely work [judgment].
- **Timing:** accountancy busy season (Jan–Apr) slows hiring; bonus-season moves Mar–Apr [judgment].
- **Pitfalls:** applying to barred multiple divisions; failed tests (often a 6–12 month lockout); qualification overstated; typos; missing regulatory status (FCA SM&CR, US Series 7/63).
- **UK/US/EU:** US resume is one page with GPA; UK graduate forms may ask UCAS points; Germany expects full certificates; Switzerland/Luxembourg add languages.

## 2.7 Legal

- **Where posted:** *TCs/vac schemes:* firm sites, Legal Cheek, TARGETjobs, All About Law, LawCareers.net. *Paralegal/lawyer:* LinkedIn, Indeed, agencies (Taylor Root, Major Lindsey & Africa). *In-house:* LinkedIn, agencies.
- **CV leads with:** academics (degree class, SQE/LPC status), paralegal/vac-scheme experience, languages. Two pages UK; one US with law school detail.
- **Cover letter:** UK firms mainly use online motivation/commercial-awareness questions; letters when asked must say why this firm and practice area. US OCI and laterals require letters [judgment].
- **Process:** vac schemes are the main route to TCs. Examples: Linklaters closes 3 Dec 2026 (scheme participants get a TC interview), Norton Rose Fulbright 4 Dec 2026, Burges Salmon 5 Jan 2027 ([TARGETjobs](https://targetjobs.co.uk/jobs/vacation-scheme-2027-253487), [Bright Network NRF](https://www.brightnetwork.co.uk/graduate-jobs/norton-rose-fulbright/spring-summer-vacation-scheme-london-2027-ak82), [Burges Salmon](https://www.burges-salmon.com/join-us/emerging-talent/vacation-scheme), [Legal Cheek calendar](https://www.legalcheek.com/?p=102414)) [evidence]. Limits: Reed Smith max three applications; Ashurst scheme or direct TC, not both ([Ashurst](https://www.brightnetwork.co.uk/graduate-jobs/ashurst/summer-vacation-scheme-2027)) [evidence]. Some aggregator pages are stale; verify on firm sites. Then SJT, case study, group exercise, partner interview.
- **Outreach:** firm events, insight days, trainee contacts (culture questions, not job asks). No cold emails to partners. Laterals: agencies plus a note to the practice head.
- **Timing:** vac schemes autumn–January; TCs ~2 years ahead; NQ hiring tied to qualification date [judgment].
- **Pitfalls:** wrong firm name pasted, generic commercial awareness, breaching application limits, unclear SQE status.
- **UK/US/EU:** US is JD-based with summer/autumn OCI; England qualifies via SQE (traditional TC still common at large firms); EU civil-law routes need national exams and local language.

## 2.8 Healthcare & NHS (critical UK specifics)

- **Where posted:** [NHS Jobs](https://www.jobs.nhs.uk) (England, Trac-backed), NHS Scotland, Health Jobs Wales, HSC (NI), trust sites, RCN, BMJ Careers, locum agencies; Indeed for private care.
- **Lead with the person specification.** Employment history and qualifications (NMC/GMC/HCPC numbers) are checked; the **supporting information** is scored. Guidance: shortlisting is against the person spec; essential vs desirable (assume unmarked = essential); cover every essential criterion with an example; use spec headings ([NHS Jobs advice](https://www.jobs.nhs.uk/candidate/search/advice/making-successful-applications), [LHCH](https://www.lhch.nhs.uk/top-tips-for-making-a-successful-application), [UH Liverpool](https://careers.uhliverpool.nhs.uk/your-recruitment-journey/how-best-write-your-application)) [evidence-lite].
- **Statement norms:** no cover letter. Typically 750–1,500 words if unlimited (varies by trust). One STAR example per essential criterion with outcome and reflection; reflect NHS values (compassion, respect, quality of care) [judgment]. [RCN samples](https://www.rcn.org.uk/Professional-Development/Your-career/Sample-Supporting-Statements).
- **Process:** after closing, managers score anonymised forms on Trac against the spec; personal/monitoring data is not used [evidence-lite]. Roles can close early on volume. Pre-employment checks (DBS, occupational health, references, right to work) are slow. Panels are structured: values, scenarios, sometimes presentation or clinical test.
- **AI:** trusts differ. Many will not reject for AI use but expect personal examples; FOI replies suggest no AI-detection tools ([Bolton NHS FT](https://boltonft.nhs.uk/join-our-team/use-of-artificial-intelligence-ai-when-writing-job-applications), [Trac-hosted trust guidance](https://static.trac.jobs/docs-employer/412/2969/Using%20AI%20when%20completing%20application%20forms.pdf)) [evidence-lite]. Agent: draft only from the user's real examples; user edits.
- **Outreach:** adverts name a contact for an informal chat or visit; using it is expected, not bypassing. Ask one or two questions.
- **Timing:** year-round; Band 5 nursing peaks around graduation (Sep–Oct, Mar–Apr); medical training has national timelines (Oriel) [judgment].
- **Pitfalls:** missing one essential criterion; generic statement; no registration PIN; unexplained gaps; Band 6 without Band 5-level evidence.
- **UK/US/EU:** US hospitals use Workday/Taleo-type ATS, state licensure, credentialing, staffing agencies; EU needs recognition of qualifications and language certificates. UK care-sector sponsorship rules changed in 2025; verify before applying [judgment, unverified].

## 2.9 Public sector & Civil Service

- **Where posted:** Civil Service Jobs, Gov.uk Find a job, Scottish/Welsh portals, council sites, police/fire sites, public appointments portal, NHS. US: USAJOBS, GovernmentJobs (8.7% Huntr response). EU: EPSO.
- **Lead with Success Profiles:** Behaviours, Strengths, Experience, Ability, Technical; the advert says which are tested at sift ([GOV.UK candidate overview](https://www.gov.uk/government/publications/success-profiles/success-profiles-candidate-overview), [Behaviours](https://www.gov.uk/government/publications/success-profiles/success-profiles-civil-service-behaviours)) [evidence]. Many roles require a CV plus personal statement, sometimes per-behaviour answers.
- **Statement norms:** word limits vary by advert. Reported patterns: ~250 words per behaviour example; 500–1,250 words for the personal statement ([Civil Service Careers](https://www.civil-service-careers.gov.uk/how-to-write-your-ps), [Home Office](https://support.careers.homeoffice.gov.uk/how-do-i-write-a-cv-personal-statement-or-behaviours)) [evidence-lite; I found no single official "250 words" rule]. Use STAR, spend most words on your Action, "I" not "we", mirror the essential criteria, land at 90–95% of the limit, and echo the behaviour wording for the grade.
- **Process:** two-assessor sift against criteria; some departments anonymise; online tests (judgement, verbal, numerical); 30–60-minute behaviour/strengths interview; sometimes presentation. Disability Confident guarantee applies. 4–10 weeks, plus vetting (BPSS/SC/DV) of weeks to months; some roles are nationality-restricted.
- **Outreach:** do not lobby managers; use the named contact only for clarification or adjustments (fair and open competition) [judgment].
- **Timing:** adverts commonly open ~2 weeks; large campaigns rolling; Fast Stream applications run autumn (verify).
- **Pitfalls:** answering what you prefer, not the behaviour; no outcome; over limit; "we"; same example everywhere; missing the closing time.
- **UK/US/EU:** USAJOBS federal resumes run 3–5 pages and must map to "specialized experience"; EPSO uses CBT tests and assessment centres on long cycles; UK local government uses forms plus person spec.

## 2.10 Education & academia

- **Where posted:** *Schools (England):* [Teaching Vacancies](https://teaching-vacancies.service.gov.uk) (DfE), TES, Eteach, trust/LA sites. *HE:* [jobs.ac.uk](https://www.jobs.ac.uk) (not comprehensive), university portals, HigherEdJobs (US), MathJobs, PhilJobs, EconJobMarket.
- **CV leads with:** *Teaching:* QTS/PGCE, subject/key stage, outcomes, safeguarding training. *Academia:* academic CV (education, publications, grants, teaching, supervision, service, referees); length unlimited. UK packages: CV + research statement + referees, increasingly a teaching statement; US packages: teaching and research statements, sometimes diversity statement, 3 letters ([jobs.ac.uk guide](https://www.jobs.ac.uk/media/pdf/careers/resources/building-academic-job-applications-a-quick-practical-guide-for-early-career-researchers.pdf), [LSE](https://info.lse.ac.uk/current-students/careers/information-and-resources/phd-resources/academic-applications)) [evidence-lite]. Diversity statements are contested in the US; follow the posting.
- **Statement norms:** teachers: supporting letter against the person spec (~2 pages) referencing the school's ethos; visit expected. UK HE: address each essential/desirable criterion explicitly. US: 1–2 page cover letter plus statements.
- **Process:** teaching: lesson observation, student panel, interview, safeguarding questions, DBS and KCSIE checks. HE: job talk or teaching demo, panel. US academic cycle: ads Sept–Nov, deadlines Oct–Dec, interviews Jan–Mar ([Matt Might](https://matt.might.net/articles/advice-for-academic-job-hunt), [LSE US guide](https://info.lse.ac.uk/current-students/careers/Assets/Documents/Applying-for-US-Jobs.pdf)) [evidence-lite]. UK postdocs rolling, grant-linked. UK referee letters tend to be shorter than US norms; brief referees [evidence-lite].
- **Outreach:** contacting the PI/supervisor beforehand is expected for PhD/postdocs; head-of-department emails are acceptable for lectureships; visit schools when invited.
- **Timing:** teachers in England resign by 31 Oct (leave at Christmas), 28 Feb (Easter) or 31 May (summer) under the Burgundy Book; head teachers' autumn date can be 30 Sept ([Edapt](https://edapt.org.uk/blog/2024/02/teacher-resignation-dates), [Southwark](https://education.southwark.gov.uk/assets/attach/6428/Resignation-dates.pdf), [Eteach](https://www.eteach.com/blog/how-to-resign-from-your-teaching-job)) [evidence]. Today is 2 Nov 2026, so 31 Oct has just passed; next is 28 Feb 2027. September-start adverts peak Jan–May. Independent schools set their own terms.
- **Pitfalls:** research statements that are lists; generic letters to schools; omitting referee details (schools often take references pre-interview); US-style CVs for UK schools.
- **UK/US/EU:** US teachers need state licensure; Germany/France use Habilitation frameworks; UK academic CV is standard.

## 2.11 Engineering & manufacturing

- **Where posted:** LinkedIn, Indeed, company ATS (defence primes), professional-body boards (IMechE, ICE, IET), agencies (Matchtech, Rullion, Hays Engineering).
- **CV leads with:** registration (CEng/IEng/EngTech in UK; PE in US; EUR ING), discipline, projects with scale (£/$, MW, tolerances), tools (CAD, FEA, PLC, Lean/Six Sigma), safety tickets (CSCS, IOSH, NEBOSH, SMSTS), clearance (SC/DV). Two pages.
- **Cover letter:** optional; useful for graduate schemes and defence.
- **Process:** ATS → technical interview → competency interview; graduate aptitude tests; background and medical checks; export-control and nationality limits in defence. Hiring tracks contract awards [judgment].
- **Outreach:** professional-body events, project directors; agencies dominate contract and construction engineering.
- **Timing:** graduates Sep–Dec; experienced year-round.
- **Pitfalls:** "working towards CEng" left unexplained; clearance eligibility undisclosed; duties instead of outcomes.
- **UK/US/EU:** US PE licence required for public-works sign-off; EU uses Bologna equivalence and EUR ING; Germany values Dipl.-Ing. and certificates.

## 2.12 Skilled trades & logistics

- **Where posted:** Indeed (dominant for volume; Huntr's tech-skewed 4.5% should not be generalised) [judgment], Find a Job (470 "CSCS" listings in one snapshot), Reed, Totaljobs, agencies (Adecco, Randstad, Staffline), employer sites (Amazon, DHL, Wincanton), local social groups.
- **CV leads with:** valid cards and licences. **CSCS** is not a legal requirement but most principal contractors insist ([CSCS](https://cscs.uk.com/about/), [Get Licensed](https://www.get-licensed.co.uk/get-daily/is-a-cscs-card-a-legal-requirement-to-work-in-the-construction-industry)) [evidence]. Also NVQ L2/3, Gas Safe, NICEIC/18th Edition, HGV class, Driver CPC, FLT, SIA, right to work. One page; phone and location on top.
- **Cover letter:** none; a one-line message to the supervisor with availability, card and start date.
- **Process:** Indeed quick apply → phone screen → agency registration → trial shift or induction → drug/background test; agency-to-permanent conversion common. Days to two weeks [judgment].
- **Outreach:** call or visit the branch/site manager; reply within hours. Friend referrals are often decisive.
- **Timing:** logistics peaks before Christmas; construction in spring.
- **Pitfalls:** expired cards, missing tickets, no availability, unprofessional email handle, missing calls, umbrella confusion (2.17).
- **UK/US/EU:** US OSHA 10/30, CDL; EU needs national qualification recognition; Germany/Netherlands lean on staffing agencies.

## 2.13 Hospitality, retail & customer service

- **Where posted:** Indeed, employer pages (Tesco, M&S, John Lewis, Boots), Caterer.com, local Facebook/Instagram groups, Indeed Flex, Find a Job.
- **CV leads with:** availability, customer-facing experience, languages, Level 2 Food Safety, personal licence, first aid, right to work. One page. Large chains often use online forms and assessments (M&S: online application and assessment, then in-store interview) ([Retail Gazette, Oct 2026](https://www.retailgazette.co.uk/blog/2026/10/retailers-ramp-up-christmas-recruitment/)) [evidence].
- **Cover letter:** none; a polite three-line note when applying in person.
- **Process:** rolling recruitment, SJTs, group sessions, trials. 2026 seasonal drives: John Lewis 10,400+ roles, Tesco 28,000+; hiring Sep–early Dec with rolling applications; seasonal staff can convert ([Indeed Flex](https://indeedflex.co.uk/?p=4768), [Gov job help](https://jobhelp.campaign.gov.uk/?p=8079)) [evidence-lite].
- **Outreach:** visits and manager chats work for independents (no source verifies walk-in effectiveness) [folklore]; chains want the online route.
- **Timing:** retail Sep–Nov; hospitality events and summer posts from spring; supermarket graduate schemes run autumn cycles.
- **Pitfalls:** no stated availability; expired food hygiene; poor assessment prep.
- **UK/US/EU:** alcohol-sale age rules differ; US uses in-store/online forms and I-9; EU seasonal staff hired via local agencies.

## 2.14 Executive & senior leadership

- **Where posted:** mostly not. **Retained search** (Heidrick & Struggles, Korn Ferry, Spencer Stuart, Odgers, Russell Reynolds, boutiques), boards and networks, PE/VC operating teams; advertised only in public sector and charities. NEDs: search firms, Institute of Directors, public appointments portal.
- **Documents:** two-page (max three) executive CV with scope (P&L, headcount, geographies), board/NED roles, a one-page leadership bio, matched LinkedIn. Advertised roles: a 1–2 page statement mapped to the candidate pack's outcomes.
- **Process:** longlist → consultant calls → panel/CEO/Board → leadership assessments → deep references → negotiation (equity, notice, garden leave). 3–6 months. Search firms work for the client, not you ([glossary summary](https://www.myndsolution.com/glossary/executive-search/)) [evidence-lite]. A former PayPal MD says search firms are a core board network because you cannot predict which wins a mandate ([AICD](https://www.aicd.com.au/board-of-directors/career/how-to-get-on/how-to-stand-out-to-headhunters.html)); research frames headhunters as shaping, not just matching, the market ([LSE](https://researchonline.lse.ac.uk/id/eprint/64472)) [evidence-lite]. I found no reliable share of senior roles filled by search.
- **Outreach:** relationship-first. Send a concise credentialed intro to 15–30 relevant sector/function consultants, offer to be a source or referrer, update every six months. No mass CV blasts; never "find me a job" [judgment].
- **Timing:** slow July–August and Christmas; strong Sep–Nov, Jan–Mar [judgment].
- **Pitfalls:** hype, no numbers, unrealistic compensation, exposing a confidential search, one CV for all.
- **UK/US/EU:** US executives negotiate equity and severance hard; UK has garden leave and covenants; DACH has Vorstand/Aufsichtsrat structures.

## 2.15 Graduates & early career

- **Where posted:** employer graduate sites, TARGETjobs, Bright Network, Prospects, Handshake (US), RateMyPlacement, Milkround, Indeed; apprenticeships on Find an apprenticeship.
- **CV leads with:** degree and predicted grade, relevant modules, internships and part-time work, societies, quantified wins. One page, no photo (UK/US) [judgment].
- **Cover letter:** most schemes use online forms with 150–500-word competency/motivation answers. Prepare reusable evidence stories; tailor "why us".
- **Process:** form → psychometrics (numerical, verbal, logical, SJT) → recorded video (sometimes AI-scored) → assessment centre. Test use is widespread (">80% of UK graduate employers" is a prep-site citation) [folklore]; see [Nottingham](https://www.nottingham.ac.uk/careers/students/applications/psychometrictests/), [Warwick](https://warwick.ac.uk/services/careers/blog/the_graduate_recruitment_process). Competition: 140 applications per vacancy; graduate hiring fell 8% in 2024–25 and rose ~4% in 2025–26; retail/FMCG/tourism ~290 per role ([ISE](https://ise.org.uk/knowledge/insights/492/apprenticeships_rise_as_graduate_vacancies_drop_8), [Wonkhe](https://wonkhe.com/wonk-corner/a-slightly-better-outlook-for-graduate-jobs)) [evidence].
- **Outreach:** campus fairs, employer events, alumni for insight (not referrals at scale). Do not chase rolling-process status within a month.
- **Timing:** IB, consulting, law Sep–Nov; many corporates Oct–Jan; Big 4 into spring. Start in the penultimate year.
- **Pitfalls:** failing a test then re-applying (results are held); wrong firm name; unpractised SJTs; one example for every question.
- **UK/US/EU:** US uses on-campus recruiting and GPA cut-offs (often 3.5+ for finance/consulting); UK uses degree classes; EU relies on internships and master's.

## 2.16 Career changers

- **Where posted:** target-sector boards plus returnship and bootcamp-partner programmes; internal moves.
- **CV leads with:** a summary linking past work to the new field; "relevant skills/projects" above chronology; retraining; quantified transferable outcomes. Hybrid format with full reverse-chronological history to survive ATS [judgment].
- **Cover letter:** use one (250–350 words): why, what you bring, proof of commitment [judgment].
- **Process:** employers claim skills-based hiring (85% in TestGorilla's 2025 survey; 53% dropped degree requirements), yet a Harvard/Burning Glass study found 45% of firms that dropped degree requirements did so "in name only" ([TestGorilla](https://www.testgorilla.com/skills-based-hiring/state-of-skills-based-hiring-2025/), [HCAmag](https://www.hcamag.com/ca/specialization/recruitment/in-name-only-firms-dropping-degree-requirements-fall-short-in-practice/477331)) [evidence-lite, vendor/self-report]. Expect to prove skill by test or project, and to target bridge roles first.
- **Outreach:** informational interviews are the main tactic and feed referrals (1.3); state exactly what you ask.
- **Timing:** plan 6–12 months; 20–40 targeted applications [judgment].
- **Pitfalls:** hiding the change; old duties list; no proof of new skills; senior roles in a new field; agencies who place only in your old sector.
- **UK/US/EU:** US more tolerant of non-linear paths; UK public sector scores only against the spec, so transferable evidence must be explicit; Germany expects formal qualifications in regulated professions.

## 2.17 Contractors & freelancers

- **Where posted:** Jobserve, CWJobs, Technojobs, LinkedIn, agency databases; Upwork/Toptal. US: staffing firms (W2/C2C/1099), Dice. EU: freelance.de, Malt.
- **CV leads with:** availability date, rate bracket (or "on application"), location/remote, clearance, top skills, last 3–5 contracts with client, scope and result. Two pages; tailor every submission ([Hays](https://www.hays.co.uk/career-advice/article/how-to-determine-your-contractor-rate)) [evidence-lite].
- **Cover letter:** a 3–4 line covering email: availability, rate, right to work.
- **Process:** days, often one client interview; start in 1–3 weeks. **IR35:** medium/large private-sector clients decide status and issue a Status Determination Statement; inside-IR35 roles typically need a 15–25% higher gross day rate to match take-home ([IT Job Board](https://www.itjobboard.co.uk/blog/392/it-contract-jobs-uk-2026-day-rates-ir35-market-trends/)) [evidence-lite; confirm with an accountant]. Cited 2026 outside-IR35 IT rates: ~£450–650 developers/DevOps, £600–900 cloud architects, London +20–30% [evidence-lite]. **Umbrellas:** from 6 April 2026, agencies and end-clients share PAYE/NIC liability for umbrella defaults, so expect agency scrutiny of umbrella choice; IR35 rules were unchanged ([Lewis Silkin](https://www.lewissilkin.com/en/insights/2026/03/02/umbrella-company-tax-compliance-changes-effective-6-april-2026), [Osborne Clarke](https://www.osborneclarke.com/system/files/documents/25/12/09/2026-uk-umbrella-regime_0.pdf)) [evidence]. The post-2022 boom is over; clients scrutinise spend [evidence-lite].
- **Outreach:** cultivate 3–5 agency consultants per niche; reply within hours; keep availability current; LinkedIn matters [evidence-lite].
- **Timing:** contracts end at quarter/fiscal ends; start looking 4–8 weeks ahead [judgment].
- **Pitfalls:** wrong rate; unstated IR35 preference; inside-IR35 contract at an outside rate; unvetted umbrella; double submission through two agencies.
- **UK/US/EU:** US 1099/C2C/W2 and non-competes; EU bogus self-employment rules (Germany); UK IR35.

## 2.18 Remote-first roles

- **Where posted:** LinkedIn remote filter, Wellfound, We Work Remotely, Remote OK, Otta/WTTJ, Himalayas, fully-remote companies' own ATS pages.
- **CV leads with:** async evidence (written docs, distributed teams), tools (Slack, Notion, Linear), self-management outcomes, plus **time zone, location and right-to-work / contract type** at the top.
- **Cover letter:** use one; it doubles as a writing sample [judgment].
- **Process:** fully remote jobs are only ~5–6% of postings (down from 10–12%) yet draw 3–6x the applications of on-site roles ([Jobgether, Dec 2025](https://jobgether.com/blog/remote-work-barometer-2025)) [evidence-lite]; LinkedIn 2022 data showed remote at 20% of listings but 50% of applications ([NY Fed deck](https://www.newyorkfed.org/medialibrary/media/research/advisory_panel/eap/eap_kimbrough_20220323.pdf?la=en)) [stale]. Expect written async interviews, paid trials, contractor/EOR arrangements.
- **Outreach:** high-signal and short; a public work sample beats a pitch.
- **Timing:** apply fast; roles may close after 100–200 applications [judgment].
- **Pitfalls:** assuming "work from anywhere" (many roles are country-restricted); ignoring time-zone overlap; salary expectations above location bands; vague async skills.
- **UK/US/EU:** US "remote" often excludes UK/EU; EU roles may use Employer-of-Record; UK candidates for US remote jobs should expect contractor terms.

## 2.19 Management consulting & strategy

- **Where posted:** firm careers portals (McKinsey, BCG, Bain; Deloitte, PwC, EY, KPMG advisory; boutiques such as PA Consulting, Baringa, L.E.K., Oliver Wyman), university careers services, Bright Network/TARGETjobs, LinkedIn; MBA programmes feed the post-MBA intake. Experienced hires: referrals, alumni networks, boutique/search recruiters.
- **CV leads with:** one page in consulting format; academics (degree class, test scores where asked), then quantified impact and leadership in each role. Experienced: sector/functional expertise and client-facing outcomes.
- **Cover letter/statement:** several firms still ask for a short, firm- and office-specific motivation statement; others use forms only ([Road to Offer UK guide](https://www.roadtooffer.com/blog/uk-consulting-recruiting-guide), July 2026) [evidence-lite]. Apply to a specific office: a US or European application does not carry over [evidence-lite].
- **Process:** online screens are the first hard filter. MBB uses its own tests (McKinsey Solve, BCG Casey); UK stacks also use SJTs and numerical/verbal reasoning on SHL-type platforms; parts of Big 4 add Watson-Glaser-style tests; Bain UK adds behavioural and reasoning assessments. Then case interviews (structure, quantitative accuracy, defensible recommendation; usually profitability/growth in round one) plus a fit interview on motivation and leadership. Round counts vary by firm. I found no authoritative "PST" requirement for UK processes (a US-era term) [evidence-lite].
- **Timelines (2026 cycle; sources conflict, check each office):** McKinsey UK graduate portal Jan–29 Mar 2026 with a reopening expected autumn; Bain London reopens in September with first-round cases mid-November; BCG UK opens in autumn, rolling; Big 4 advisory opened Sept 2025 and closed 24 Apr (EY, KPMG), 1 May (Deloitte), 1 June (PwC), rolling with early office closure ([Road to Offer](https://www.roadtooffer.com/blog/uk-consulting-recruiting-guide); US dates differ: e.g. BCG undergraduate 2 Jun/7 Jul 2026, [Management Consulted](https://managementconsulted.com/bcg-undergraduate-deadline-2026/)) [evidence-lite]. Rolling review rewards early applications. MBA cycles run on school calendars [judgment].
- **Outreach:** target-school students get coffee chats, workshops and society access; non-target candidates can apply through open portals and face the same rubric ([Road to Offer](https://www.roadtooffer.com/blog/uk-consulting-recruiting-guide)) [evidence-lite]. Etiquette [judgment]: ask alumni about work and culture, not for referrals in the first message; 15-20 minute calls; follow up with thanks; for experienced hires a referral is the strongest route (see 1.3).
- **Timing:** graduates apply Sep–Nov (internships) and Jan–Apr (UK full-time); experienced hires year-round, tied to staffing gaps [judgment].
- **Pitfalls:** rejection locks (firms commonly bar reapplication for 6–12 months [judgment]); applying to several offices of one firm; case-prep memorisation without structure; generic motivation statements; failing the online test.
- **UK/US/EU:** US cycles open earlier (summer for the following year) with on-campus recruiting; UK stacks lean on SJT/numerical tests; EU offices (e.g. Germany, France) expect a full CV with language and sometimes certificates.

## 2.20 Charity, non-profit & third sector

- **Where posted:** [CharityJob](https://www.charityjob.co.uk), Guardian Jobs, Third Sector Jobs, Charity People, Indeed, employer ATS pages, ReachVolunteering for trustee/volunteer roles, specialist fundraising/charity recruiters; US: Idealist, Candid, Chronicle of Philanthropy.
- **CV leads with:** mission-relevant impact (funds raised, beneficiaries served, programmes delivered), then transferable skills; volunteering and trustee roles listed as real experience. Two pages.
- **Cover letter/statement:** the **supporting statement is the scored document**, like the public sector. Charities weight it more than most employers ([ClientEarth](https://clientearth.org/about/careers/practical-tips)); selection is mainly from it (Sutton Carers Centre guidance, via search). Structure it by the person specification criteria with the criteria as subheadings; open with motivation; connect your values to their strategy; draw evidence from work, volunteering or personal life; keep to the limit (often 2 sides of A4; where none, 1–2 pages) ([Salford careers](https://www.salford.ac.uk/careers/cvs-applications-and-interviews/personal-and-supporting-statements), [CharityJob statement guide](https://downloads.charityjob.co.uk/attachments/supporting_statement_guide_2024_04_10_04_48_21_pm.pdf)) [evidence-lite].
- **Process:** application form or CV + statement, a first interview (often video), a second interview with a task, presentation or case; small charities have 1–2 rounds and fast turnarounds, larger ones add checks (DBS for safeguarding roles, references). Values questions are standard.
- **Market data:** CharityJob median advertised salary £36,000 in 2025 (£35,000 in 2024); roles posted fell 18% in 2025 while candidate applications rose by over a third; 34% of London entry/junior full-time roles paid below the London Living Wage ([CharityJob salaries 2025](https://www.charityjob.co.uk/recruiterinsights/charity-salaries-2025-insights-trends-and-benchmarks), [2026 trends](https://www.charityjob.co.uk/careeradvice/trends-in-charity-salaries-2026/)). Civil Society reports a different average (£36,100, +4%), so mean/median and year differ across sources [evidence-lite].
- **Salary transparency:** most adverts show a salary or band, but many are bands with a low entry point; use the advertised figure rather than negotiating hard on small charities. Check for restricted funding and fixed-term contracts [judgment].
- **Outreach:** short notes to a named hiring manager are fine but the statement does the work; informal-chat contacts are often listed and welcomed. Volunteering first is a legitimate route in. Trustee roles: apply via Reach Volunteering (UK-based, three years' experience in a skill area, free text on why you are interested and what you bring; up to five applications as a guest) ([Reach](https://reachvolunteering.org.uk/how-do-i-apply-volunteer-or-trustee-opportunity)) [evidence].
- **Timing:** year-round; fundraising peaks (autumn appeals) bring Q3 hiring; grant cycles drive fixed-term posts [judgment].
- **Pitfalls:** "passion" without evidence; generic statements recycled across charities; ignoring the person spec; underestimating how many applicants a mission-led role attracts.
- **UK/US/EU:** the UK model mirrors public-sector statements; US non-profits want resume plus cover letter and development metrics; EU NGOs expect languages and often multi-step written tests.

## 2.21 Pharma, biotech, life sciences & regulated industries

- **Where posted:** company careers pages (AstraZeneca, GSK, Roche, Novartis and others), LinkedIn, PharmiWeb.jobs, CRO career pages (IQVIA, Fortrea, Parexel, ICON, Syneos), specialist agencies (EPM Scientific, Hays Life Sciences, Proclinical), jobs.ac.uk and company R&D pages for discovery science. Medical devices, food safety, aerospace/defence quality and finance compliance share the same "regulated" logic.
- **CV leads with:** therapeutic area and phase (e.g. oncology Phase II–III), function (regulatory affairs, clinical operations/CRA, QA/QC, pharmacovigilance, CMC, medical affairs), the regulators and systems you know (MHRA, FDA, EMA; GxP/GMP/GCP, ICH-GCP E6, eTMF/CTMS, Veeva, TrackWise), submission and inspection history, and registrations (e.g. QP eligibility). R&D roles add a publication and patent list. Two pages; academics may use a longer CV with publications in the appendix.
- **Cover letter/statement:** optional but common for R&D and regulatory roles; a short paragraph on therapeutic-area motivation is read [judgment].
- **Process:** recruiter screen → technical interview on SOPs, audits, deviations/CAPA, protocols or submissions → site or hiring-manager panel; presentations of research for scientists. Compliance gates are slow: right-to-work, qualification verification, references and sometimes occupational health. Expect 6–12 weeks, longer for GMP site roles. Agencies and CROs dominate entry-level clinical research hiring; typical entry route for CRAs is clinical trial assistant or in-house coordinator before monitoring [judgment; sources thin]. Post-Brexit UK regulatory roles ask specifically for UK submissions experience, per current listings on [PharmiWeb.jobs](https://www.pharmiweb.jobs/jobs/regulatory-affairs/united-kingdom/full-time/) [evidence-lite].
- **Outreach:** specialist recruiters are the main channel; LinkedIn contact with hiring managers is acceptable for experienced hires; scientists use conference networks and PI introductions. Keep claims verifiable: employers check training records and audit history [judgment].
- **Timing:** year-round; R&D hiring tracks funding rounds and trial starts; CRO hiring follows study awards [judgment]. A vendor blog claims over 35% of UK pharma hiring was driven by inspection findings; I could not verify it [folklore].
- **Pitfalls:** unspecific "GxP experience" with no regulator or document type; overstated QP/RP or signatory status; gaps with no explanation (regulated employers probe them); sharing confidential project details from previous employers.
- **UK/US/EU:** UK work mirrors the EU framework but now requires separate MHRA submissions; US roles want FDA-specific experience and often a degree-heavy CV; EU hubs (Switzerland, Germany, Netherlands, Belgium) expect language skills, formal certificates and EMA/national agency familiarity.

---

# PART 3 – RECRUITER OUTREACH NORMS

**Evidence warning:** almost all numbers come from outreach vendors and recruiter-side logs (employer-to-candidate). Candidate-to-recruiter response data barely exists [judgment]. Recruiter-authored advice is more useful than benchmarks.

**Channels**

- **Email** to a named hiring manager or in-house recruiter: best for tech, sales, marketing, creative, startups. Vendor logs show human-written recruiter emails get ~6% replies vs ~17% for LinkedIn messages ([Pin](https://www.pin.com/blog/recruiting-outreach-benchmark-report/)) [evidence-lite], but that is recruiter-to-candidate.
- **LinkedIn connection note:** free accounts ~200 characters with a small monthly allowance of personalised notes (reports range 3–10); Premium 300 and no cap. Sources conflict; check the editor ([Hublead](https://www.hublead.io/linkedin-character-limit)) [evidence-lite]. Often better to connect without a note, then message on acceptance.
- **InMail/DM:** LinkedIn data on tens of millions of recruiter InMails (Apr 2020–Feb 2021): 200–400 characters were 16% more likely to get replies than 800; over 1,400 characters 18% less likely; individually written beat bulk by ~20% ([SHRM, 2021](https://www.shrm.org/topics-tools/news/talent-acquisition/analysis-short-personalized-inmails-work-best)) [stale but best primary; recruiter-side].

**Content rules** (talent-acquisition expert Arabella Podmore in [Welcome to the Jungle, Dec 2024](https://www.welcometothejungle.com/en-GB/articles/messaging-recruiters-on-linkedin-tips)) [evidence-lite]: update your profile first; personalise (name, role, one reason you fit); professional tone; short; one clear call to action; attach CV/portfolio; no rapid-fire messages across platforms; wait a few days; one or two follow-ups at most.

**Shapes** [judgment]:

- *Email subject:* `Senior Data Engineer – Spark/dbt, ex-Monzo – re: Req 4821`
- *Body (80–120 words):* why this role/company; two quantified proofs; the ask; CV attached; phone and LinkedIn.
- *Connection note (≤200 chars):* "Hi Sam, I've applied for the Senior PM role at Acme and admire your work on X. Would value a quick chat on the team's priorities."

**Touches** [judgment + survey]: initial message, follow-up after 5–7 working days, final nudge 7–10 days later; max three over ~3 weeks. A 2022 US survey: 39% would accept two LinkedIn follow-ups, 25% one ([Passport Photo Online](https://passport-photo.online/blog/linkedin-recruiting/)) [stale, vendor]. Stop at any "no" or redirect.

**What gets people ignored or blocked** (recruiter-authored lists such as [The Undercover Recruiter](https://theundercoverrecruiter.com/pet-peeves-candidates-recruiters/)) [evidence-lite]: mass generic messages; asking for "a job" without naming one; sending a profile link instead of applying; inflated CVs; messaging several people at one firm; ignoring "apply via portal"; AI-pasted messages with wrong names; arguing a rejection; long cover letters by DM.

**Hiring-manager etiquette** [judgment]: message after applying and say so; cite something specific they built or posted; ask only for consideration or ten minutes; if a recruiter is named on the advert, message them instead; respect "no agencies" and auto-replies.

**AI caution:** ~20% of surveyed US hiring managers would reject AI-generated materials, a third say they spot them ([TopResume](https://topresume.com/career-advice/ai-in-hiring-survey)) [evidence-lite]. Draft from real facts; never send in volume; never automate LinkedIn.

| Sector | Outreach posture |
|---|---|
| Sales, tech, startups, creative, marketing | Welcome; specificity prized; up to three touches |
| Finance (experienced) | Via agencies/referrals; graduates: events only |
| Legal | Events, trainee contacts; no partner cold emails |
| Public sector, NHS, universities | Named informal contact only; never lobby panels |
| Trades, logistics, hospitality | Phone/visit/WhatsApp fine; speed of reply wins |
| Executive | Search-consultant relationships; brief, reciprocal |
| Academia | Expected for supervisors/PIs; formal for lectureships |

---

# PART 4 – QUICK-REFERENCE DECISION TABLE

Timelines are first application to offer [judgment] unless noted; cross-sector US benchmarks are 46.2 days first-contact-to-offer and 63.5 days posting-to-offer ([Employ](https://www.hrdive.com/news/hiring-benchmarks-report-employ-2025-more-applicants/809604/)) [evidence]. "Outreach OK" means the agent may draft a direct approach for the user to send.

| Sector | Cover letter? | CV length | Portfolio/links | Outreach OK? | Timeline | Top boards | Top dealbreakers |
|---|---|---|---|---|---|---|---|
| Software/IT | Optional | 1 (US) / 1–2 (UK) | GitHub, projects | Yes | 4–8 wks | LinkedIn, company ATS, Wellfound | No right to work; no code evidence |
| Data/AI/ML | Optional; research yes | 1–2 | GitHub, papers | Yes | 4–8 wks | LinkedIn, company ATS, lab pages | No SQL/production evidence |
| Product/UX/design | Short | 1 + portfolio | Portfolio essential | Yes | 3–6 wks | LinkedIn, Otta, company ATS | Bloated or locked portfolio |
| Marketing/comms/creative | Yes | 2 | Work samples | Yes | 3–6 wks | LinkedIn, Indeed, The Drum | Typos; vague metrics |
| Sales/BD | Optional | 2 | LinkedIn, numbers | Yes, encouraged | 2–5 wks | LinkedIn, agencies, Wellfound | Unquantified quota; spam |
| Finance/accounting | Forms; rarely letter | 1 (grad) / 2 | LinkedIn | Agencies; events for grads | 4–8 wks; grad 2–4 mths | Employer sites, LinkedIn, eFinancialCareers | Missed deadline; failed tests; qualification overstated |
| Legal | Forms or letter | 2 UK / 1 US | No | Events; agencies for laterals | TC 3–6 mths | Firm sites, Legal Cheek, LinkedIn | Wrong firm name; application limits |
| Healthcare/NHS | No; statement mandatory | Form | No | Informal contact only | 6–12 wks | NHS Jobs, trust sites | Missing essential criterion; gaps |
| Civil Service/public | Statement + behaviours | 2 + form | No | Contact point only | 6–12 wks + vetting | Civil Service Jobs, council sites | Over limit; "we"; nationality rules |
| Teaching | Application letter | 2 | No | Visit head | Jan–May peak | Teaching Vacancies, TES, Eteach | Missed resignation date |
| Academia | Statement/cover letter | Academic CV | Publications | PI/supervisor yes | 2–8 mths | jobs.ac.uk, HigherEdJobs | Missing statements; wrong deadlines |
| Engineering | Optional | 2 | Project list | Moderate | 4–8 wks | LinkedIn, Indeed, institutions | Registration/clearance unclear |
| Trades/logistics | No | 1 | Cards/tickets | Phone/visit | 2–14 days | Indeed, Find a Job, agencies | Expired card/licence |
| Hospitality/retail | No | 1 | No | In person (small) | 1–3 wks | Indeed, employer sites, Caterer.com | No availability |
| Executive | Statement to pack | 2–3 | Board bio | Search firms | 3–6 mths | Search firms, LinkedIn | Mass mailing; vague impact |
| Graduate | Form answers | 1 | LinkedIn | Events | 2–4 mths | TARGETjobs, Bright Network | Missed deadlines; tests |
| Career changer | Yes | 1–2 | Projects/certs | Yes (info chats) | 3–6+ mths | Target-sector boards | No proof of skill |
| Contractor (UK) | Covering email | 2 | Client list | Agencies | Days–2 wks | Jobserve, CWJobs, LinkedIn | Wrong IR35/rate; double submission |
| Remote-first | Yes | 1–2 | Writing samples | Yes, short | 3–6 wks | LinkedIn, WWR, Wellfound | Time-zone/country mismatch |
| Management consulting | Short motivation statement where asked | 1 (grad) / 2 (exp.) | No | Alumni chats; referrals | Grad 2–4 mths; exp. 4–8 wks | Firm portals, Bright Network, LinkedIn | Failed online test; wrong office; rejection lock |
| Charity/third sector | Statement vs person spec (mandatory) | 2 | Volunteering/trustee roles | Informal contact OK | 3–8 wks | CharityJob, Guardian Jobs, Third Sector | Generic statement; no values evidence |
| Pharma/biotech/regulated | Optional; R&D yes | 2 (+ publications) | Publications/patents | Recruiters; managers (experienced) | 6–12 wks | PharmiWeb, LinkedIn, agencies/CROs | Vague GxP claims; status overstated |

---

## Could not verify

- Day-of-week/hour effects and the first-24-hour advantage (original Talent.Works data not found).
- Candidate-to-recruiter reply rates.
- A single official Civil Service word limit; NHS Jobs/Trac scoring pages (403).
- Current LinkedIn free-tier note limits.
- UK agency CV-fishing prevalence; High Fliers figure for graduate psychometric use.
- 2027-intake dates for Big 4 and banks; UK care-sector sponsorship rules as of Nov 2026.
