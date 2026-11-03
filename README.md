# JobFerret

A UK job-hunting skill for Codex and Claude Code. It audits and tailors CVs using a fact ledger, finds and screens jobs, prepares applications for approval, and tracks follow-ups.

The installable skill is in [jobferret/](jobferret/). Read its [installation and usage guide](jobferret/README.md) and [skill instructions](jobferret/SKILL.md). The [research brief](research/00-research-brief.md) records the original design; current scope is UK support, with EU locale support deferred.

## Local tests

Requires Python 3.11 or later. From this repository root:

```sh
python -m pip install -r jobferret/scripts/requirements.txt pytest
python -m pytest jobferret/scripts/tests -q
```

The initial validated version passes 539 local tests, including regression checks for cancellation and fact validation. Live invocation in both hosts and real employer application flows remain untested.

Local evaluation runs, datasets, Python caches and generated sample renders are excluded from version control. Synthetic fixtures needed by tests and skill evaluations are included.
