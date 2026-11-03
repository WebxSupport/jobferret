"""Tests for jf_net.py. No socket is ever opened: _do_request is replaced."""
import json
import time

import pytest

import jf_net


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    jf_net.set_cache_dir(tmp_path / "cache")
    jf_net.set_offline(False)
    jf_net._state["rates"] = {}
    jf_net._state["last"] = {}
    slept = []
    monkeypatch.setitem(jf_net._state, "sleep", lambda s: slept.append(s))
    yield slept
    jf_net.set_offline(None)
    jf_net.set_cache_dir(None)


class Fake:
    """Scripted responses: each call pops the next (status, text) pair."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, full_url, headers, method, body, timeout):
        self.calls.append({"url": full_url, "headers": headers, "method": method, "body": body})
        if not self.responses:
            raise AssertionError("unexpected extra request")
        status, text = self.responses.pop(0)
        if isinstance(status, Exception):
            raise status
        return status, text, {"Content-Type": "application/json", "X-Api-Key": "leak"}


def test_redact_hides_secret_keys_only():
    out = jf_net.redact({"app_id": "a", "app_key": "b", "what": "python", "nested": {"token": "t", "q": 1}, "items": [{"secret": 1}]})
    assert out == {"app_id": "***", "app_key": "***", "what": "python", "nested": {"token": "***", "q": 1}, "items": [{"secret": "***"}]}


def test_redact_url_hides_query_secrets_and_userinfo():
    url = "https://user:pw@api.example.com/v1/jobs?what=python&app_key=XYZ&page=2"
    out = jf_net.redact_url(url)
    assert "XYZ" not in out and "pw" not in out
    assert "what=python" in out and "page=2" in out and "app_key=%2A%2A%2A" in out


def test_fetch_json_caches_second_call(monkeypatch):
    fake = Fake((200, '{"results": [1, 2]}'))
    monkeypatch.setattr(jf_net, "_do_request", fake)
    first = jf_net.fetch_json("https://api.example.com/jobs", params={"what": "python", "app_key": "K"})
    second = jf_net.fetch_json("https://api.example.com/jobs", params={"what": "python", "app_key": "K"})
    assert first == second == {"results": [1, 2]}
    assert len(fake.calls) == 1
    assert "app_key=K" in fake.calls[0]["url"]          # the real request carries the key


def test_cache_file_holds_no_secret(monkeypatch, tmp_path):
    fake = Fake((200, '{"ok": true}'))
    monkeypatch.setattr(jf_net, "_do_request", fake)
    jf_net.fetch_json("https://api.example.com/jobs", params={"app_key": "SECRETVALUE"})
    files = list((tmp_path / "cache").glob("*.json"))
    assert len(files) == 1
    text = files[0].read_text(encoding="utf-8")
    assert "SECRETVALUE" not in text and "leak" not in text


def test_cache_key_ignores_secret_values():
    a = jf_net.cache_key("https://x/jobs", {"what": "python", "app_key": "A"})
    b = jf_net.cache_key("https://x/jobs", {"what": "python", "app_key": "B"})
    c = jf_net.cache_key("https://x/jobs", {"what": "java", "app_key": "A"})
    assert a == b and a != c


def test_ttl_expiry_refetches(monkeypatch):
    fake = Fake((200, '{"n": 1}'), (200, '{"n": 2}'))
    monkeypatch.setattr(jf_net, "_do_request", fake)
    url = "https://api.example.com/jobs"
    assert jf_net.fetch_json(url) == {"n": 1}
    key = jf_net.cache_key(url)
    rec = jf_net._read_cache(key)
    rec["fetched_ts"] = time.time() - 10_000
    jf_net._write_cache(key, rec)
    assert jf_net.fetch_json(url) == {"n": 2}
    assert len(fake.calls) == 2


def test_offline_miss_raises(monkeypatch):
    fake = Fake()
    monkeypatch.setattr(jf_net, "_do_request", fake)
    jf_net.set_offline(True)
    with pytest.raises(jf_net.OfflineMiss) as info:
        jf_net.fetch_json("https://api.example.com/jobs", params={"app_key": "K"})
    assert "K" not in str(info.value) and fake.calls == []


def test_offline_serves_primed_cache(monkeypatch):
    fake = Fake()
    monkeypatch.setattr(jf_net, "_do_request", fake)
    jf_net.prime_cache("https://api.example.com/jobs", {"results": ["x"]}, params={"what": "nurse", "app_key": "any"})
    jf_net.set_offline(True)
    out = jf_net.fetch_json("https://api.example.com/jobs", params={"what": "nurse", "app_key": "different"})
    assert out == {"results": ["x"]} and fake.calls == []


def test_env_var_turns_offline_on(monkeypatch):
    jf_net.set_offline(None)
    monkeypatch.setenv("JOBFERRET_OFFLINE", "1")
    assert jf_net.is_offline() is True
    monkeypatch.setenv("JOBFERRET_OFFLINE", "0")
    assert jf_net.is_offline() is False


def test_retries_on_503_then_succeeds(monkeypatch, isolated):
    fake = Fake((503, "busy"), (200, '{"ok": 1}'))
    monkeypatch.setattr(jf_net, "_do_request", fake)
    assert jf_net.fetch_json("https://api.example.com/jobs") == {"ok": 1}
    assert len(fake.calls) == 2
    assert isolated and isolated[0] == jf_net.RETRY_BACKOFF[0]


def test_gives_up_after_three_attempts(monkeypatch):
    fake = Fake((500, "a"), (502, "b"), (503, "c"))
    monkeypatch.setattr(jf_net, "_do_request", fake)
    with pytest.raises(jf_net.FetchError) as info:
        jf_net.fetch_json("https://api.example.com/jobs?app_key=SECRET")
    assert info.value.status == 503 and len(fake.calls) == 3
    assert "SECRET" not in str(info.value)


def test_404_is_not_retried(monkeypatch):
    fake = Fake((404, "no such board"))
    monkeypatch.setattr(jf_net, "_do_request", fake)
    with pytest.raises(jf_net.FetchError) as info:
        jf_net.fetch_json("https://api.example.com/boards/nope")
    assert info.value.status == 404 and len(fake.calls) == 1


def test_network_error_retried_then_raises(monkeypatch):
    import urllib.error
    fake = Fake((urllib.error.URLError("dns"), ""), (urllib.error.URLError("dns"), ""), (urllib.error.URLError("dns"), ""))
    monkeypatch.setattr(jf_net, "_do_request", fake)
    with pytest.raises(jf_net.FetchError) as info:
        jf_net.fetch_text("https://nowhere.example/feed.xml")
    assert info.value.status is None and "network error" in str(info.value)


def test_rate_limit_sleeps_between_requests_to_one_host(monkeypatch, isolated):
    fake = Fake((200, "a"), (200, "b"))
    monkeypatch.setattr(jf_net, "_do_request", fake)
    jf_net.set_rate("api.example.com", 2.0)
    jf_net.fetch_text("https://api.example.com/one")
    jf_net.fetch_text("https://api.example.com/two")
    assert isolated and 0 < isolated[-1] <= 2.0


def test_basic_auth_and_json_post(monkeypatch):
    fake = Fake((200, '{"posted": true}'))
    monkeypatch.setattr(jf_net, "_do_request", fake)
    out = jf_net.fetch_json("https://www.reed.co.uk/api/1.0/search", auth=("APIKEY", ""),
                            data={"query": "nurse"}, headers={"X-Extra": "1"})
    assert out == {"posted": True}
    call = fake.calls[0]
    assert call["method"] == "POST"
    assert call["headers"]["Authorization"].startswith("Basic ")
    assert call["headers"]["Content-Type"] == "application/json"
    assert call["headers"]["X-Extra"] == "1"
    assert call["headers"]["User-Agent"].startswith("JobFerret/")
    assert json.loads(call["body"]) == {"query": "nurse"}


def test_fetch_json_rejects_non_json(monkeypatch):
    fake = Fake((200, "<html>not json</html>"))
    monkeypatch.setattr(jf_net, "_do_request", fake)
    with pytest.raises(jf_net.FetchError) as info:
        jf_net.fetch_json("https://api.example.com/jobs")
    assert "not JSON" in str(info.value)


def test_offline_arg_helper():
    import argparse
    p = argparse.ArgumentParser()
    jf_net.add_offline_arg(p)
    jf_net.apply_offline_arg(p.parse_args(["--offline"]))
    assert jf_net.is_offline() is True
