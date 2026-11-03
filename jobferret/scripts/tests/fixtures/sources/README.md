# Recorded source responses

Small excerpts used by `test_sources.py`, `test_discover.py` and `test_screen.py`. No test
opens a socket.

| File | What | Origin |
|---|---|---|
| `nhs/search.xml` | NHS Jobs `search_xml`, three vacancies | Live response, 3 Nov 2026 (public-sector open data), trimmed |
| `teaching/jobs.json` | Teaching Vacancies page 1, three postings | Live response, 3 Nov 2026 (Open Government Licence), descriptions cut |
| `boards/greenhouse.json`, `lever.json`, `ashby.json`, `workable.json`, `recruitee.json`, `pinpoint.json`, `teamtailor.rss`, `personio.xml` | Employer ATS boards, two jobs each | Live public job adverts, 3 Nov 2026, descriptions cut |
| `boards/smartrecruiters.json` | SmartRecruiters postings | Synthetic, from the documented shape (not re-tested) |
| `adzuna/search.json` | Adzuna search | Synthetic, from the fields in Adzuna's OpenAPI spec (needs a key) |
| `reed/search.json`, `search-agency.json`, `detail-*.json` | Reed search and job detail | Synthetic, from Reed's documented fields (needs a key) |
| `rss/feed.xml`, `rss/atom.xml` | RSS 2.0 and Atom job feeds | Synthetic |
| `alerts/*.eml` | Reed and Totaljobs alert emails, and one from an unknown sender | Synthetic. The Totaljobs one has a fake sign-in token that the tests check never leaks |
| `sponsors/content.json` | GOV.UK Content API for the sponsor register | Live, 3 Nov 2026, trimmed to the attachments |
| `sponsors/register.csv` | Sponsor register CSV | Synthetic rows under the real header |
