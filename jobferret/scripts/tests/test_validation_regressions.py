"""Regression checks from the local skill review; no live requests or user data."""
import json
from urllib.request import Request

import pytest

import db
import discover
import hunt_cron
import jf_net
import ledger_check
import srcfx


@pytest.mark.parametrize("body,rule", [
    ("Increased productivity by 40%.", 2),
    ("- Increased productivity by 40%.", 1),
    ("**Skills:** SQL", 1),
])
def test_claim_below_name_is_not_contact_details(body, rule):
    result = ledger_check.check(f"# Jane Smith\n\n{body}\n", {"facts": []}, strict=True)
    assert not result["ok"] and result["violations"][0]["rule"] == rule


def test_actual_contact_details_below_name_remain_exempt():
    result = ledger_check.check(
        "# Jane Smith\nLeeds · 07700 900000 · jane@example.com\n", {"facts": []}, strict=True)
    assert result["ok"]


@pytest.fixture
def home(jf_home):
    jf_net.set_cache_dir(None)
    jf_net.set_offline(True)
    srcfx.write_home(jf_home)
    srcfx.prime_sources()
    yield jf_home
    jf_net.set_cache_dir(None)
    jf_net.set_offline(None)


def test_cancellation_stops_next_source_and_finishes_run(home, monkeypatch):
    original = discover.run_source
    calls = []

    def stop(entry, config, fetch):
        calls.append(entry["name"])
        result = original(entry, config, fetch)
        (home / "RUN").unlink()
        return result

    monkeypatch.setattr(discover, "run_source", stop)
    summary = discover.run_discovery(["reed", "nhs"], since=3650)
    assert calls == ["reed"] and summary["stopped"]
    assert not discover.any_ran(summary)
    assert "Next:" not in discover.render_summary(summary)
    con = db.connect(home / "jobferret.db")
    try:
        run = db.get_run(con, summary["run_id"])
        assert run["finished_at"] and run["errors"]["stopped"]
        assert discover.last_ok(con, "reed") is None
        assert discover.last_ok(con, "nhs") is None
        assert con.execute("SELECT count(*) FROM jobs").fetchone()[0] == 0
    finally:
        con.close()


def test_cancellation_stops_next_query(home, monkeypatch):
    profile_path = home / "profile.json"
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    profile["targets"]["titles"] = ["Data Analyst", "Reporting Analyst"]
    profile_path.write_text(json.dumps(profile), encoding="utf-8")
    calls = []

    def search(query, creds, fetch):
        calls.append(query)
        (home / "RUN").unlink()
        return []

    monkeypatch.setattr(discover.sources.SOURCES["nhs"], "search", search)
    summary = discover.run_discovery(["nhs"], since=3650)
    assert len(calls) == 1 and summary["stopped"]


def test_stop_during_storage_keeps_accurate_partial_totals(home, monkeypatch):
    original = discover.store
    calls = []

    def store(*args, **kwargs):
        row = original(*args, **kwargs)
        calls.append(row)
        (home / "RUN").unlink()
        return row

    monkeypatch.setattr(discover, "store", store)
    summary = discover.run_discovery(["nhs", "reed"], since=3650)
    assert len(calls) == 1 and summary["stopped"]
    assert summary["found"] == summary["new"] == 1
    con = db.connect(home / "jobferret.db")
    try:
        run = db.get_run(con, summary["run_id"])
        assert run["found"] == run["new"] == 1 and run["errors"]["stopped"]
        assert con.execute("SELECT count(*) FROM jobs").fetchone()[0] == 1
        assert discover.last_ok(con, "nhs") is None
    finally:
        con.close()


def test_cancellation_stops_additional_fetch_in_source(home, monkeypatch):
    calls = []

    def fetch(*args, **kwargs):
        calls.append(args)
        (home / "RUN").unlink()
        return "first response"

    def search(query, creds, fetch):
        fetch("https://example.test/first")
        fetch("https://example.test/second")
        return []

    monkeypatch.setattr(discover.sources.SOURCES["nhs"], "search", search)
    summary = discover.run_discovery(["nhs"], since=3650, fetch=fetch)
    assert len(calls) == 1 and summary["stopped"]


@pytest.mark.parametrize("stop_stage", ["discovery", "screening"])
def test_cron_skips_later_stages_after_stop(home, monkeypatch, capsys, stop_stage):
    original_discover = discover.run_discovery
    original_screen = hunt_cron.screen.screen_jobs

    def find(*args, **kwargs):
        summary = original_discover(*args, **kwargs)
        if stop_stage == "discovery":
            (home / "RUN").unlink()
        return summary

    def screen(*args, **kwargs):
        assert stop_stage == "screening", "screening started after cancellation"
        result = original_screen(*args, **kwargs)
        (home / "RUN").unlink()
        return result

    monkeypatch.setattr(discover, "run_discovery", find)
    monkeypatch.setattr(hunt_cron.screen, "screen_jobs", screen)
    assert hunt_cron.main(["--offline", "--since", "3650", "--json"]) == 1
    output = json.loads(capsys.readouterr().out)
    assert output["ok"] is False and "digest" not in output
    assert not (home / "digests").exists()


def test_stopped_discovery_cli_returns_failure(home, monkeypatch, capsys):
    def search(*args):
        (home / "RUN").unlink()
        return []

    monkeypatch.setattr(discover.sources.SOURCES["nhs"], "search", search)
    assert discover.main(["run", "--source", "nhs", "--offline", "--json"]) == 1
    output = json.loads(capsys.readouterr().out)
    assert output["stopped"] and output["ok"] is False


def test_request_guard_stops_retries_and_resets(home, monkeypatch):
    jf_net.set_offline(False)
    calls = []

    def request(*args):
        calls.append(args)
        (home / "RUN").unlink(missing_ok=True)
        return 503, "Unavailable", {}

    monkeypatch.setattr(jf_net, "_do_request", request)
    monkeypatch.setitem(jf_net._state, "sleep", lambda _: None)
    with jf_net.request_guard(discover.check_running):
        with pytest.raises(discover.DiscoveryStopped):
            jf_net.fetch("https://example.test/retry")
    assert len(calls) == 1
    # Other network clients are not left with discovery's guard after it exits.
    jf_net._check_request_guard()


def test_request_guard_checks_redirects(home):
    handler = jf_net._NeverFetchRedirect()
    (home / "RUN").unlink()
    with jf_net.request_guard(discover.check_running):
        with pytest.raises(discover.DiscoveryStopped):
            handler.redirect_request(Request("https://example.test/start"), None,
                                     302, "Found", {}, "https://example.test/next")
