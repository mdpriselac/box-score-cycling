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
