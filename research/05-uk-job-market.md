# JobFerret: the UK job market (Research 05)

*Compiled 3 November 2026. This track fills the UK gap left by docs 01 to 04, which leaned US. It covers which UK sites matter, how a machine can read each one, what their terms allow, what UK adverts say and how to parse it, the law on contacting recruiters, and a weekly rhythm. The machine-readable companion is [uk-sources.json](uk-sources.json), one object per site.*

**Evidence tags.** `[live]` means I called the URL myself on 3 November 2026 and the status and fields quoted are what came back. `[own count]` is my own tally from a page I fetched. `[docs]` is the publisher's own documentation, read on the date given. `[independent]` is a third party with no product to sell. `[vendor]` is a company with something to sell. `[judgment]` is my reasoning. `[unverified]` means I could not confirm it. Where doc 01 or 02 already covers a point, I cite it (01 §C1) and do not repeat the evidence.

**No accounts were created and nothing was signed into.** I fetched one search page per board at most, with curl's default user agent. Where a site answered with a bot check, I recorded that and stopped.

---

## Ten findings that change the discovery loop

1. **Teaching Vacancies (DfE) has a free, keyless JSON API** under the Open Government Licence. `GET https://teaching-vacancies.service.gov.uk/api/v1/jobs.json` returned 4,754 school jobs over 48 pages, each already shaped as schema.org `JobPosting` `[live]`. The only extra condition is that you must not charge a fee for hiring someone you found through it. Doc 01 did not list it.
2. **NHS Jobs `search_xml` works with no key** and takes `keyword`, `location`, `distance`, `page` and `contractType` `[live]`. Every record carries `closeDate` and `postDate`. NHSBSA's own integration page now labels a "Removed External Jobs Board API", so treat this endpoint as useful but at risk of withdrawal.
3. **All five unconfirmed ATS feeds are confirmed live** (Workable, Teamtailor, Recruitee, Personio, Pinpoint), alongside Greenhouse, Lever and Ashby. Exact URL patterns and field names are in §3. Pinpoint's feed is common among UK scale-ups and exposes `compensation_minimum`/`maximum` and a free-text `compensation` that can say "Competitive".
4. **StepStone UK changed its jobseeker terms on 29 October 2026.** Clause 6.2.11 on Totaljobs and Caterer.com now bans using "any bot, script, crawler, scraper or other automated tool", explicitly including "automated means to submit applications or messages, extract data from the platform". That puts Totaljobs, CWJobs, Jobsite, Caterer and Milkround in `prohibited-automation`. The sister brands still showed an October 2025 version on the page I fetched, but they share an operator and a template, so expect them to follow.
5. **Totaljobs-family alert emails contain auto-login links.** The terms say the alert's "personalised link ... will recognise you" and pre-fill your CV on the apply form. The email parser must treat those links as credentials: extract the job ID, never store or follow the raw link, and never put it in logs.
6. **Reed is the one large UK board that is API-first and permissive.** The API takes Basic auth with the key as username `[live: 401 with WWW-Authenticate: Basic]`. It has `postedByRecruitmentAgency` and `postedByDirectEmployer` filters, and the detail endpoint returns `External Url` when the apply happens off-site. Reed's website terms contain no anti-automation clause I could find, and its `robots.txt` explicitly allows `AnthropicBot` and `GPTBot` everywhere except `/api/` and a few handlers.
7. **Agency multi-posting is the main UK duplicate problem, not cross-board syndication.** On page one of a Totaljobs "developer, London" search, 14 of 25 results named a recruitment agency or hiring marketplace as advertiser, and two pairs were the same agency posting the same title under different job IDs `[own count]`. Across Totaljobs, CWJobs and Jobsite for the same query, page one overlapped by only 1 to 7 IDs. Dedupe on (normalised title, salary band, location, agency) before company, because the company is often absent.
8. **Indeed's MCP server accepts any OAuth client in principle.** The endpoint `https://mcp.indeed.com/claude/mcp` returns 401 with protected-resource metadata pointing at `secure.indeed.com`, which advertises a dynamic client registration endpoint and the scopes `job_seeker.jobs.search`, `job_seeker.profile.read`, `job_seeker.company.details.read` `[live]`. Indeed's docs still say "available only for Claude Connector". Whether Claude Code can connect is an owner test, not something I could do without signing in.
9. **Several public-sector sources are closed to machines.** Civil Service Jobs serves a "confirm you're a real person" interstitial. GOV.UK Find a job returned 503 to both curl and WebFetch, and DWP is replacing it because the supplier contract is ending (service assessment published 14 October 2026). For both, the discovery loop should rely on the user's own alert emails.
10. **The Home Office sponsor register is a daily CSV** found through the GOV.UK Content API (last updated 2 November 2026) `[live]`. Joining employer names against it lets the screener mark "sponsor licence: yes or no" on every job for users who need a visa, which is more reliable than the advert's wording.

---

## 1. The UK sites that matter in 2026

### 1.1 Reach

There is no free, current, independent traffic ranking for UK job sites. The Semrush MCP connector in this workspace has no plan attached, so I could not pull my own figures. The best available numbers:

- Semrush's public category page put indeed.com first among UK "human resources" sites in October 2025 at 34.06 million monthly visits, with totaljobs.com second at 6.92 million ([Semrush top UK jobs sites](https://www.semrush.com/website/top/united-kingdom/jobs/), via search snippet, read 3 Nov 2026) `[vendor]`.
- Indeed's Hiring Lab reports UK postings down 11% in 2026 to date and 32% below the pre-pandemic baseline ([Hiring Lab UK](https://hiringlab.indeed.com/uk/?p=14268), via search snippet) `[vendor]`. Fewer jobs and more applicants per job make filtering and timing matter more than coverage.

`[judgment]` Rough order of usefulness for a UK candidate: Indeed and LinkedIn for breadth; Reed, Totaljobs and CV-Library as the large UK-native boards; employer careers pages and ATS feeds for direct roles; sector boards (NHS Jobs, Civil Service Jobs, Teaching Vacancies, jobs.ac.uk, CharityJob) for those sectors, where they are effectively the only channel.

### 1.2 Generalist boards

| Site | What it is | Worth the time? `[judgment]` |
|---|---|---|
| **Indeed UK** (uk.indeed.com) | Largest by traffic. Mix of direct employer posts, agency posts and scraped career-site jobs. Indeed Apply on-site, or redirect. | Yes, for coverage, but through alert emails or the MCP. Automation of apply is banned (01 §C2). |
| **LinkedIn** | Strongest for professional, tech, sales and senior roles. Easy Apply or redirect. Agency recruiters live here. | Yes, as the place recruiters look at you. Automation banned (01 §C2). |
| **Reed** (reed.co.uk) | UK-owned board, also a large agency. Heavy on agency posts, admin, finance, public sector supply, social care. Free API. | Yes. Best machine access of any big UK board. |
| **Totaljobs** | StepStone UK's flagship. Sister brands CWJobs (IT), Jobsite, Caterer (hospitality), Milkround (graduates). Searchable CV profile. | Yes for the profile and alerts. Automation banned from 29 Oct 2026. |
| **CV-Library** | Large independent board with a big CV database. Agency-heavy. Blocks non-browser clients (403). | Yes for the inbound CV database. Discovery only through alerts. |
| **Glassdoor UK** | Reviews and salary data; job listings now largely come from Indeed after Recruit Holdings folded Glassdoor's operations into Indeed in 2025 `[unverified date]`. 403 to curl. | For research on employers, not for discovery. |
| **Monster UK** | monster.co.uk redirected to monster.com, which returned 403 `[live]`. Monster's US business went through insolvency in 2025 `[unverified]`. | No. |
| **Jobsite** | StepStone brand; overlaps Totaljobs. | No, if already on Totaljobs. |
| **Adzuna** | UK-founded aggregator. Its listings point back to the source board or employer. Free evaluation API. | As an API source, yes. As a site, it duplicates what you can see elsewhere. |
| **GOV.UK Find a job** (DWP) | Free DWP board for England, Scotland and Wales, used by Jobcentre work coaches. Many entry-level, care, warehouse, cleaning and security roles; also some self-employed and commission-only posts. Being replaced. | For hourly and entry-level roles, yes. For professional roles, low yield. |
| **Google for Jobs** | Not a board; a panel inside Google Search built from `JobPosting` markup on other sites. No API (01 §C1). | Useful for a human. JobFerret should not scrape it. |

### 1.3 Tech

| Site | Notes |
|---|---|
| **CWJobs** | StepStone's IT brand. Mostly agency posts for permanent and contract roles. Same terms as Totaljobs. |
| **Technojobs** | Small UK IT board; the search URL I tried returned a 133-byte redirect page. Low priority. |
| **Jobserve** | The long-running UK contract IT and engineering board, nearly all agency posts with day rates and IR35 status. Pages returned a 75-byte script stub to curl. RSS for saved searches existed historically `[unverified]`. |
| **Welcome to the Jungle** (formerly Otta) | WTTJ bought Otta in January 2024 and retired the brand. Curated startup and scale-up roles; candidates report salary ranges now show less often ([search results](https://hotfix.jobs/alternatives/otta)) `[independent, weak]`. Its terms ban scraping ("Develop, support, or use any software, device, script, robot ... to web 'scrape'"). Apply usually redirects to the employer's ATS, so the underlying jobs are reachable through ATS feeds. |
| **cord** (cord.co, now cord.com) | UK tech marketplace where candidates message hiring teams directly. Its terms ban scraping and automated access faster "than a human can reasonably produce". Account needed. Assist only. |
| **Haystack** | UK tech jobs app with a candidate profile. Live. Terms not read. |
| **Hired** | Gone. hired.com now redirects to an LHH "Our story" page `[live]`. Drop it. |
| **Work in Startups** | Returned 403 to curl. Small. Low priority. |
| **ITJobsWatch** | Not a board but useful: median salaries and contract day rates by skill, built from UK adverts. A reference for the salary screener `[judgment]`. |

For tech roles the best direct source is the employers' own ATS boards (§3.3). Most UK scale-ups use Greenhouse, Lever, Ashby, Workable, Teamtailor or Pinpoint; Monzo and Deliveroo (Greenhouse), Octopus Energy (Lever), Synthesia (Ashby), Thought Machine and Goodlord (Pinpoint) all returned live feeds.

### 1.4 Public sector and regulated

| Site | Coverage | Machine access |
|---|---|---|
| **NHS Jobs** (jobs.nhs.uk) | NHS England and Wales, plus many GP practices and primary care networks. NHS Scotland and Northern Ireland use their own sites. | Keyless XML (§3.2). No `JobPosting` markup on the advert page I fetched `[live]`. |
| **Civil Service Jobs** | UK central government departments and agencies. | Bot-check interstitial. Alerts via account. |
| **Teaching Vacancies** (DfE) | State schools in England, free to schools. | Keyless JSON API (§3.2). |
| **TES** | Schools, independent and international. | `JobPosting` JSON-LD on adverts with `directApply: true` `[live]`. Terms not read. |
| **jobs.ac.uk** | Universities and research. | Subject-area RSS feeds exist ([jobs.ac.uk feeds](https://www.jobs.ac.uk/feeds/subject-areas/law)); the feed page I tried returned 404, so the URL pattern is unverified. |
| **LGJobs, Jobs Go Public, council sites** | English councils (LGJobs is the LGA's board); Scotland uses myjobscotland. Many councils run their own ATS (often Oleeo, Tribepad or Jobs Go Public). | LGJobs returned 200 with no `JobPosting` markup. Mostly email alerts. |
| **CharityJob, Guardian Jobs** | Charities, NGOs, some public and media roles. | CharityJob search page had no `JobPosting`; Guardian Jobs returned 403. |
| **Police and fire** | Each force and fire service recruits on its own site; national entry routes are Police Now and the College of Policing pages. policecareers.co.uk is a parked domain `[live]`. | Per-force sites; no central feed found. |

**Sector convention that affects the agent:** public-sector, NHS and charity adverts often say the advert "may close early if a high volume of applications is received". That is a reason to poll those sources twice a day and apply within days (see §5.7).

### 1.5 Graduate

Prospects (Jisc-owned careers service), TARGETjobs, Gradcracker (STEM), Milkround (StepStone) and Bright Network (Cloudflare challenge to curl). Large graduate schemes open in September to November for the next year and many close on volume (02 §2.15). The schemes themselves sit on employer ATS platforms (Oleeo, Workday, SuccessFactors, Avature), so the useful automation is a watch-list of target employers' scheme pages with opening-date reminders, not scraping the graduate boards `[judgment]`.

### 1.6 Trades and hourly

Indeed dominates. Totaljobs, CV-Library, Caterer (hospitality) and Find a job cover the rest. Temporary and warehouse work goes heavily through agencies (Adecco, Randstad, Pertemps, Blue Arrow, Staffline) and shift apps (Indeed Flex, Coople, Syft) `[judgment; app names unverified for 2026 status]`. For this group the job-seeker's constraint is often travel distance and shift pattern, not the CV, so the screener should weight location and hours more than keyword match.

### 1.7 Recruitment agencies as a channel

UK agency recruiting differs from what the US-leaning docs assume. Doc 02 §1.9 covers right-to-represent and the "two agencies, one client" problem; here is the rest of how it works for the candidate `[judgment unless tagged]`.

- **The agency submits your CV, not you.** For an agency advert there is no employer ATS to apply to. The consultant reformats your CV (often removing contact details and adding their logo) and sends it to the client. JobFerret's "apply at source" rule (01 §C2) does not apply; the action is "send CV plus a short note to the named consultant, and log the right to represent".
- **One role, many adverts.** Agencies are paid on placement, so several agencies may advertise the same client role, each under a slightly different title and with "our client" in place of the employer's name. One agency may also post the same role twice to refresh its position in results (§5.6).
- **Exclusivity.** Some roles are exclusive or retained, which the consultant may say. More often they are contingent and several agencies compete. A candidate who applies directly and through an agency to the same employer causes an ownership dispute, and the employer may reject both. Clients tend to honour the first documented submission (02 §1.9).
- **Agencies cannot charge you.** Conduct Regulations 2003, regulation 10 ([REC](https://www.rec.uk.com/recruiters/legal/legal-guide/conduct-regulations-2003)) `[docs]`.
- **Contract work language.** "Rate" means the day or hour rate. "Inside IR35" means the client has decided the engagement is employment-like for tax, so the contractor is paid through PAYE, usually via an umbrella company, and the umbrella deducts employer's National Insurance and apprenticeship levy from the rate before the worker's own tax. "Outside IR35" means the contractor can invoice through their own limited company. Medium and large clients must issue a Status Determination Statement. Since 6 April 2026 agencies share liability for umbrella-company PAYE failures (02 §2.17). The screener should compare inside-IR35 rates only with other inside rates, and should flag "umbrella only" and "PAYE or umbrella" as inside.
- **Multi-posting tools.** Agencies use Broadbean, idibu and similar to post one vacancy to many boards at once. The Find a job bulk-upload spec names Broadbean and idibu as typical senders ([findajob bulk upload](https://findajob.dwp.gov.uk/bulk-upload-specification.html)) `[docs]`. This is why the same agency advert appears on Reed, Totaljobs, CV-Library, Indeed and Jobserve within minutes.
- **Large agencies.** Hays, Michael Page, Robert Walters, Robert Half, Reed, Adecco, Randstad, and specialist tech recruiters (Harvey Nash, Sanderson, Morson, Salt, Spectrum IT among those seen today). Their own sites mostly duplicate their board posts. Agency sites run Bullhorn, Vincere, Firefish or similar; most have job alerts but no public feed `[unverified]`.

**Which sites are the same postings aggregated?** Adzuna, Google for Jobs, Glassdoor (now Indeed's feed), Jooble and similar aggregators repackage postings from boards and ATSs. Indeed itself mixes direct posts with scraped career pages. The original sources are the employer ATS, the agency's own posting, and the public-sector systems. JobFerret should treat aggregators as a way to find jobs and then resolve each one to its source before scoring and applying.

---

## 2. Machine access, terms and how applying works

### 2.1 Tiers

Tiers follow 01 §C, expanded for this file:

- **api:** a documented or open read API or feed, and nothing in the terms forbids automated reading.
- **grey:** no API, but automated reading or applying through the user's own browser session is not clearly forbidden.
- **assist:** a bot wall, or terms that are silent but the site is login-heavy; the agent prepares and the user acts.
- **prohibited-automation:** the terms explicitly ban automated access, scraping or applying.
- **unknown:** terms not read and no clear technical signal.

### 2.2 Per-site summary

Full fields (endpoint patterns, sample fields, quotes) are in `uk-sources.json`. "Inbound" means uploading a CV creates a profile recruiters can search.

| Site | Machine access | Terms on automation (read 3 Nov 2026) | Tier | Apply | Account | Inbound |
|---|---|---|---|---|---|---|
| Reed | Jobseeker API, free key, Basic auth | No anti-bot clause found; copying allowed "for your own private or domestic purposes" ([policies](https://www.reed.co.uk/policies#termsConditions)) | api | both | to apply | yes |
| Adzuna | REST API, free key | Free tier "intended for evaluating"; commercial use needs a licence ([ToS](https://developer.adzuna.com/docs/terms_of_service)) | api | redirect | no | no |
| Teaching Vacancies | Keyless JSON | OGL; no fee for hiring respondents | api | both | to apply | no |
| NHS Jobs | Keyless XML | No jobseeker clause found; NHSBSA describes feeds for embedding | api | on-site (some redirect) | to apply | no |
| Greenhouse, Lever, Ashby, Workable, Teamtailor, Recruitee, Personio, Pinpoint | Public JSON or XML per employer | Public, unauthenticated endpoints intended for career sites | api | on-site at ATS | no | no |
| Indeed | MCP (beta), OAuth via Indeed account | Bans automating Indeed Apply (01 §C2) | prohibited-automation (apply); MCP is sanctioned read | both | yes | yes |
| LinkedIn | None | User Agreement bans scraping and bots | prohibited-automation | both | yes | yes |
| Totaljobs, Caterer | None; `JobPosting` not on search pages | Clause 6.2.11, effective 29 Oct 2026, bans bots for access, extraction and applying | prohibited-automation | both | to apply | yes |
| CWJobs, Jobsite, Milkround | As above | Page fetched still showed the 31 Oct 2025 version; same operator | prohibited-automation (inferred) | both | to apply | yes |
| CV-Library | Partner-only Job View API; 403 to curl | Terms page blocked; `robots.txt` disallows `/api/` | assist | both | to apply | yes |
| Civil Service Jobs | None; human check | Terms not reachable | assist | on-site | yes | no |
| Find a job (DWP) | None public; 503 to automated clients | Not reachable | assist | redirect mostly | for some | no |
| Welcome to the Jungle | None | Bans scraping | prohibited-automation | redirect | yes | yes |
| cord | None | Bans scraping and superhuman request rates | prohibited-automation | on-site messaging | yes | yes |
| TES | `JobPosting` JSON-LD on adverts | Not read | grey | on-site | yes | no |
| Jobserve, Technojobs, Gradcracker, Bright Network, Work in Startups, Guardian Jobs | Bot walls or stubs | Not reachable | assist | mostly redirect to agency | varies | Jobserve yes |

### 2.3 How applying works, and the inbound channel

**Apply mechanisms.** Reed, Totaljobs, CV-Library and Indeed all offer on-site "quick apply" using a stored CV, and redirect to the employer when the advertiser chooses. Totaljobs' terms describe both routes: the board either stores the application for the recruiter or sends it "directly to the recruiter's own applicant management system" (clause 6.2.5). Reed's API signals the redirect case with `External Url` `[docs]`. For agency posts, quick apply sends the CV into the agency's CRM, which is fine and arguably the intended route.

**The inbound channel.** UK agencies search CV databases daily, which is why being visible matters more in the UK than the US docs suggest `[judgment]`.

- **Totaljobs family:** profiles are "set to not searchable by default" (clause 6.2.1). When searchable, recruiters see the CV and a "Last Active" date, and Totaljobs runs automated matching that pushes profiles to recruiters (6.8.2). The "Last Active" date is the decay mechanism: recruiters filter on recent activity. Totaljobs also builds an interest profile from "job specifications you have interacted with in the past 45 days" (6.8.4) `[docs]`.
- **Reed, CV-Library, Indeed, LinkedIn:** all run searchable CV databases; recruiters commonly sort by "last updated" or "last active" `[judgment; ranking logic not published]`. LinkedIn's "Open to work" (recruiters only) is the main tech and professional signal.
- **What visibility costs:** calls from agencies about roles that do not fit, and the CV circulating. For contractors it is essential. For someone wanting direct employer roles only, Reed and LinkedIn are enough.

**Rule for JobFerret** `[judgment]`: recommend two or three searchable profiles (LinkedIn plus Reed or Totaljobs or CV-Library by sector), with a CV that omits home address and date of birth. Prompt the user to refresh each profile weekly by hand (re-upload or edit one line), because the "last active" signal decays. JobFerret must not do the refresh itself on Totaljobs-family sites, since that is automated account use under clause 6.2.11.

---

## 3. Live verification

All calls made 3 November 2026 from the UK (Cloudflare reported the LHR edge) with curl's default user agent unless noted. Raw responses are in the scratch folder.

### 3.1 Keyed APIs

**Adzuna**
- `GET https://api.adzuna.com/v1/api/jobs/gb/search/1?what=developer` without a key: **400**, HTML error page `[live]`.
- OpenAPI spec at `https://developer.adzuna.com/swagger/spec/test2.json` **200** `[live]`. Search path `/jobs/{country}/search/{page}`. Parameters: `app_id, app_key, results_per_page, what, what_and, what_phrase, what_or, what_exclude, title_only, where, distance` (km, default 5), `location0..location7, max_days_old, category, sort_dir, sort_by, salary_min, salary_max, salary_include_unknown, full_time, part_time, contract, permanent, company`.
- `Job` fields: `id, title, description, created, redirect_url, adref, latitude, longitude, location{area[], display_name}, category{label, tag}, company{display_name}, salary_min, salary_max, salary_is_predicted, contract_time, contract_type`. Other endpoints: `categories, histogram, top_companies, geodata, history`. Errors: 400, 404, 410 (authorisation failed).
- `description` is a snippet, not the full advert ([search docs](https://developer.adzuna.com/docs/search)) `[docs]`. So the agent must follow `redirect_url` to get the full text.
- **`redirect_url`** points to an Adzuna tracking URL that forwards to the source posting. I could not follow one without a key, and adzuna.co.uk returned 403 to curl. `[unverified]` whether it lands on the employer, a board, or an Adzuna details page; the parser should follow it once, record the final host, and run ATS detection on that.
- **`salary_is_predicted`**: when `1`, the salary is Adzuna's estimate, not from the advert. The screener must not treat it as disclosed pay.
- **Limits.** The current terms say only "The free tier is intended for evaluating the API" and that limits "are shown in your account" ([ToS](https://developer.adzuna.com/docs/terms_of_service)) `[docs]`. The 2024 archived terms listed a default of "25 hits per minute, 250 hits per day, 1000 hits per week and 2500 hits per month" ([Wayback, 2024](https://web.archive.org/web/2024/https://developer.adzuna.com/docs/terms_of_service)) `[docs, archived]`. Plan for 250 a day until the user's dashboard says otherwise. Attribution ("Adzuna" label on displayed adverts) applies if results are published; showing them privately to one user in a terminal is not publishing `[judgment]`. Commercial use needs a licence, which matters if JobFerret is ever sold.

**Reed**
- `GET https://www.reed.co.uk/api/1.0/search?keywords=developer&locationName=London` without a key: **401**, `WWW-Authenticate: Basic` `[live]`.
- Docs ([Reed jobseeker API](https://www.reed.co.uk/developers/jobseeker), read 3 Nov 2026) `[docs]`: key as Basic-auth username, empty password. Search parameters `employerId, employerProfileId, keywords, locationName, distanceFromLocation` (miles, default 10), `permanent, contract, temp, partTime, fullTime, graduate, minimumSalary, maximumSalary, postedByRecruitmentAgency, postedByDirectEmployer, resultsToTake` (max 100), `resultsToSkip`.
- Search result fields: `jobId, employerId, employerName, employerProfileId, jobTitle, description, locationName, minimumSalary, maximumSalary`; salary omitted when hidden on the site. In practice responses also carry `date, expirationDate, applications, jobUrl, currency` `[unverified; from third-party clients, not the docs page]`.
- Detail `GET /api/1.0/jobs/{jobId}`: adds `yearlyMinimumSalary, yearlyMaximumSalary, salaryType` (per hour, day, week, month, annum), `contractType` (permanent, contract, temporary), `jobType`, `expirationDate`, `externalUrl`, `jobUrl`. The docs say an unknown ID returns "a blank job", not a 404, so check for empty fields.
- No published rate limit or API terms. Reed's website terms forbid commercial copying only. **Free key, self-serve** per third-party guides `[unverified: I did not sign up]`.
- Reed advert pages carry full `JobPosting` JSON-LD with `identifier.value` equal to the API job ID, `datePosted` and `validThrough` `[live]`.

**CV-Library.** The only official API page found is a partner-only "Job View API": "Access to the Job View API is not provided as standard" and it is "not designed for bulk download" ([CV-Library developers](https://www.cv-library.co.uk/developers/job-view-api), via search snippet) `[docs]`. No public search API. Site and terms returned 403 to curl.

**Indeed MCP**
- `POST https://mcp.indeed.com/claude/mcp` (MCP initialize) without a token: **401**, `resource_metadata="https://mcp.indeed.com/.well-known/oauth-protected-resource/claude/mcp"` `[live]`.
- That metadata names `https://secure.indeed.com` as authorisation server and scopes `job_seeker.company.details.read, job_seeker.jobs.search, job_seeker.profile.read, offline_access` `[live]`.
- The authorisation server's metadata includes `registration_endpoint: https://secure.indeed.com/oauth/v2/register` and `token_endpoint_auth_methods_supported` including `none` `[live]`, which is what MCP clients such as Claude Code use for dynamic registration. Indeed's docs still say the server "is available only for Claude Connector" ([docs.indeed.com/mcp](https://docs.indeed.com/mcp)) `[docs]`. The `/claude/` path suggests per-client endpoints.
- There is no apply scope. UK coverage is not stated; the Job Search tool takes a location, so UK use is likely `[unverified]`.
- **Owner test:** run `claude mcp add --transport http indeed https://mcp.indeed.com/claude/mcp` and sign in. If Indeed rejects the redirect URI, fall back to the claude.ai connector or alert emails.

### 3.2 Keyless public-sector feeds

**NHS Jobs**
- `GET https://www.jobs.nhs.uk/api/v1/search_xml?keyword=nurse`: **200**, `application/xml`, 10 results per page, `totalPages` 465, `totalResults` 4,642 `[live]`.
- Root `<nhsJobs>`; each `<vacancyDetails>` has `id, reference, title, description` (truncated), `employer, type` (e.g. Permanent), `salary` (free text, e.g. "Negotiable"), `closeDate` (date), `postDate` (timestamp), `url` (currently `https://beta.jobs.nhs.uk/candidate/jobadvert/{reference}`), `locations/location`.
- Filters observed working: `location=Leeds&distance=10` cut the count to 155; `contractType=Permanent` changed the count; `page=N` pages. A `sort` parameter had no visible effect `[live]`.
- `https://www.jobs.nhs.uk/api/v1/feed/all_current_vacancies.xml` returned an HTML page, not a feed.
- The advert page (`/candidate/jobadvert/W0038-26-0003`) has **no** `JobPosting` JSON-LD `[live]`.
- NHSBSA's integration page mentions open APIs and, in its navigation, "Removed External Jobs Board API" ([NHSBSA](https://www.nhsbsa.nhs.uk/node/6112)) `[docs]`. The employer "Self-Serve" XML/RSS API is documented in NHSBSA Word files ([v1.07, May 2026](https://www.nhsbsa.nhs.uk/sites/default/files/2026-05/NHS%20Jobs%20Self-Serve%20Job%20Adverts%20API%20V1.07_0.docx)) `[docs, not opened]`. No jobseeker terms restricting automated reading were found. Poll gently (a few calls per run).

**Teaching Vacancies (DfE)**
- `GET https://teaching-vacancies.service.gov.uk/api/v1/jobs.json`: **200**, JSON, 100 jobs per page, `meta.count` 4,754, `links.next` for paging `[live]`.
- Each item is schema.org `JobPosting`: `title, description, datePosted, validThrough, employmentType[], hiringOrganization, jobLocation, occupationalCategory, industry, jobBenefits, directApply, url`.
- Terms: "You are free to reuse job listing data under the terms of the Open Government Licence ... with the following exception: you must not charge any fee or commission for contacting, interviewing or hiring a respondent to your listing if you have reused Teaching Vacancies data" (last updated 9 July 2026, [terms for API users](https://teaching-vacancies.service.gov.uk/pages/terms-and-conditions#terms-and-conditions-for-api-users)) `[docs]`.
- England state schools only. I did not test query parameters, so fetch all 48 pages and filter locally (about 4 MB).

**GOV.UK Find a job (DWP)**
- `https://findajob.dwp.gov.uk/search?q=developer&w=london`: **503** to curl and to WebFetch `[live]`. I did not try to get around it.
- No public API or RSS found. The only machine route is the employer bulk upload by SFTP ([spec](https://findajob.dwp.gov.uk/bulk-upload-specification.html)); bulk-uploaded vacancies "automatically expire after 30 days unless a specific closing date is defined" `[docs, via search snippet]`.
- GOV.UK's start page now links to `jobs.service.gov.uk/jobs` ([gov.uk/find-a-job](https://www.gov.uk/find-a-job)) `[live]`; that host failed TLS from here. A GDS service assessment calls it a replacement for Find a job because "that service's commercial contract is ending" ([assessment, published 14 Oct 2026](https://www.gov.uk/service-standard-reports/dwp-jobs-and-careers-service-find-a-job-replacement-employers-beta)) `[docs]`. Re-check in 2027; a government replacement may offer an open feed like Teaching Vacancies.
- Advert URLs look like `findajob.dwp.gov.uk/details/{id}` (seen in search results).

**Civil Service Jobs.** `https://www.civilservicejobs.service.gov.uk/csr/index.cgi` returned 200, but the content is a human-verification page ("We just need to confirm you're a real person") `[live]`. No RSS or API found. `robots.txt` allows all agents except JoobleBot. Assist tier; use the site's own job alerts.

**Home Office sponsor register.** `GET https://www.gov.uk/api/content/government/publications/register-of-licensed-sponsors-workers` **200**; `public_updated_at` 2026-11-02; attachment `SP_-_Worker_and_Temporary_Worker_Web_Register_-_2026-11-02.csv` (text/csv) `[live]`. The URL changes daily, so resolve it through the Content API each time.

### 3.3 Employer ATS boards

All eight return public data without a key. Real UK or UK-hiring employers used where I could find them.

| ATS | Endpoint (verified) | Company tested | Status, count | Fields worth using |
|---|---|---|---|---|
| Greenhouse | `GET https://boards-api.greenhouse.io/v1/boards/{token}/jobs` (`?content=true` adds the description) | monzo, deliveroo | 200; Monzo 62 jobs | `absolute_url, title, location.name, first_published, updated_at, application_deadline, requisition_id, company_name, metadata, data_compliance` |
| Lever | `GET https://api.lever.co/v0/postings/{site}?mode=json` | octoenergy, palantir | 200 (cera: 404) | `text, hostedUrl, applyUrl, createdAt, categories{commitment, location, team}, workplaceType, country, descriptionPlain, lists` |
| Ashby | `GET https://api.ashbyhq.com/posting-api/job-board/{name}?includeCompensation=true` | synthesia | 200; 33 jobs | `title, location, secondaryLocations, workplaceType, isRemote, employmentType, publishedAt, jobUrl, applyUrl, compensation{compensationTierSummary, ...}` |
| Workable | `GET https://apply.workable.com/api/v1/widget/accounts/{subdomain}`; also `POST https://apply.workable.com/api/v3/accounts/{subdomain}/jobs` with a JSON filter body | huggingface | 200 both | v1: `title, shortcode, employment_type, telecommuting, department, url, application_url, published_on, created_at, city, country, locations`; v3: `results[]` with `remote, location.countryCode` |
| Teamtailor | `GET https://{company}.teamtailor.com/jobs.rss` or `{custom-careers-domain}/jobs.rss` | career.teamtailor.com | 200 RSS; 17 items | `title, description` (HTML), `pubDate, link, remoteStatus, guid, tt:locations, tt:department` |
| Recruitee | `GET https://{company}.recruitee.com/api/offers/` | vilgain | 200; 15 offers | `title, slug, careers_url, careers_apply_url, published_at, close_at, employment_type_code, remote, hybrid, on_site, location, country_code, salary, min_hours, max_hours, open_questions, options_cv, options_cover_letter` |
| Personio | `GET https://{company}.jobs.personio.de/xml` (also `.jobs.personio.com`) | tado | 200 XML | `<position>`: `id, subcompany, office, department, name, employmentType, seniority, schedule, yearsOfExperience, keywords, createdAt, salaryInformation{min, max, currencyCode, type}, jobDescriptions` |
| Pinpoint | `GET https://{company}.pinpointhq.com/postings.json` | thoughtmachine, goodlord | 200; Goodlord 6 jobs | `data[]`: `title, url, employment_type, workplace_type, location{name, city}, compensation` (text), `compensation_minimum, compensation_maximum, compensation_currency, compensation_frequency, compensation_visible, deadline_at, description, key_responsibilities, skills_knowledge_expertise, reporting_to` |

Notes:
- A wrong slug returns 404 everywhere (Personio returns 200 with an empty `<workzag-jobs/>` for some slugs), so ATS detection should confirm a non-empty response.
- Greenhouse's `first_published` versus `updated_at` is the cleanest repost signal available anywhere `[judgment]`.
- Recruitee's `open_questions` and `options_*` reveal the form's required fields before the agent opens it. That is useful for preparing answers in advance.
- Personio's `jobDescriptions` and Recruitee's `description` are full HTML, so no second fetch is needed.

### 3.4 JSON-LD on board pages

`[own count]` from one search page and up to one advert per board:

- **Search result pages** on Totaljobs, CWJobs, Jobsite, Caterer, Milkround, Reed, CharityJob and LGJobs carried JSON-LD, but only `BreadcrumbList`, `FAQPage`, `Organization` or `WebSite`; none had `JobPosting`.
- **Advert pages:** Reed and TES had full `JobPosting` (salary as `MonetaryAmount`, `datePosted`, `validThrough`; TES adds `directApply`). NHS Jobs had none. The Totaljobs advert fetch returned nothing (status 000).
- **Blocked outright (403 or challenge):** Indeed, CV-Library, Monster, Guardian Jobs, Gradcracker, Bright Network, Work in Startups and Adzuna's website.

So JSON-LD is a good way to read an advert the user has opened or pasted, not a discovery mechanism.

### 3.5 Feeds that I could not confirm

Jobserve RSS, CWJobs and Technojobs feeds, Totaljobs RSS (none known since StepStone's redesign), jobs.ac.uk RSS URL pattern, Civil Service Jobs RSS. All `verified_live: false` in the JSON.

---

## 4. Job-alert emails

Every UK board above sends alert emails, and for the closed sites (LinkedIn, Indeed without the MCP, Totaljobs family, CV-Library, Civil Service Jobs, Find a job, Jobserve, WTTJ) alerts are the only compliant feed into JobFerret. Reading your own inbox is not access to the board.

### 4.1 What each sends

`[judgment, from the sites' own help pages where cited; the link formats are from my own memory of these emails and are unverified against 2026 samples]`

| Board | Alert content | Link form | Canonical recovery |
|---|---|---|---|
| LinkedIn | 5 to 15 jobs: title, company, location, sometimes "Easy Apply" or "Actively recruiting" | `linkedin.com/comm/jobs/view/{jobId}/?trackingId=...&refId=...` | Take `{jobId}` and build `https://www.linkedin.com/jobs/view/{jobId}/` |
| Indeed | Title, company, location, salary if posted, snippet | `uk.indeed.com/rc/clk?jk={jobKey}&...` or `/pagead/clk?...` (sponsored) via email click-tracker | `jk` gives `https://uk.indeed.com/viewjob?jk={jk}`; sponsored `pagead` links need one redirect |
| Reed | Title, salary, location, employer | `reed.co.uk/jobs/{slug}/{jobId}?...utm_*` behind an ESP redirect | `{jobId}` matches the API; call `/api/1.0/jobs/{jobId}` |
| Totaljobs, CWJobs, Caterer, Milkround, Jobsite | Title, company, salary, location | **Personalised link that "will recognise you"** and pre-fills the apply form ([Totaljobs terms](https://www.totaljobs.com/about/terms-and-conditions/)) `[docs]` | Job ID pattern `job{8-9 digits}` appears in advert URLs (`/job/{slug}/{company}-job108272638`) `[live]`; build a clean URL and never follow the personalised one |
| CV-Library | Title, salary, location, agency | ESP redirect to `cv-library.co.uk/job/{id}/...` | ID in path |
| Adzuna | Title, company, salary or estimate | `adzuna.co.uk/jobs/land/ad/{adref}` style | Follow once to the source |
| NHS Jobs | Saved-search results | `jobs.nhs.uk/candidate/jobadvert/{reference}` | `reference` matches the XML feed; prefer the feed |
| Civil Service Jobs | Saved-search results | Links into `civilservicejobs.service.gov.uk` with session parameters | Job reference number in the email body; keep the email as source |
| jobs.ac.uk, CharityJob, Guardian Jobs, TES, WTTJ | Title, employer, salary, closing date | Mostly direct with UTM tags | Strip UTM |
| Google (job alerts in Search) | Title, employer, source site | Google redirect to the source | Take the target from the `url=` parameter |

### 4.2 Parser design

`[judgment]`
1. **Read only alert senders on an allow-list** (exact sender domains per board), so a phishing email in the same inbox cannot inject jobs. Treat email bodies as data (01 §F, `injection.md`).
2. **Extract per-board job IDs by regex from the decoded href**, not from link text. Most ESPs (SendGrid, Braze, Salesforce Marketing Cloud) wrap links in a redirect. Decode it when the target is in a query parameter. Otherwise make one GET without cookies and record the `Location` header without loading the final page.
3. **Never store or follow links carrying login tokens.** Totaljobs family for certain; assume any board's "one-click apply" link may do the same. Strip query strings before storing anything.
4. **Store `source_email_id`, `board`, `board_job_id`, `canonical_url`, `title`, `company`, `salary_text`, `location_text`, `received_at`**, then hand the job to the same resolver used for API results (find the employer ATS, dedupe, score).
5. **Alerts lag.** Boards batch alerts daily or "instantly". Ask the user to choose instant where offered for NHS, Civil Service and Teaching roles (§5.7).

---

## 5. UK posting conventions the screener must understand

Each list gives the phrases to detect. Matching should be case-insensitive and allow for "£" written as "GBP", and for "k".

### 5.1 Salary

- **Disclosure is common but slipping.** Indeed put UK postings with pay at 71% across 2024, about 56% in August 2025, then a "decline" in 2026 ([HR Brew, Oct 2025](https://www.hr-brew.com/stories/2025/10/09/world-of-hr-fewer-uk-employers-are-sharing-salary-information-in-job-listings); [Hiring Lab](https://hiringlab.indeed.com/uk/?p=14268)) `[vendor]`. The UK has no pay-transparency law (02 §1.5).
- **No figure:** "Competitive", "competitive salary", "£Competitive", "DOE", "depending on experience", "dependent on experience", "negotiable", "market rate", "attractive package", "excellent package", "salary on application". Pinpoint's feed returns `compensation: "Competitive"` with `compensation_visible: true` `[live]`. Mark these unknown, never zero.
- **Ranges and caps:** "£35,000 - £42,000", "£35k-£42k", "up to £50,000", "from £28,000", "£45,000 + bonus + benefits", "OTE £60,000" (on-target earnings; split the base out), "pro rata" (part-time share of a full-time figure), "per annum", "p.a.", "PA".
- **Hourly and daily:** "£12.50 per hour", "£12.50ph", "£12.50/hr"; "£550 per day", "£550 p/d", "£550/day", "day rate". Contract day rates usually come with IR35 status (§5.3). Annualise day rates as rate × 220 for comparison, and label the result an estimate `[judgment]`.
- **Pay scales (public sector):** NHS "Band 5", "Band 8a", "Agenda for Change"; Civil Service grades "AA, AO, EO, HEO, SEO, Grade 7, Grade 6, SCS" with "National" and "London" figures; teachers "MPS", "UPS", "M1-M6", "TLR"; universities "Grade 7" on a local scale; councils "Grade 6, SCP 23-25", "NJC". Map grades to numbers using the range printed in the advert, not a lookup table, because London weighting and local scales vary.
- **Aggregator estimates:** Adzuna `salary_is_predicted: 1` and Indeed's "estimated salary" are not disclosed pay.
- **Hidden in API:** Reed omits salary fields when hidden on the site.

### 5.2 Contract type and hours

`permanent`, `perm`; `contract`, `contractor`, `interim`, `freelance`; `fixed term`, `fixed-term contract`, `FTC`, "12 month FTC", "maternity cover", "secondment"; `temporary`, `temp`, "temp to perm", "ongoing temp"; `part time`, `part-time`, "x hours per week", "0.6 FTE"; `full time`; `zero hours`, "zero-hour contract", "casual", "flexible hours"; NHS `bank` (pool of staff called in as needed) and `locum`; `apprenticeship`, "Level 3 apprenticeship"; `graduate scheme`, `internship`, `placement year`; `term time only`, `TTO`; `job share`; `compressed hours`, `annualised hours`; `sessional`. Note that "FTC" with "possibility of extension" is still fixed-term.

### 5.3 IR35 and engagement route

"Inside IR35", "inside", "IR35: Inside", "deemed inside"; "Outside IR35", "outside", "IR35: Outside"; "IR35 TBC", "determination pending", "status to be confirmed"; "Umbrella", "umbrella only", "via umbrella", "PAYE", "PAYE/Umbrella", "Ltd", "Limited company", "LTD/Umbrella", "SDS" (Status Determination Statement); "CEST" (HMRC's status tool). Rules `[judgment]`: "Umbrella only" or "PAYE" means inside, even when IR35 is not named. An unstated status on a public-sector contract is usually inside, since public bodies have run the rules since 2017. Show inside and outside rates separately and never compare across them.

### 5.4 Remote, hybrid, office

"Hybrid", "hybrid working", "2 days a week in the office", "3 days on-site", "1 day per week in London", "office-based", "on-site", "site-based", "field-based", "home-based", "fully remote", "remote (UK)", "UK remote", "remote within the UK", "remote first", "WFH", "agile working" (NHS and public-sector term for partial home working), "flexible working", "occasional travel to", "Must live within commutable distance of". Feed fields: Lever `workplaceType`, Ashby `workplaceType` and `isRemote`, Workable `telecommuting`, Teamtailor `remoteStatus`, Recruitee `remote`/`hybrid`/`on_site`, Pinpoint `workplace_type`. "Remote" in UK adverts nearly always means remote within the UK for tax and right-to-work reasons; treat it as UK-only unless "anywhere" or a country list is stated `[judgment]`.

### 5.5 Right to work, sponsorship, checks and licences

**Right to work and sponsorship**
- Negative: "You must have the right to work in the UK", "must already have the right to work in the UK", "unable to offer sponsorship", "we are unable to sponsor visas", "visa sponsorship is not available", "no sponsorship", "this role does not offer sponsorship", "we cannot sponsor", "applicants must not require sponsorship".
- Positive: "visa sponsorship available", "we can sponsor", "Skilled Worker sponsorship", "Skilled Worker visa", "Certificate of Sponsorship", "CoS", "Health and Care Worker visa", "sponsorship may be available for the right candidate", "we hold a sponsor licence".
- Nationality restrictions: "UK nationals only", "sole UK national", "British citizen", Civil Service "Nationality requirements" (reserved posts), "dual nationals may not be eligible".
- **Rule:** if the user needs sponsorship, require both a positive phrase (or no negative phrase) and a match on the sponsor register (§3.2). Thresholds changed in 2025 and may change again, so the agent must not judge eligibility itself; it should say "this employer holds a licence; check whether the role meets current Skilled Worker rules on gov.uk" `[judgment]`.

**Criminal record checks**
- "Basic DBS", "Standard DBS", "Enhanced DBS", "enhanced DBS with barred list check", "enhanced DBS (child and/or adult workforce)", "subject to a satisfactory DBS", "DBS update service", "regulated activity", "safer recruitment", "KCSIE" (Keeping Children Safe in Education), "exempt from the Rehabilitation of Offenders Act 1974".
- Scotland: "PVG", "Protecting Vulnerable Groups scheme", "Disclosure Scotland". Northern Ireland: "AccessNI".
- These are not knock-outs for most users, but the agent should note them and never answer criminal-record questions on the user's behalf.

**Security clearance**
- "BPSS", "Baseline Personnel Security Standard", "CTC", "Counter Terrorist Check", "SC", "Security Check", "SC cleared", "active SC", "eSC", "DV", "Developed Vetting", "eDV", "NPPV" (police vetting, levels 2 and 3), "List X", "must be eligible for SC", "willing to undergo SC", "5 years UK residency" (typical for SC), "10 years" (typical for DV).
- "Active", "current" or "live" clearance is a hard knock-out if the user has none. "Eligible" or "willing to undergo" is not.

**Driving and licences**
- "full UK driving licence", "full clean UK driving licence", "clean licence", "no more than 6 points", "own vehicle", "access to a vehicle", "business insurance", "car allowance", "company car", "willing to travel".
- Vocational: "Cat C", "Cat C+E", "Class 1", "Class 2", "HGV", "7.5t", "C1", "Driver CPC", "digi card" (tachograph card), "ADR". Other cards: "CSCS card", "SIA licence" (door supervision, security), "forklift licence" (counterbalance, reach), "IPAF", "PASMA", "Gas Safe", "18th Edition".

### 5.6 Ghost jobs, duplicates and agency multi-posting

Doc 02 §1.7 has prevalence and general signals. UK-specific additions:

- **Agency multi-posting** `[own count]`. On page one of Totaljobs "developer, London" (25 results), 14 named an agency or hiring marketplace as the advertiser. Two cases were the same advertiser posting the same title twice with different IDs: two "lead software developer" adverts from one tech recruiter (job IDs 108047514 and 108089099), and two "full stack developer" adverts from a hiring marketplace with IDs three apart (108212596 and 108212599). A cross-site check on the same query found only 1 to 7 shared IDs between Totaljobs, CWJobs and Jobsite page one. So the sister brands carry different first pages, while one agency vacancy can surface as several adverts.
- **Dedupe key** `[judgment]`: normalise the title (strip "Senior/Lead" only for clustering, not scoring), salary band rounded to £5k or day rate to £25, location to town, plus advertiser. Then cluster across advertisers on title, band, location and a description similarity score above about 0.8. Show the cluster as one job with "advertised by 3 agencies"; the user picks one agency, and the right-to-represent log records it.
- **Signals that the employer is hidden:** "our client", "my client", "a leading", "a well-known", "household name", "an award-winning", "a global", "confidential", employer field equal to the agency's name. Not ghost signals on their own, but combined with "Competitive" and generic duties they raise the risk of a CV-collecting advert (02 §1.7).
- **Urgency phrases:** "immediate start", "start ASAP", "urgent requirement", "interviews this week". Genuine for temp and contract work; on permanent roles from agencies they are a weak "evergreen advert" signal.
- **Reposting cadence:** Find a job bulk uploads expire after 30 days unless a closing date is set, so agency posts reappear on a roughly 30-day cycle. Greenhouse's `first_published` against `updated_at`, Recruitee `published_at`, Lever `createdAt` and NHS `postDate` give a first-seen date. Store first-seen per cluster and flag anything older than 45 days that is still being re-advertised.
- **Low ghost risk:** NHS Jobs, Civil Service Jobs, Teaching Vacancies, councils and universities. Their adverts carry closing dates and references, and the process is audited. The risk here is different: internal candidates, and adverts that close early.
- **Scam markers seen on Find a job and Indeed:** "self-employed", "commission only", "no experience needed, earn £", "work from home earning", requests to pay for training or a DBS check up front (an employer may ask you to pay for a basic DBS, but agencies cannot charge work-seekers fees for finding work).

### 5.7 When UK postings go live and how fast to apply

- No primary UK data on posting day or hour was found. Doc 02 §1.1's rule holds: apply within about seven days for good matches, and never trade tailoring for speed.
- **Exceptions where speed decides** `[docs and judgment]`: adverts that say "may close early", "we reserve the right to close this vacancy early", or "if we receive a high number of applications". These are common in NHS, charity, council and some Civil Service adverts. Graduate schemes that "recruit on a rolling basis" are the same. Temporary and hourly roles fill in days.
- NHS feed `postDate` and `closeDate` give the window directly. In today's sample a GP-practice nurse role was posted 16 October and closed 6 November, a three-week window.
- Civil Service adverts close at a stated time (often 23:55) on the closing date; the agent should treat that as a hard deadline and finish a day early.

---

## 6. Recruiter outreach in the UK

### 6.1 Who to contact and how

`[judgment unless tagged; builds on 01 §E and 02 §1.9-1.10]`

- **Agency recruiters.** Contact is expected; it is how they work. The named consultant on the advert is the right person. A short email with the CV attached, or a call, gets faster replies than LinkedIn for a live role. LinkedIn messages work for building a relationship with a specialist recruiter in your field. Recruiters reply when you match a live role and often not otherwise; silence is not rejection of you, only of the fit. Ask which client before agreeing to be put forward (02 §1.9).
- **In-house talent acquisition.** Apply through the ATS first, then one LinkedIn connection note or email naming the role and one specific reason you fit. TA teams in large UK employers are measured on process compliance, so do not ask them to bypass it.
- **Hiring managers.** In startups, tech, sales, creative and small firms, a short note after applying is welcome. In NHS, Civil Service, councils, schools and universities, do not contact the panel before shortlisting; the process is scored and contact can count against you. Named contacts in those adverts are for "informal enquiries", which is a real invitation: one specific question about the role is fine and often useful for writing the supporting statement.
- **Channel.** LinkedIn for people whose email you do not have; email where the advert or agency site publishes one. Free LinkedIn accounts get a small monthly allowance of personalised invitation notes (01 §E).

### 6.2 The law, for one person looking for work

**PECR 2003, regulation 22** ([legislation.gov.uk](https://www.legislation.gov.uk/uksi/2003/2426/regulation/22)). You must not send unsolicited direct-marketing email to an *individual subscriber* without their consent, apart from the soft opt-in for existing customers. Regulation 22 "does not apply to corporate subscribers" (ICO, [business-to-business marketing](https://ico.org.uk/for-organisations/direct-marketing-and-privacy-and-electronic-communications/business-to-business-marketing/)) `[docs]`. A named work address at a company (jane.smith@agency.co.uk) belongs to a corporate subscriber. Sole traders and some partnerships are individual subscribers, and many one-person recruitment businesses are sole traders (01 §E).

**Regulation 23** applies to every subscriber, corporate included: do not disguise or conceal your identity, and give a valid address for opt-out requests. That is cheap to follow.

**Is an application "direct marketing"?** Direct marketing is "the communication (by whatever means) of advertising or marketing material which is directed to particular individuals" (Data Protection Act 2018, s.122(5), as used by the ICO, [key concepts](https://ico.org.uk/for-organisations/direct-marketing-and-privacy-and-electronic-communications/guidance-on-direct-marketing-using-electronic-mail/key-concepts-for-direct-marketing-using-electronic-mail/)). `[judgment]` A one-to-one email about an advertised vacancy is an application, not advertising. A speculative "are you hiring?" note to one hiring manager is close to the line but is still a personal approach, not material promoting goods or services. A contractor emailing their day rate and availability to fifty agencies is marketing their services, and if any of them are sole traders PECR consent rules bite.

**UK GDPR.** Holding a recruiter's name and address is processing personal data. The lawful basis is legitimate interests (Article 6(1)(f)), which needs a short balancing test: a job seeker contacting a recruiter at their work address about work is the kind of contact recruiters expect, so it passes easily `[judgment]`. Article 14 requires telling someone where you got their data if you did not get it from them, at the latest at first contact. Article 21(2) and (3) give an absolute right to object to direct marketing; outside marketing, an objection must still be respected unless you have compelling grounds, which a job seeker will not have.

**Fines.** The Data (Use and Access) Act 2025 raised PECR penalties to UK GDPR levels from 5 February 2026 (01 §E). These are aimed at bulk marketers; the practical risk to one job seeker is a complaint, a ruined relationship, or a LinkedIn restriction.

**What the user must do** (JobFerret enforces these):
1. Send from their own name and real address, and sign with their name and phone or LinkedIn.
2. Say where they found the address in the first message ("I saw your name on the Reed advert for...").
3. Make stopping easy, in plain words ("If this isn't useful, just say and I won't follow up").
4. Stop when asked, and add the person to a permanent suppression list.
5. Keep a note per contact: address, where it was found, date, messages sent, any objection. Delete after the retention period (01 §E sets 12 months).

**What they must not do:**
- Bulk or templated sends to lists. JobFerret's limit stays at five new contacts a day (01 §E).
- Use scraped, bought or guessed addresses. Only use published ones or addresses the person gave.
- Pretend to be an employer or a recruiter, or write as if a referral exists when it does not.
- Email personal addresses found through private social profiles.
- Keep chasing: at most one follow-up after the first message (01 §E; 02 §1.6 for timing).

LinkedIn messages are governed by LinkedIn's own terms first. Whether a platform direct message counts as "electronic mail" under PECR is not settled in ICO guidance I found `[unverified]`, so apply the same five rules there.

---

## 7. Cadence

Doc 02 §1.1, 1.2 and 1.6 set the evidence: apply within about a week, quality beats volume (8.1% interview rate at 11 to 20 applications against 2.9% at over 100, Huntr), follow up once after 7 to 10 working days. 01 §C2 sets the hard limits: 10 to 15 tailored applications a day at most, cap 25. UK adjustments `[judgment]`:

**Daily (automated, about 07:00)**
- Pull Reed, Adzuna (about 20 queries, inside the 250-a-day evaluation budget), the ATS watch-list, Teaching Vacancies and NHS Jobs where relevant.
- Parse overnight alert emails from LinkedIn, Indeed, Totaljobs family, CV-Library, Civil Service Jobs and Find a job.
- Dedupe, resolve to source, score, and produce a digest of the top 5 to 10 with reasons and closing dates.
- For NHS, charity and council roles marked "may close early", run a second pull at about 13:00 and flag same-day items.

**Daily (user, 30 to 90 minutes)**
- Review the digest and pick two or three to apply for.
- Reply to agency calls and emails the same day; agencies move on fast.

**Weekly volume by applicant type**
- Private-sector professional: 8 to 15 tailored applications.
- Public sector or NHS: 2 to 5, because a supporting statement mapped to the person specification takes two to four hours to do well.
- Contract IT: unlimited quick replies to agencies on genuine matches, but no more than one agency per client role.
- Hourly and temp: 10 to 20, with location and shift fit doing most of the filtering.

**Weekly (Friday)**
- Send follow-ups due under 02 §1.6.
- Review the right-to-represent log for clashes.
- Refresh each searchable CV profile by hand.
- Look at the funnel by source and role family (which boards produced replies).
- Prune alert searches that produce only noise.

**Seasons.** January to March and September to November are strongest; August and late December are slow (02 §1.1). Graduate schemes open in September to November. Teaching posts for September are advertised mainly from January to May, with resignation deadlines of 31 October, 28 February and 31 May. NHS and Civil Service recruit year-round, with a dip before the financial year end.

---

## Unverified items and decisions for the owner

**Unverified**
- Adzuna's current free-tier limits (the 2024 terms said 250 calls a day) and where `redirect_url` lands.
- Whether the Reed jobseeker key is still self-serve and free (I did not sign up), and the extra search fields third-party clients report.
- Whether Claude Code can use the Indeed MCP directly via dynamic registration.
- Jobserve, CWJobs, Technojobs, Totaljobs and Civil Service Jobs RSS; the jobs.ac.uk feed URL pattern; Teaching Vacancies query parameters.
- The terms of CV-Library, Glassdoor, Jobserve, Gradcracker, Bright Network, TES, jobs.ac.uk and CharityJob (blocked or not found). CWJobs, Jobsite and Milkround are inferred from Totaljobs.
- Alert-email link formats in §4.1, which are from memory of these emails, not from 2026 samples.
- Monster UK and Glassdoor corporate changes in 2025.

**Decisions for the owner**
1. **Adzuna licensing.** Personal use fits the evaluation tier. If JobFerret is ever distributed for others to run with their own keys, each user registers their own key, which keeps it personal use. If it is ever sold as a service, Adzuna requires a licence.
2. **Indeed MCP test.** Try connecting it in Claude Code with your own Indeed login. If it works, Indeed discovery becomes API-based; if not, it stays on alert emails.
3. **Searchable profiles.** Which two or three to make searchable (my default: LinkedIn plus Reed for most roles; add CV-Library or Totaljobs for agency-heavy sectors; Jobserve for contract IT).
4. **Totaljobs family.** With the 29 October 2026 terms, JobFerret should not even fetch adverts from these sites automatically. Agree that StepStone jobs reach the skill only through alert emails or a URL the user pastes, and that the user clicks apply.
5. **Sponsor register join.** Only needed if any user requires a visa; it is a 20 MB daily download.
6. **Public-sector priority.** If NHS or teaching roles are in scope, build `discover_nhs.py` and `discover_teaching_vacancies.py` in Phase 2 ahead of Adzuna, since both are keyless and are the only channel for those sectors.
