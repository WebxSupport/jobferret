# JobFerret

A UK job-hunting skill for Codex and Claude Code. It audits and tailors CVs using a fact ledger, finds and screens jobs, prepares applications for approval, and tracks follow-ups.

The installable skill is in [jobferret/](jobferret/). Read its [installation and usage guide](jobferret/README.md) and [skill instructions](jobferret/SKILL.md). The [research brief](research/00-research-brief.md) records the original design; current scope is UK support, with EU locale support deferred.

## Install

Use a local Codex or Claude Code session with Python 3.11+. From your own terminal, clone this repository (or extract the [repository ZIP](https://github.com/WebxSupport/jobferret/archive/refs/heads/main.zip)):

```sh
git clone https://github.com/WebxSupport/jobferret.git
cd jobferret
python install.py --host codex
```

For Claude Code, use `python install.py --host claude`. On macOS/Linux use `python3` if `python` is unavailable; on Windows use `py -3`.

The installer defaults to **this project**, using `.agents/skills/jobferret` for Codex or `.claude/skills/jobferret` for Claude Code. It needs no GitHub connection once the repository is on disk, uses no third-party libraries, and does not write to your personal skills folder. Open this folder as your project in the app. To install into another project, append `--project "path/to/project"`; for a personal install across projects, append `--scope user`. Existing installations are preserved: move the old skill folder out of the skills directory before reinstalling.

The installer prints a command to install the Python dependencies. Run that command, then `$jobferret start` in Codex or `/jobferret start` in Claude Code. If the skill does not appear, restart the session. Copying files, installing dependencies and completing setup are separate steps; the installer only copies the skill.

### If an assistant says GitHub or the personal skills folder is unavailable

That reports restrictions in the current session; it does not establish that the repository or skill is broken. A ZIP attachment alone cannot grant access to your computer's skills folder. Use the terminal instructions above, or ask the assistant:

> Install JobFerret from https://github.com/WebxSupport/jobferret/tree/main/jobferret into this project's skills directory. Check the tools and writable locations actually available. If a local checkout already exists, use it without downloading again. Otherwise use an allowed download method. Read the repository README before installing. Use `python install.py --host codex --scope project --project "<current project path>"` from the repository root (use `--host claude` for Claude Code). Do not change permission settings. If this session cannot download or write the files, explain the specific restriction and provide the local-terminal steps from the README. Do not claim installation succeeded without verifying the destination's SKILL.md.

If the session cannot access GitHub, download the [repository ZIP](https://github.com/WebxSupport/jobferret/archive/refs/heads/main.zip) in your browser, extract it, open the extracted folder and run the installer locally. If your own browser also cannot access GitHub, you need a repository copy from someone who can. No installer can fetch files without a permitted network route or a local copy.

### Claude web / other hosted chats

These instructions install local **Claude Code or Codex** skills. A hosted chat may have a separate skill-upload interface and may not have access to local folders. Where supported, upload a skill-only ZIP through that product's skill settings rather than assuming a chat attachment installs it. Build that ZIP from a checkout with:

```sh
python install.py --bundle dist/jobferret.zip
```

The ZIP has one `jobferret/` folder containing `SKILL.md` and its runtime resources, without test data or caches. It is not the same as GitHub's repository ZIP. Hosted compatibility, Python dependencies, browser tools and persistence still need checking in that product; packaging alone does not provide them.

## Local tests

Requires Python 3.11 or later. From this repository root:

```sh
python -m pip install -r jobferret/scripts/requirements.txt pytest
python -m pytest tests jobferret/scripts/tests -q
```

The initial validated version passes 539 local tests, including regression checks for cancellation and fact validation. Live invocation in both hosts and real employer application flows remain untested.

Local evaluation runs, datasets, Python caches and generated sample renders are excluded from version control. Synthetic fixtures needed by tests and skill evaluations are included.
