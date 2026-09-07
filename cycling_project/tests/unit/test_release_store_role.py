"""The weekly release must open the hosted store as the operator role."""
import inspect

from cycling_project.nightly import release_store, weekly_release


def test_resolve_store_passes_role_through(monkeypatch):
    seen = {}

    class Fake:
        def __init__(self, role="agent"):
            seen["role"] = role

    monkeypatch.setattr(release_store, "hosted_store", lambda role="agent": Fake(role))
    release_store.resolve_store("hosted", None, role="operator")
    assert seen["role"] == "operator"


def test_weekly_release_uploads_as_operator():
    src = inspect.getsource(weekly_release)
    assert 'resolve_store(store_kind, store_root, role="operator")' in src


def test_upload_release_resumes_and_skips_present_objects(monkeypatch, tmp_path):
    from cycling_project.nightly import store as st
    (tmp_path / "a.bin").write_bytes(b"a"); (tmp_path / "b.bin").write_bytes(b"b")
    manifest = {"files": {"a.bin": {}, "b.bin": {}}, "tag": "t"}
    s = st.SupabaseStore.__new__(st.SupabaseStore); s.role = "operator"
    uploaded = []
    monkeypatch.setattr(s, "_list", lambda bucket, prefix, recursive=True: [{"key": "t/a.bin", "created_at": "", "size": 1}])
    monkeypatch.setattr(s, "_upload", lambda bucket, key, data, content_type=None: uploaded.append(key) or key)
    keys = s.upload_release("t", tmp_path, manifest)
    assert uploaded == ["t/b.bin", "t/manifest.json"] and len(keys) == 3
    # a complete release (manifest present) is immutable
    monkeypatch.setattr(s, "_list", lambda bucket, prefix, recursive=True: [{"key": "t/manifest.json", "created_at": "", "size": 1}])
    import pytest
    with pytest.raises(st.StoreConflictError):
        s.upload_release("t", tmp_path, manifest)


def test_upload_retries_transport_errors(monkeypatch):
    import requests
    from cycling_project.nightly import store as st
    s = st.SupabaseStore.__new__(st.SupabaseStore); s.role = "operator"; s.url = "https://x"; s.timeout = 1
    s._headers = lambda h: h
    calls = {"n": 0}
    class R:  status_code = 200; text = ""
    class Sess:
        def post(self, *a, **k):
            calls["n"] += 1
            if calls["n"] < 3: raise requests.exceptions.SSLError("bad record mac")
            return R()
    s._s = Sess()
    monkeypatch.setattr(st.time, "sleep", lambda *_: None)
    assert s._upload("releases", "t/x", b"x") == "t/x" and calls["n"] == 3
