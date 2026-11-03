// JobFerret: read one uk.indeed.com /viewjob page the user has open: title, employer, place, pay,
// the full description, and how applying works ("Apply on company site" -> the employer's ATS;
// Indeed Apply -> the user clicks). Read-only: no clicks, no requests, no storage. The apply
// address is Indeed's own redirect; JobFerret never fetches it, it is clicked in the browser.
// Save the returned JSON and run: python scripts/discover.py browse job <file>
(() => {
  const out = { board: "indeed", kind: "job", url: location.href, captured_at: new Date().toISOString(),
                jobkey: null, title: null, company: null, location: null, salary: null, salary_text: null,
                job_types: [], description_html: null, apply: { kind: "unknown", url: null, label: null },
                expired: false, date_published: null, logged_in: null, challenge: false, how: null };
  const body = (document.body && document.body.innerText) || "";
  out.challenge = /verify you are human|additional verification|unusual traffic|access denied/i.test(body);
  const jkFromUrl = (/[?&]jk=([a-f0-9]+)/.exec(location.search) || [])[1] || null;
  try {
    const m = window._initialData && window._initialData.viewJobClientSideModel;
    if (m) {
      out.how = "initialData";
      out.jobkey = m.jobKey || jkFromUrl;
      out.title = m.jobTitle || null;
      out.logged_in = typeof m.loggedIn === "boolean" ? m.loggedIn : null;
      out.date_published = m.datePublished || null;
      out.expired = !!(m.jobInfoWrapperModel && m.jobInfoWrapperModel.jobInfoModel &&
        m.jobInfoWrapperModel.jobInfoModel.jobDescriptionSectionModel &&
        m.jobInfoWrapperModel.jobInfoModel.jobDescriptionSectionModel.jobDetailsSection &&
        m.jobInfoWrapperModel.jobInfoModel.jobDescriptionSectionModel.jobDetailsSection.isJobExpired);
      const info = m.jobInfoWrapperModel && m.jobInfoWrapperModel.jobInfoModel;
      const head = info && info.jobInfoHeaderModel;
      if (head) { out.company = head.companyName || null; out.location = head.formattedLocation || null; }
      if (info && info.sanitizedJobDescription) out.description_html = info.sanitizedJobDescription;
      const s = m.salaryInfoModel;
      if (s && (s.salaryMin || s.salaryMax)) out.salary = { min: s.salaryMin || null, max: s.salaryMax || null, type: s.salaryType || null };
      if (s && s.salaryText) out.salary_text = s.salaryText;
      const link = m.viewJobButtonLinkContainerModel && m.viewJobButtonLinkContainerModel.viewJobButtonLinkModel;
      if (m.indeedApplyButtonContainer) out.apply = { kind: "indeed-apply", url: null, label: "Apply now" };
      else if (link && link.href) out.apply = { kind: "company-site", url: link.href, label: "Apply on company site" };
      try {
        const attrs = m.categorizedAttributesModel && m.categorizedAttributesModel.categorizedAttributes;
        if (Array.isArray(attrs)) for (const g of attrs) if (g && /job type/i.test(g.header || "") && Array.isArray(g.attributes))
          out.job_types.push(...g.attributes.map(a => a.label).filter(Boolean));
      } catch (e) {}
    }
  } catch (e) { out.initial_error = String(e); }
  if (!out.title) {
    // DOM fallback.
    out.how = out.how || "dom";
    out.jobkey = out.jobkey || jkFromUrl;
    const h = document.querySelector("h1, h2[data-testid='jobsearch-JobInfoHeader-title'], [data-testid='jobsearch-JobInfoHeader-title']");
    out.title = h ? h.innerText.trim() : (document.title || "").split(" - ")[0];
    const c = document.querySelector("[data-testid='inlineHeader-companyName'], [data-company-name], .jobsearch-InlineCompanyRating div");
    if (c) out.company = c.innerText.trim();
    const l = document.querySelector("[data-testid='inlineHeader-companyLocation'], [data-testid='jobsearch-JobInfoHeader-companyLocation']");
    if (l) out.location = l.innerText.trim();
  }
  if (!out.description_html) {
    const d = document.querySelector("#jobDescriptionText, .simple-job-description-html, [class*='job-description'], [id*='jobDescription']");
    if (d) out.description_html = d.innerHTML;
  }
  if (out.apply.kind === "unknown") {
    const b = document.querySelector("[data-testid='viewjob-apply'], #indeedApplyButton, [data-testid='indeedApplyButton'], #applyButtonLinkContainer a, #applyButtonLinkContainer button");
    if (b) {
      const label = (b.innerText || b.getAttribute("aria-label") || "").trim();
      out.apply = { kind: /company site|employer site/i.test(label) ? "company-site" : (/apply now|easily apply/i.test(label) ? "indeed-apply" : "unknown"),
                    url: b.getAttribute("href") || null, label };
    }
  }
  return JSON.stringify(out);
})();
