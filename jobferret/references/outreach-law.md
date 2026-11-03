# Outreach and the law: the plain rules for one job seeker

A summary of how UK law applies when a job seeker writes to recruiters and hiring managers, taken from research 05 §6.2 (which cites the ICO guidance and the legislation) with 01 §E and 02 Part 3 for the limits. It is a summary for a careful individual, not legal advice. If the user is doing something unusual (a recruitment business of their own, contracting through a limited company and marketing their services widely), they should check the ICO guidance or take advice.

## The rules

1. Write one-to-one about a real job or a real reason. Never send to a list.
2. Use only addresses the person or their employer published, or that the person gave you. No scraped, bought or guessed addresses.
3. Send from your own name and real address; sign with your name and a phone number or LinkedIn link.
4. Say where you found their address in the first message.
5. Make it easy to say no, in plain words, and stop the moment they do.
6. Put anyone who objects on the permanent do-not-contact list (`outreach.py` does this on any "no").
7. Keep a short record per contact: address, where it came from, date, messages, any objection. Keep it no longer than it is useful (about a year), but keep the do-not-contact entry.
8. One follow-up, then stop. JobFerret allows two touches and five new contacts a day.
9. Never pretend to be someone else, or imply a referral that does not exist.
10. LinkedIn's own terms come first on LinkedIn: the user sends, and nothing is automated.

## Why each rule is there

**Marketing email rules (PECR 2003, regulation 22).** Regulation 22 bars unsolicited direct-marketing email to *individual subscribers* without consent. It does not apply to corporate subscribers, so a named work address at a company (jane.smith@agency.co.uk) is outside it. Sole traders and some partnerships count as individual subscribers, and many one-person recruitment businesses are sole traders (05 §6.2, ICO business-to-business guidance).

**Is a job enquiry "marketing" at all?** Direct marketing means advertising or marketing material directed to particular people (Data Protection Act 2018 s.122(5), as the ICO uses it). A one-to-one email about an advertised vacancy is an application, not advertising. A speculative note to one hiring manager is close to the line but is still a personal approach. A contractor emailing their rate and availability to fifty agencies is marketing their services, and if any are sole traders the consent rule applies (05 §6.2, judgment). That is why rule 1 forbids lists and why JobFerret caps new contacts at five a day (01 §E).

**Identity (PECR regulation 23).** Applies to every subscriber, corporate included: do not hide who you are, and give a working address for opt-outs. Rules 3 and 5 cover it at no cost.

**UK GDPR.** Keeping a recruiter's name and address is processing personal data. The lawful basis is legitimate interests (Article 6(1)(f)). A job seeker contacting a recruiter at their work address about work is contact recruiters expect, so the balancing test passes easily (05 §6.2, judgment). Article 14 asks you to tell people where you got their data, at the latest at first contact: rule 4. Article 21 gives an absolute right to object to direct marketing, and outside marketing an objection must still be respected unless there are compelling grounds, which a job seeker will not have: rules 5 and 6. Records kept no longer than needed: rule 7; 01 §E suggests 12 months.

**Scraped and guessed addresses.** Using only published or given addresses keeps the processing within what the person could expect, and keeps the user off spam blocklists. Guessing firstname.lastname@ also means writing to people who never published an address (05 §6.2). `outreach.py verify` never probes mail servers for the same reason.

**Fines.** The Data (Use and Access) Act 2025 raised PECR penalties to UK GDPR levels from 5 February 2026 (05 §6.2, 01 §E). They are aimed at bulk marketers. For one job seeker the practical risks are a complaint, a damaged relationship with a recruiter, or a LinkedIn restriction.

**LinkedIn.** LinkedIn's User Agreement governs messages there first, and it prohibits automation (G2). Whether a platform message counts as "electronic mail" under PECR is not settled in the ICO guidance the research found (05 §6.2, unverified), so JobFerret applies the same ten rules on LinkedIn too.

**Follow-ups.** Recruiter advice is one or two polite follow-ups at most; more reads as pressure (02 §1.6, 02 Part 3). 05 §6.2 sets one follow-up after the first message, which is JobFerret's default (`max_touches = 2`).

## What JobFerret does about it

| Rule | Enforced by |
|---|---|
| Published or given addresses only, source recorded | `outreach.md` step 2; `contacts add --source-url` |
| Identity, source of address, easy opt-out in every first message | `outreach.md` step 3; you check before G1 |
| Stop on "no", permanent suppression | `outreach.py messages reply` suppresses on no/stop/remove/unsubscribe/not interested; `contacts add` and `messages add` refuse a suppressed contact |
| Two touches | `outreach.py messages done` refuses a touch past `max_touches` |
| Five new contacts a day, no bulk | `outreach.md` step 2 cap; bulk requests declined |
| The user sends | G1; LinkedIn always the user's click (G2) |

Not built yet: automatic deletion of old contact records. The user can export with `outreach.py export` and remove what they no longer need; the suppression list must stay.
