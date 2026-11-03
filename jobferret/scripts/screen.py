"""screen.py: deterministic pre-screen of discovered jobs against profile.json (ARCHITECTURE.md 8.5).

Usage
    screen.py [--run <run id> | --all-new] [--offline] [--json]

    --run      screen the jobs first found in that discovery run
    --all-new  screen every job still at status seen (the default)

What it does, per job
    1. Exclude, only on hard facts, naming the rule and the text that matched:
       dealbreaker (exclusions.dealbreakers, word match in title or description),
       company (exclusions.companies), agency (an agency posting while
       exclusions.filters.no_agencies), unpaid / commission-only (the two filters),
       contract-type (known and not in targets.contract_types), salary (salary_max below
       targets.salary_floor in the same period), clearance (active or held clearance the
       user does not have: eligibility.security_clearance), sponsorship (the posting says
       no sponsorship and eligibility.sponsorship_needed_ever is true).
    2. Flag, never exclude: location outside targets.locations (not remote), work mode,
       salary not stated or estimated, old or reposted, no employer named, agency with a
       generic advert, immediate start, may close early, closes soon, right-to-work or
       nationality wording, DBS, driving licence, IR35 status, likely-duplicate-of <job id>
       (same normalised title, salary band, town and advertiser within 14 days), and
       sponsor-licence: yes|no|unknown from the Home Office register when the user needs
       sponsorship.
    3. Score 0-100: title 0-40, skills 0-30 (the ledger's skill facts and history.skills
       found in the description), recency 0-10, salary 0-10, employer named and direct 0-10.
       ghost_risk low|medium|high is counted from the flags and reported separately.

    Writes fit_pre and screen_json with db.set_screening. Excluded jobs get status
    excluded and status_reason "<rule>: <matched text>"; the rest become screened. A job
    already shortlisted, dismissed or applied keeps its status. Phrase patterns come from
    lexicon/uk_phrases.toml.

screen_json
    {"excluded": "<rule>: <matched text>" | null, "exclusions": [{"rule", "matched", "where"}],
     "flags": ["..."], "scores": {"title", "skills", "recency", "salary", "employer"},
     "matched_terms": [...], "skills_found": [...], "ghost_risk": "low|medium|high", "duplicate_of": id|null,
     "sponsor_licence": "yes|no|unknown"|null, "screened_at": ISO}

Exit codes
    0  ok (including nothing to screen)
    1  the database could not be read
    4  usage or input error (bad profile.json, unknown run)
"""
from __future__ import annotations

import json
import re
import sys
import tomllib
from datetime import datetime, timedelta, timezone
from pathlib import Path

import db
import jf_net
from jf_common import (
    EXIT_FAIL, EXIT_OK, EXIT_USAGE, SCRIPTS_DIR, die, emit_json, load_ledger, load_profile, make_parser, now_iso,
    setup_io, user_dir,
)

PHRASES_PATH = SCRIPTS_DIR / "lexicon" / "uk_phrases.toml"
DUP_WINDOW_DAYS = 14
OLD_DAYS = 30
REPOST_GAP_DAYS = 30
SENIORITY = {"senior", "snr", "sr", "junior", "jnr", "jr", "lead", "principal", "graduate", "trainee", "mid", "level",
             "i", "ii", "iii", "iv", "staff", "head", "assistant", "associate", "chief"}
STOP = {"and", "or", "of", "the", "a", "an", "in", "for", "to", "with", "at", "on", "&", "uk", "x", "f", "m", "d", "w"}
CLEARANCE_LEVEL = {"bpss": 1, "ctc": 2, "sc": 3, "esc": 3, "dv": 4, "edv": 4}
PUBLIC_SECTOR_SOURCES = {"nhs", "teaching"}
CONTRACT_PHRASE_KEY = {"fixed-term": "fixed_term", "part-time": "part_time"}
CONTRACT_ALIASES = {"perm": "permanent", "permanent": "permanent", "contract": "contract", "contractor": "contract",
                    "freelance": "contract", "interim": "contract", "fixed term": "fixed-term", "fixed-term": "fixed-term",
                    "ftc": "fixed-term", "temporary": "temporary", "temp": "temporary", "part time": "part-time",
                    "part-time": "part-time"}


# ----------------------------------------------------------------- phrases

_phrases: dict | None = None


def load_phrases(path: Path | None = None) -> dict:
    global _phrases
    if _phrases is not None and path is None:
        return _phrases
    data = tomllib.loads(Path(path or PHRASES_PATH).read_text(encoding="utf-8"))
    out = {g: {k: [re.compile(p) for p in pats] for k, pats in grp.items()} for g, grp in data.items()}
    if path is None:
        _phrases = out
    return out


def match(text: str, group: str, key: str) -> str | None:
    """The first text that matches one of the patterns in [group] key, or None."""
    for rx in load_phrases().get(group, {}).get(key, []):
        m = rx.search(text)
        if m:
            return m.group(0)
    return None


def term_rx(term: str) -> re.Pattern:
    return re.compile(r"(?<![\w])" + re.escape(term.lower()) + r"(?![\w])")


# ----------------------------------------------------------------- inputs

def job_text(job: dict) -> tuple[str, dict]:
    """(description, extra) from the job file at jd_path; ('', {}) when it is missing."""
    path = job.get("jd_path")
    if not path or not Path(path).is_file():
        return "", {}
    try:
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "", {}
    return str(doc.get("description") or ""), dict(doc.get("extra") or {})


def skill_terms(profile: dict, ledger: dict | None) -> list[str]:
    terms: list[str] = []
    for f in (ledger or {}).get("facts", []):
        if f.get("kind") != "skill" or f.get("superseded_by"):
            continue
        text = re.sub(r"^\*\*[^*]+:\*\*", "", str(f.get("text") or ""))
        text = re.sub(r"^[^:]{1,30}:", "", text)
        for part in re.split(r"[,;|/()•·]+|\band\b", text):
            part = part.strip(" .-*")
            if 1 < len(part) <= 40:
                terms.append(part)
    for s in (profile.get("history") or {}).get("skills") or []:
        if isinstance(s, str) and s.strip():
            terms.append(s.strip())
    seen, out = set(), []
    for t in terms:
        k = t.casefold()
        if k not in seen and not re.fullmatch(r"[\d\s.%+£$-]+", k):
            seen.add(k)
            out.append(t)
    return out


def load_user_ledger() -> dict | None:
    path = user_dir() / "cv" / "ledger.json"
    if not path.is_file():
        return None
    try:
        return load_ledger(path)
    except Exception:
        return None


def user_clearance(profile: dict) -> int:
    held = str((profile.get("eligibility") or {}).get("security_clearance") or "").lower()
    if re.search(r"\b(?:e?dv|developed vetting)\b", held):
        return 4
    if re.search(r"\b(?:e?sc|security check)\b", held):
        return 3
    if re.search(r"\b(?:ctc|counter)", held):
        return 2
    if "bpss" in held or "baseline" in held:
        return 1
    return 0


def required_level(phrase: str) -> int:
    p = phrase.lower()
    for word, level in sorted(CLEARANCE_LEVEL.items(), key=lambda kv: -kv[1]):
        if re.search(rf"\b{word}\b", p):
            return level
    return 1                                    # "active security clearance": some clearance, level unclear


def norm_contracts(values) -> set[str]:
    out = set()
    for v in values or []:
        k = re.sub(r"\s+", " ", str(v).strip().lower().replace("_", " "))
        out.add(CONTRACT_ALIASES.get(k, k))
    return out


def _dt(value) -> datetime | None:
    if not value:
        return None
    s = str(value)
    if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
        s += "T00:00:00+00:00"
    try:
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def money(amount, period: str | None) -> str:
    if amount is None:
        return "?"
    text = f"£{amount:,.0f}" if amount >= 100 else f"£{amount:,.2f}"
    return text + (f" a {period}" if period and period != "unknown" else "")


# ----------------------------------------------------------------- duplicates

def _title_key(title: str) -> str:
    words = [w for w in db.normalize_title(title).split() if w not in SENIORITY and w not in STOP]
    return " ".join(words)


def _band(job: dict) -> str:
    amt = job.get("salary_max") if job.get("salary_max") is not None else job.get("salary_min")
    if amt is None:
        return "?"
    period = job.get("salary_period") or "unknown"
    step = {"year": 5000, "day": 25, "hour": 1}.get(period, 5000 if amt >= 2000 else 25)
    return f"{period}:{int(round(float(amt) / step) * step)}"


def _town(location: str | None) -> str:
    if not location:
        return ""
    first = re.split(r"[,;/(|]| - ", location)[0].strip().lower()
    first = re.sub(r"\b[a-z]{1,2}\d[a-z\d]?\s*\d[a-z]{2}\b", "", first)   # postcodes
    return re.sub(r"\s+", " ", first).strip()


def duplicate_key(job: dict) -> tuple | None:
    title, town = _title_key(job.get("title") or ""), _town(job.get("location"))
    band = _band(job)
    advertiser = db.normalize_company(job.get("company") or "") or "?"
    if not title or not town or (band == "?" and advertiser == "?"):
        return None
    return (title, band, town, advertiser)


def find_duplicates(jobs: list[dict], window_days: int = DUP_WINDOW_DAYS) -> dict[str, str]:
    """{job id: id of the earlier job it probably repeats}. Never more than a flag."""
    out: dict[str, str] = {}
    clusters: dict[tuple, tuple[str, datetime]] = {}

    def when(j):
        return _dt(j.get("posted_at")) or _dt(j.get("first_seen")) or datetime.now(timezone.utc)
    for j in sorted(jobs, key=lambda j: (when(j), j.get("first_seen") or "", j["id"])):
        key = duplicate_key(j)
        if key is None:
            continue
        t = when(j)
        if key in clusters:
            orig_id, orig_t = clusters[key]
            if abs((t - orig_t).days) <= window_days:
                out[j["id"]] = orig_id
                continue
        clusters[key] = (j["id"], t)
    return out


# ----------------------------------------------------------------- the screen

def screen_job(job: dict, profile: dict, skills: list[str], *, description: str = "", extra: dict | None = None,
               duplicate_of: str | None = None, sponsor_check=None, now: datetime | None = None) -> dict:
    """The screening result for one job (a list_jobs-style dict). Pure apart from sponsor_check."""
    extra = extra or {}
    now = now or datetime.now(timezone.utc)
    title = job.get("title") or ""
    company = (job.get("company") or "").strip()
    text = f"{title}\n{description}".lower()
    targets = profile.get("targets") or {}
    excl = profile.get("exclusions") or {}
    filters = excl.get("filters") or {}
    elig = profile.get("eligibility") or {}
    exclusions: list[dict] = []
    flags: list[str] = []

    def exclude(rule, matched, where="description"):
        exclusions.append({"rule": rule, "matched": matched, "where": where})

    # 1. Exclusions -------------------------------------------------------
    for term in excl.get("dealbreakers") or []:
        if not isinstance(term, str) or not term.strip():
            continue
        m = term_rx(term.strip()).search(text)
        if m:
            exclude("dealbreaker", term.strip(), "title" if m.start() < len(title) else "description")
    comp_norm = db.normalize_company(company)
    for c in excl.get("companies") or []:
        cn = db.normalize_company(str(c))
        if cn and comp_norm and (cn == comp_norm or re.search(rf"\b{re.escape(cn)}\b", comp_norm)):
            exclude("company", company, "company")
    agency_name = match(company.lower(), "agency", "names") if company else None
    is_agency = job.get("employer_type") == "agency" or bool(agency_name)
    if is_agency and filters.get("no_agencies"):
        exclude("agency", agency_name or f"{company or 'advertiser'} is listed as a recruitment agency", "company")
    unpaid = match(text, "pay", "unpaid")
    if unpaid:
        (exclude("unpaid", unpaid) if filters.get("no_unpaid", True) else flags.append(f"unpaid: {unpaid}"))
    commission = match(text, "pay", "commission_only")
    if commission:
        (exclude("commission-only", commission) if filters.get("no_commission_only", True)
         else flags.append(f"commission-only: {commission}"))
    wanted = norm_contracts(targets.get("contract_types"))
    ctype = job.get("contract_type") or "unknown"
    hours = extra.get("hours")
    if wanted and ctype != "unknown" and ctype not in wanted and not (hours == "part-time" and "part-time" in wanted):
        # Listing labels are coarse (Adzuna files fixed-term work under "contract"), so when the advert's
        # own words name a type the user wants, flag the conflict instead of excluding.
        said = next((m for w in sorted(wanted) if (m := match(text, "contract", CONTRACT_PHRASE_KEY.get(w, w)))), None)
        if said:
            flags.append(f"contract-type-unclear: listed as {ctype}, advert says {said}")
        else:
            exclude("contract-type", f"{ctype} (you want {', '.join(sorted(wanted))})", "listing")
    floor = targets.get("salary_floor") or {}
    floor_amt = floor.get("amount") or 0
    floor_period = floor.get("period") or "year"
    smax, period = job.get("salary_max"), job.get("salary_period") or "unknown"
    if floor_amt and smax is not None and period == floor_period and smax < floor_amt:
        exclude("salary", f"{money(smax, period)} is below your floor of {money(floor_amt, floor_period)}", "listing")
    have = user_clearance(profile)
    active = match(text, "clearance", "active")
    if active and required_level(active) > have:
        exclude("clearance", active)
    needs_sponsor = bool(elig.get("sponsorship_needed_ever"))
    no_sponsor = match(text, "sponsorship", "not_offered")
    if no_sponsor and needs_sponsor:
        exclude("sponsorship", no_sponsor)

    # 2. Flags ------------------------------------------------------------
    remote = job.get("remote") or "unknown"
    locations = [str(l).strip().lower() for l in targets.get("locations") or [] if str(l).strip()]
    loc = (job.get("location") or "").lower()
    if locations and remote != "remote":
        if not loc:
            flags.append("location-unknown")
        elif not any(re.search(rf"\b{re.escape(l)}\b", loc) for l in locations):
            flags.append(f"location-outside: {job.get('location')}")
    modes = {str(m).lower() for m in targets.get("work_modes") or []}
    if modes and remote != "unknown" and remote not in modes:
        flags.append(f"work-mode: {remote} (you said {', '.join(sorted(modes))})")
    if job.get("salary_min") is None and job.get("salary_max") is None:
        said = extra.get("salary_text") or match(text, "salary", "not_stated")
        flags.append("salary-not-stated" + (f": {said}" if said else ""))
        if extra.get("salary_estimate"):
            flags.append("salary-estimated-by-adzuna")
    elif floor_amt and period not in (floor_period, "unknown") and period == "day" and floor_period == "year":
        top = smax if smax is not None else job.get("salary_min")
        flags.append(f"day-rate: {money(top, 'day')} is about {money(top * 220, 'year')} at 220 days (estimate)")
    posted = _dt(job.get("posted_at"))
    if posted and (now - posted).days > OLD_DAYS:
        flags.append(f"old-posting: posted {(now - posted).days} days ago")
    fp, up = _dt(extra.get("first_published")), _dt(extra.get("updated_at"))
    if fp and up and (up - fp).days > REPOST_GAP_DAYS:
        flags.append(f"reposted: first published {fp.date()}, updated {up.date()}")
    tells = match(text, "agency", "tells")
    if not company or (tells and not is_agency and tells in ("our client", "my client")):
        flags.append("no-employer-named" + (f": {tells}" if tells else ""))
    if is_agency:
        flags.append(f"agency: {company or 'unnamed'}")
        if tells or (job.get("salary_min") is None and job.get("salary_max") is None):
            flags.append("agency-generic")
    immediate = match(text, "urgency", "immediate_start")
    if immediate:
        flags.append(f"immediate-start: {immediate}")
    early = match(text, "urgency", "may_close_early")
    if early:
        flags.append(f"may-close-early: {early}")
    exp = _dt(job.get("expires_at"))
    if exp and 0 <= (exp - now).total_seconds() <= 3 * 86400:
        flags.append(f"closes-soon: {exp.date()}")
    rtw = match(text, "right_to_work", "required")
    if rtw and needs_sponsor:
        flags.append(f"right-to-work: {rtw}")
    nat = match(text, "right_to_work", "nationality")
    if nat:
        flags.append(f"nationality: {nat}")
    offered = match(text, "sponsorship", "offered")
    if offered and needs_sponsor:
        flags.append(f"sponsorship-offered: {offered}")
    if no_sponsor and not needs_sponsor:
        pass                                    # irrelevant to this user
    if not active:
        for lvl in ("dv", "sc", "ctc", "bpss"):
            hit = match(text, "clearance", lvl)
            if hit:
                eligible = match(text, "clearance", "eligible")
                flags.append(f"clearance: {hit}" + (" (eligibility, not held)" if eligible else ""))
                break
    elif required_level(active) <= have:
        flags.append(f"clearance: {active} (you hold it)")
    dbs = match(text, "dbs", "any")
    if dbs:
        flags.append(f"dbs: {dbs}")
    licence = match(text, "driving", "licence")
    held = str(elig.get("driving_licence") or "").strip().lower()
    if licence and (not held or held in ("no", "none", "false")):
        flags.append(f"driving-licence-needed: {licence}")
    voc = match(text, "driving", "vocational")
    if voc:
        flags.append(f"licence-or-card: {voc}")
    for key in ("inside", "outside", "undetermined"):
        hit = match(text, "ir35", key)
        if hit:
            flags.append(f"ir35-{key}: {hit}")
            pref = str(targets.get("ir35") or "").lower()
            if pref in ("inside", "outside") and key in ("inside", "outside") and pref != key:
                flags.append(f"ir35-mismatch: you said {pref}")
            break
    scam = match(text, "pay", "scam")
    if scam:
        flags.append(f"scam-marker: {scam}")
    if not description.strip():
        flags.append("description-missing")
    if extra.get("no_public_link"):
        flags.append("no-public-link: open the alert email")
    if duplicate_of:
        flags.append(f"likely-duplicate-of {duplicate_of}")
    sponsor = None
    if needs_sponsor and sponsor_check is not None:
        sponsor = sponsor_check(company) if company and not is_agency else "unknown"
        flags.append(f"sponsor-licence: {sponsor}")

    # 3. Scores -----------------------------------------------------------
    matched_terms: list[str] = []
    jt = set(db.normalize_title(title).split()) - STOP
    t_score = 0.0
    for target in targets.get("titles") or []:
        tt = set(db.normalize_title(str(target)).split()) - STOP
        if not tt:
            continue
        if db.normalize_title(str(target)) in db.normalize_title(title):
            score = 40.0
        else:
            score = 40.0 * len(tt & jt) / len(tt)
        if score > t_score:
            t_score = score
        matched_terms.extend(sorted(tt & jt))
    found = [s for s in skills if term_rx(s).search(text)]
    matched_terms.extend(found)
    s_score = 30.0 * min(1.0, len(found) / max(3, min(10, len(skills)))) if skills else 0.0
    if posted is None:
        r_score = 5.0
    else:
        age = (now - posted).days
        r_score = 10.0 if age <= 1 else 8.0 if age <= 3 else 6.0 if age <= 7 else 4.0 if age <= 14 else 2.0 if age <= 30 else 0.0
    if job.get("salary_min") is None and job.get("salary_max") is None:
        p_score = 3.0
    elif any(e["rule"] == "salary" for e in exclusions):
        p_score = 0.0
    elif not floor_amt or period == floor_period:
        p_score = 10.0
    else:
        p_score = 6.0
    if not company:
        e_score = 0.0
    elif is_agency:
        e_score = 3.0
    elif job.get("employer_type") == "direct":
        e_score = 10.0
    else:
        e_score = 7.0
    scores = {"title": round(t_score, 1), "skills": round(s_score, 1), "recency": r_score, "salary": p_score,
              "employer": e_score}
    fit = round(min(100.0, sum(scores.values())), 1)

    ghost_signals = [f for f in flags if f.split(":")[0].split(" ")[0] in (
        "old-posting", "reposted", "no-employer-named", "agency-generic", "likely-duplicate-of", "scam-marker")]
    if any(f.startswith("immediate-start") for f in flags) and is_agency and ctype == "permanent":
        ghost_signals.append("immediate-start")
    n = len(ghost_signals)
    ghost = "low" if n == 0 else "medium" if n <= 2 else "high"
    if job.get("source") in PUBLIC_SECTOR_SOURCES and not any(g.startswith("scam") for g in ghost_signals):
        ghost = "low"                            # closing dates and audited processes (05 section 5.6)

    first = exclusions[0] if exclusions else None
    return {
        "excluded": f"{first['rule']}: {first['matched']}" if first else None,
        "exclusions": exclusions,
        "flags": flags,
        "scores": scores,
        "fit_pre": fit,
        "matched_terms": sorted(set(matched_terms), key=str.lower),
        "skills_found": found,
        "ghost_risk": ghost,
        "duplicate_of": duplicate_of,
        "sponsor_licence": sponsor,
        "screened_at": now_iso(),
    }


def select_jobs(con, run: str | None) -> list[dict]:
    if run:
        try:
            db.get_run(con, run)
        except db.DBError as exc:
            die(str(exc), EXIT_USAGE)
        return db.list_jobs(con, run=run)
    return db.list_jobs(con, status="seen")


def screen_jobs(run: str | None = None, profile: dict | None = None, sponsor_check=None) -> dict:
    """Screen the selected jobs and write the results. Returns the summary."""
    profile = profile if profile is not None else load_profile()
    ledger = load_user_ledger()
    skills = skill_terms(profile, ledger)
    con = db.connect(db.default_db_path())
    try:
        targets = select_jobs(con, run)
        recent = db.list_jobs(con, since=30 + DUP_WINDOW_DAYS)
        dupes = find_duplicates(recent)
        needs = bool((profile.get("eligibility") or {}).get("sponsorship_needed_ever"))
        if needs and sponsor_check is None:
            from sources import sponsors
            register = sponsors.load_register()
            sponsor_check = (lambda name: sponsors.is_sponsor(name, register)) if register is not None else (lambda name: "unknown")
        results = []
        by_rule: dict[str, int] = {}
        for job in targets:
            description, extra = job_text(job)
            res = screen_job(job, profile, skills, description=description, extra=extra,
                             duplicate_of=dupes.get(job["id"]), sponsor_check=sponsor_check if needs else None)
            fit = res.pop("fit_pre")
            screen = dict(res)
            if res["excluded"]:
                rule = res["exclusions"][0]["rule"]
                by_rule[rule] = by_rule.get(rule, 0) + 1
                db.set_screening(con, job["id"], fit, screen)
                if job["status"] in ("seen", "screened", "excluded"):
                    db.set_job_status(con, job["id"], "excluded", res["excluded"])
            else:
                db.set_screening(con, job["id"], fit, screen, status="screened")
            results.append({"id": job["id"], "title": job["title"], "company": job["company"],
                            "location": job["location"], "salary": job.get("salary"), "source": job["source"],
                            "fit_pre": fit, "excluded": res["excluded"], "flags": res["flags"],
                            "ghost_risk": res["ghost_risk"], "url": job.get("url")})
        excluded = sum(1 for r in results if r["excluded"])
        if results:
            db.add_event(con, "screen", f"screened {len(results)}: {len(results) - excluded} kept, {excluded} excluded"
                         + (f" (run {run})" if run else ""))
        kept = sorted((r for r in results if not r["excluded"]), key=lambda r: -r["fit_pre"])
        return {"run": run, "screened": len(results), "kept": len(kept), "excluded": excluded,
                "by_rule": by_rule, "skill_terms": len(skills), "jobs": kept + [r for r in results if r["excluded"]]}
    finally:
        con.close()


def render(summary: dict) -> str:
    if not summary["screened"]:
        return "Nothing to screen: no new jobs." + (f" (run {summary['run']})" if summary["run"] else "")
    lines = [f"Screened {summary['screened']} jobs: {summary['kept']} kept, {summary['excluded']} excluded."]
    if summary["by_rule"]:
        lines.append("Excluded by rule: " + ", ".join(f"{k} {v}" for k, v in sorted(summary["by_rule"].items(),
                                                                                    key=lambda kv: -kv[1])))
    if not summary["skill_terms"]:
        lines.append("No skills to match yet (no ledger skill facts or history.skills), so skill scores are 0.")
    top = [j for j in summary["jobs"] if not j["excluded"]][:5]
    if top:
        lines.append("Top by pre-screen score:")
        for j in top:
            bits = [j["title"], j["company"] or "no employer named", j["location"] or "", j["salary"] or ""]
            lines.append(f"  {j['fit_pre']:>4.0f}  " + " · ".join(b for b in bits if b))
    lines.append("Next: python scripts/digest.py")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    setup_io()
    p = make_parser(__doc__, prog="screen.py")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--run", help="screen the jobs first found in this run")
    g.add_argument("--all-new", action="store_true", help="screen every job at status seen (default)")
    jf_net.add_offline_arg(p)
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)
    jf_net.apply_offline_arg(a)
    try:
        profile = load_profile()
    except ValueError as exc:
        die(str(exc), EXIT_USAGE)
    try:
        summary = screen_jobs(a.run, profile)
    except db.DBError as exc:
        die(str(exc), EXIT_FAIL)
    if a.json:
        emit_json(jf_net.redact(summary))
    else:
        print(render(summary))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
