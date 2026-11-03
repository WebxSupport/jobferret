// JobFerret: read the job cards on a uk.indeed.com search page the user has open.
// Run it with the browser's JavaScript action (Claude: javascript_tool; Playwright: browser_evaluate).
// It only reads the page: no clicks, no requests, no storage. It returns a compact JSON string
// (about 0.5 KB per job). Save it exactly as returned to the file `discover.py browse plan` names
// (~/.jobferret/inbox/browse/indeed-NN.json), then: python scripts/discover.py browse ingest <files>
(() => {
  const page = (() => { const m = /[?&]start=(\d+)/.exec(location.search); return m ? Math.floor(Number(m[1]) / 10) + 1 : 1; })();
  const out = { board: "indeed", kind: "search", url: location.href, page, captured_at: new Date().toISOString(),
                logged_in: null, cards: [], how: null, challenge: false };
  const body = (document.body && document.body.innerText) || "";
  out.challenge = /verify you are human|additional verification|unusual traffic|access denied/i.test(body);
  const decode = (s) => { const t = document.createElement("textarea"); t.innerHTML = s; return t.value; };
  const text = (html) => {
    if (!html) return null;
    const s = decode(String(html).replace(/<\/(li|p|div|ul|ol|h\d)>|<br\s*\/?>/gi, "\n").replace(/<[^>]+>/g, ""));
    const lines = s.split("\n").map(l => l.replace(/\s+/g, " ").trim()).filter(Boolean);
    return lines.join("\n") || null;
  };
  const labels = (r, name) => { const o = []; for (const g of (r.taxonomyAttributes || [])) if (g && g.label === name) for (const a of (g.attributes || [])) if (a && a.label) o.push(a.label); return o; };
  const uniq = (xs) => Array.from(new Set(xs.filter(Boolean)));
  try {
    const p = window.mosaic && window.mosaic.providerData && window.mosaic.providerData["mosaic-provider-jobcards"];
    const m = p && p.metaData && p.metaData.mosaicProviderJobCardsModel;
    if (m && Array.isArray(m.results) && m.results.length) {
      out.how = "mosaic";
      out.logged_in = typeof m.loggedIn === "boolean" ? m.loggedIn : null;
      out.cards = m.results.map(r => ({
        jobkey: r.jobkey || null,
        title: r.title || r.displayTitle || null,
        company: r.company || r.truncatedCompany || null,
        location: r.formattedLocation || r.jobLocationCity || null,
        remote_type: (r.remoteWorkModel && r.remoteWorkModel.type) || (r.remoteLocation ? "REMOTE_ALWAYS" : null),
        salary_text: (r.salarySnippet && r.salarySnippet.text) || null,
        salary: r.extractedSalary ? { min: r.extractedSalary.min, max: r.extractedSalary.max, type: r.extractedSalary.type } : null,
        salary_estimated: (r.estimatedSalary && (r.estimatedSalary.formattedRange || r.estimatedSalary.text)) || null,
        job_types: uniq([...(r.jobTypes || []), ...labels(r, "job-types"), ...labels(r, "job-types-cc")]),
        benefits: labels(r, "benefits"),
        snippet: text(r.snippet),
        pub_date: r.pubDate || null,
        relative_time: r.formattedRelativeTime || null,
        indeed_apply: !!r.indeedApplyEnabled,
        sponsored: !!r.sponsored, urgently_hiring: !!r.urgentlyHiring, new: !!r.newJob, expired: !!r.expired,
        company_rating: r.companyRating || null,
      }));
    }
  } catch (e) { out.mosaic_error = String(e); }
  if (!out.cards.length) {
    // DOM fallback: one card per job_seen_beacon (or any element with data-jk), same shape.
    out.how = "dom";
    const txt = (el, sel) => { const e = el.querySelector(sel); return e ? (e.getAttribute("title") || e.innerText || e.textContent || "").trim() : null; };
    const cards = Array.from(document.querySelectorAll(".job_seen_beacon, [data-jk]"));
    const seen = new Set();
    for (const el of cards) {
      const jkEl = el.matches("[data-jk]") ? el : el.querySelector("[data-jk]");
      const a = el.querySelector("h2 a, a[id^='job_'], a[data-jk]");
      const jk = (jkEl && jkEl.getAttribute("data-jk")) || (a && a.id && a.id.replace(/^job_/, "")) || null;
      if (!jk || seen.has(jk)) continue;
      seen.add(jk);
      const attrs = Array.from(el.querySelectorAll("[data-testid='attribute_snippet_testid']")).map(e => e.innerText.trim());
      const all = el.innerText || "";
      out.cards.push({
        jobkey: jk,
        title: (a && a.innerText.trim()) || txt(el, "h2") || null,
        company: txt(el, "[data-testid='company-name']"),
        location: txt(el, "[data-testid='text-location']"),
        remote_type: null,
        salary_text: txt(el, ".salary-snippet-container") || (attrs.find(t => /£/.test(t)) || null),
        salary: null, salary_estimated: null,
        job_types: attrs.filter(t => !/£/.test(t)),
        benefits: [],
        snippet: txt(el, "[data-testid='belowJobSnippet'], .job-snippet, ul"),
        pub_date: null,
        relative_time: txt(el, "[data-testid='myJobsStateDate']"),
        indeed_apply: /easily apply/i.test(all),
        sponsored: /sponsored/i.test(all), urgently_hiring: /urgently hiring/i.test(all), new: /\bnew\b/i.test(all), expired: false,
        company_rating: null,
      });
    }
  }
  return JSON.stringify(out);
})();
