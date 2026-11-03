# Format rules

One section per format: the limit, the spine, how to open and close, and two before/after pairs. The pairs come from 04 §6. Read `voice.md` first for the rules behind them and the checklist to run afterwards.

## Contents

1. Limits at a glance
2. Cover letter
3. Recruiter cold email
4. LinkedIn connection note
5. Hiring-manager message
6. CV profile
7. Application-form answers (including UK Civil Service and NHS)
8. Follow-up email
9. Thank-you note

## Read this before using any example

Every "after" uses invented people and organisations (Sam Adeyemi, Calder Valley Homes, Ferncroft Energy, Lumen Tickets). Each specific stands for something the user has to supply. Never copy a figure, name or story from this file into a real draft. If a draft needs a detail the ledger or the interview does not hold, write `[CONFIRM: the question]` and ask (04 §1 rule 1).

Where the employer bans AI-written content (`disclosure.md`, coach mode), the "after" texts show the standard to aim for. Use them to explain what good looks like. Do not hand them over as text to paste.

## 1. Limits at a glance

`scripts/voice_lint.py` enforces the hard limits (ARCHITECTURE §4). Aim for about 10% under a word limit so a different counting rule cannot fail a draft. If the linter's count differs from yours, the linter wins.

| `--format` | Hard limit | Target | Unit |
|---|---|---|---|
| `cover-letter` | 150 to 400 | 300 to 350 for a full letter, 150 to 250 for a short one (`sectors-quick-reference.md` §4); three to five uneven paragraphs | words |
| `email` | 120 maximum | 60 to 110 | words |
| `linkedin-note` | 300 maximum | 130 to 220 | characters, spaces included |
| `hiring-manager` | 120 maximum | 60 to 110. 04 §6.4 allows up to 150, but the linter caps at 120 | words |
| `cv-profile` | 80 maximum | 40 to 70 | words |
| `cv-bullets` | none | see `references/cv/rewrite-rules.md` | |
| `form-answer` | the form's limit, passed as `--max-words N` | 90% to 100% of N for a scored question | words |
| `follow-up` | none enforced | 40 to 90 (04 §6.7) | words |
| `thank-you` | none enforced | 50 to 120 (04 §6.8) | words |

Every format also gets checks 2, 3, 8, 11 and 12 from `voice.md`: no banned words, rationed items at most once, no template opener or closer, no formatting tells, no agent tics. The pairs below show what that looks like in practice.

## 2. Cover letter

**Limit:** 150 to 400 words, three to five paragraphs of uneven length. Use the short end when the sector table says Optional or Short. No bullets, bold or headers.
**Spine:** what I have done (with a number), why you specifically (something unswappable), what happens next.
**Open with** the strongest fact. **Close with** a specific offer or ask, then the sign-off from the profile.
Name the reader if you can find them. "Dear Hiring Manager" is acceptable when you cannot, once. Do not restate the CV.

**Opening**
- Before: "I am writing to express my interest in the Data Analyst position at Ferncroft Energy. As a passionate, results-driven professional with a proven track record of leveraging data, I am excited to contribute to your innovative team."
- After: "Last year I got the average wait on our empty homes down from 41 days to 29, mostly by building one dashboard and persuading fourteen housing officers to open it on Monday mornings. Your advert mentions a smart-meter fault backlog, which sounds like the same kind of problem."
- Cut: the writing-about-writing opener and six banned phrases. Added: a number, a timeframe, a link to the advert.

**Why us**
- Before: "Ferncroft's commitment to sustainability deeply resonates with me, and I am inspired by your mission to transform the energy landscape."
- After: "I've been a Ferncroft customer since 2023. When my meter stopped sending readings last winter it took three calls to fix, and the third person told me the fault list was 'still a spreadsheet'. I'd like to be the one who sorts that spreadsheet out."
- Cut: "commitment to", "deeply resonates", "transform the energy landscape". Passes the swap test, because only a customer could write it. The customer story must be the user's own.

## 3. Recruiter cold email

**Limit:** 120 words maximum.
**Spine:** why them, one proof point, one ask. Subject line in sentence case naming the role or the reason. Link to a profile or portfolio, not an attachment.
**Open with** the reason for writing. **Close with** an easy yes or no and a plain sign-off: name, phone, one link.

**Subject lines**
- Before: "Exciting Opportunity: Passionate Data Professional Seeking New Challenges!" or "Quick Question"
- After: "Data analyst, housing and energy background (Leeds)" or "Your Ferncroft data analyst role" or "Referred by Priya Shah"
- Cut: Title Case, the exclamation mark, self-labels, vague hooks. Added: the role, the reason, a named referrer.

**Full email**
- Before: "I am a highly motivated data professional with five years of experience leveraging analytics. I believe I would be a valuable asset to any organisation and would love to explore potential opportunities. Please find my CV attached!"
- After:

> Hi Hannah, you posted the Ferncroft data analyst role on Tuesday, so I'm guessing it's yours to fill.
>
> I'm a data analyst at Calder Valley Homes in Halifax. Short version: I built the dashboard that cut our empty-home wait from 41 to 29 days, and found £38k of duplicate invoices along the way.
>
> I've applied through the site. Would a 10-minute call this week help you decide whether to put me forward?
>
> Thanks,
> Sam
> 07700 900123 · linkedin.com/in/samadeyemi

- Cut: "highly motivated", "leveraging", "valuable asset to any organisation" (which fails the swap test in its own wording), the attachment. Added: the reason for writing, two figures, one ask. About 78 words.

## 4. LinkedIn connection note

**Limit:** 300 characters maximum, spaces included. Count characters, not words.
**Spine:** how you know of them, why you are connecting. No pitch, no CV, no "pick your brain". The user clicks send (gate G2).
**Open with** the specific link between you: the application, their post, the referrer, the event. **Close** when the reason is given. A sign-off wastes characters.

**Recruiter**
- Before: "Hi Hannah! I'm a passionate data professional excited to connect with like-minded individuals in the energy space. I'd love to explore synergies! 🚀"
- After: "Hi Hannah, I applied for the Ferncroft data analyst role this week. Connecting so you've got a face to the name. I'm in Leeds and can come in any day." (150 characters)

**Hiring manager, after their post**
- Before: "Hi Tom, I really enjoyed your insightful post about data quality. It truly resonated with me. I'd love to connect and learn more about your journey!"
- After: "Hi Tom, your post about meter reads arriving with the wrong timestamps made me laugh. We had the same thing with repair dates. I'm applying for your analyst role and wanted to say hello first." (192 characters)

- Cut across both: "passionate", "excited", "synergies", "insightful", "resonated", "journey", emoji, exclamation marks. Added: the post's actual content, the application, a matching story. The post must be real and the user must have read it.

## 5. Hiring-manager message

**Limit:** 120 words maximum. Sent after applying, not instead of it.
**Spine:** something specific to their team, one result, one easy question.
**Open with** a fact about the application or their work. **Close with** the question. No sign-off beyond the name.

**After applying**
- Before: "I recently applied for the Data Analyst role and wanted to reach out to express my strong enthusiasm. I am confident my skills make me an excellent fit for your team."
- After: "I applied for your data analyst role yesterday. One thing my CV doesn't show: I've spent two years getting people who hate spreadsheets to use a dashboard, which I suspect counts for as much as the SQL in your team."
- Cut: "reach out", "strong enthusiasm", "excellent fit". Added: something the CV cannot say, a limit on the claim ("I suspect").

**A question about the role**
- Before: "Could you please provide some additional insight into the key responsibilities and day-to-day expectations of the role?"
- After: "Is the fault-backlog work mostly reporting, or would the analyst be fixing the data at source as well?"
- Cut: "additional insight", "key responsibilities". Added: a question that only someone who read the advert would ask.

## 6. CV profile

**Limit:** 80 words maximum; aim for 40 to 70. Three or four lines. Dropping "I" is the UK convention; either works. The paragraph carries `[F...]` citations like the rest of the CV (`ledger_check.py`).
**Spine:** what you do, one or two lines of proof, what you are after.
**Test:** if it could go on a colleague's CV unchanged, rewrite it. Bullet-level rules are in `references/cv/rewrite-rules.md`.

**Data analyst**
- Before: "Results-driven data analyst with a proven track record of leveraging cutting-edge tools to deliver actionable insights. Passionate about data storytelling and adept at collaborating with cross-functional stakeholders in fast-paced environments."
- After: "Data analyst at a 6,000-home housing association. Built the repairs dashboard that cut empty-home turnaround from 41 to 29 days, and found £38k in duplicate contractor invoices. Power BI, SQL, Excel. Looking for a larger dataset and a team where analysts fix data at source."
- Cut: self-labels, "proven track record", "leveraging", "cutting-edge", "passionate", "adept", "fast-paced". Added: a setting, two figures, the tools, an aim.

**Nurse moving into operations**
- Before: "Compassionate and dedicated healthcare professional with extensive experience in fast-paced clinical settings, seeking to leverage transferable skills in a dynamic operational role."
- After: "Band 6 ward sister, eight years in acute medicine on a 30-bed ward. Ran the ward rota for three years and cut agency shifts from 40 a month to 12. Moving into NHS operations or patient-flow management."
- Cut: "compassionate and dedicated", "extensive experience", "leverage", "dynamic". Added: the band, the ward, a figure, a direction.

## 7. Application-form answers

**Limit:** the form's own limit, passed as `--max-words N`. Civil Service behaviour answers are commonly capped at 250 words; check the advert.
**Spine:** answer the question asked, in the order asked. Use the employer's criterion wording once, so the shortlister can tick it off. In UK public-sector forms use STAR order with most of the words on Action, and "I" rather than "we". Labels are optional and prose usually reads better.
**Open with** the situation or the criterion. **Close** on the result, plus one honest reflection or gap if there is room.
**Register:** drop most contractions on Civil Service and NHS forms to match. Zero exclamation marks and zero rhetorical questions. At least one specific per 50 words.
**Disclosure:** check the employer's AI policy before drafting (`disclosure.md`). Civil Service and some NHS trusts mean coach mode.

**UK Civil Service behaviour: "Delivering at Pace" (250 words, STAR)**
- Before (excerpt): "I spearheaded a transformative initiative to streamline our void management process, leveraging data-driven insights to foster collaboration across stakeholders. Moreover, I proactively identified key bottlenecks and implemented robust solutions, which serves as a testament to my commitment to excellence."
- After (242 words):

> In April 2024, 63 homes at Calder Valley Homes were empty and waiting for repairs, and the average wait before re-letting was 41 days. Every empty week cost about £95 in lost rent, and families on our waiting list were in temporary accommodation. My manager asked me to find where the time was going and bring the average down within six months.
>
> I matched a year of job records from our housing and repairs systems, which used different property codes. The repairs themselves were not the main delay. Homes waited an average of nine days for the first inspection to be booked, because requests went to a shared inbox that nobody owned. The repairs manager and I agreed inspections would be booked within two working days, with one named person responsible.
>
> I built a Power BI dashboard listing every empty home by days waiting, oldest first. I ran four half-hour sessions so all 14 housing officers could use it, and every Monday I went through it with the repairs manager and chased any home over 20 days. When the contractor's data feed failed in July, I updated the figures by hand for three weeks so the Monday meeting kept going.
>
> By October the average wait was 29 days, and it has stayed under 31 since. If I did it again, I would fix the inspection booking first and build the dashboard second, because that is where most of the time came from.

- Cut: eleven banned words and phrases and the self-assessment. Added: dates, numbers, the named tool, what the candidate personally did, a setback and an honest reflection. Contractions dropped for register.

**NHS supporting statement paragraph** (criterion: "Experience of analysing and presenting data to improve services")
- Before: "I have extensive experience in analysing and presenting data to improve services. I am passionate about using data to drive meaningful change and enhance patient outcomes, and I am adept at presenting complex information to stakeholders in a clear and concise manner."
- After: "Experience of analysing and presenting data to improve services. At Calder Valley Homes I produce the weekly performance pack for the senior leadership team and five area managers. In 2024 I analysed a year of repairs data and found that most of the delay in re-letting empty homes came from inspection booking, not the repairs. I presented this to the repairs manager on a one-page chart, we changed the booking process, and the average wait fell from 41 to 29 days. I have not worked with patient data yet. The closest is tenant vulnerability data, which taught me to handle sensitive records under UK GDPR and to check who really needs to see what."
- Cut: "extensive experience", "passionate", "drive meaningful change", "enhance", "adept", "clear and concise manner". Added: the criterion as a signpost, an honest gap and how it is bridged. Work down the person specification this way, one criterion at a time.

Other question types follow the same logic. "Why do you want to work for us?" passes the swap test only with a first-hand detail, such as a product the user has used or something of the employer's they have read. "Tell us about a mistake" names the mistake, what the user did the same day and the check that now prevents it (04 §6.6).

## 8. Follow-up email

**Limit:** none enforced; aim for 40 to 90 words, in the same thread.
**Spine:** one new fact or one clear question. Wait 7 to 10 working days after applying, or a day or two past any date they gave.
**Open with** the date or the thing you are following up. **Close** on the question.

**No response after applying**
- Before: "I just wanted to follow up on my application and reiterate my strong interest in the position. I remain very excited about the opportunity and would love to hear about next steps!"
- After: "Hi Hannah, I applied for the data analyst role on 14 October. Since then our dashboard has gone live in a second region, so the 41-to-29-day figure now covers 9,000 homes. Is the role still open?"
- Cut: "reiterate", "strong interest", "excited", the exclamation mark. Added: the application date, a new fact, a question that has a yes or no answer. The new fact must be real.

**After interview, past their date**
- Before: "I hope you are well. I wanted to touch base regarding the status of my candidacy following our recent interview."
- After: "Hi Tom, you mentioned you'd decide by Friday, so I'm checking whether there's any news. Still very keen."
- Cut: the pleasantry, "touch base", "candidacy". Added: the date they gave. "Very keen" spends the one allowed feeling word.

## 9. Thank-you note

**Limit:** none enforced; aim for 50 to 120 words, sent the same or next working day.
**Spine:** one specific moment from the conversation, plus anything you would answer better now.
**Open with** the moment. **Close** with a plain line about them or the work, not a request.
Thank-you notes are less expected in the UK than the US, so keep it short. Skip it after a formal anonymised panel such as a Civil Service board (04 §6.8).

**Opening**
- Before: "Thank you so much for taking the time to meet with me today. I truly enjoyed learning more about the role and your amazing team!"
- After: "Thanks for this morning, Tom. I hadn't realised how much of the backlog comes from the old Elster meters."
- Cut: "so much", "truly", "amazing", the exclamation mark. Added: one thing learned in the room.

**Middle**
- Before: "Our conversation further solidified my enthusiasm for the position, and I am more confident than ever that my skills align perfectly with your needs."
- After: "I gave you a vague answer on the timestamp problem. A better one: I'd start by counting how many reads arrive out of order each day, before anyone fixes anything, so we know whether it's 2% or 20%."
- Cut: "solidified my enthusiasm", "more confident than ever", "align perfectly". Added: a better answer to a real question. Use it only if the user did give a vague answer. Never invent a moment.
