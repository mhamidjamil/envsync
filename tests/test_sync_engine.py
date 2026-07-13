from pathlib import Path

from envsyncer.core.sync_engine import build_plan
from envsyncer.models import RemoteFile, SecretFile, SyncAction


def local(rel, h):
    return SecretFile(relative_path=rel, absolute_path=Path(rel), sha256=h, size=1)


def remote(rel, h):
    return RemoteFile(relative_path=rel, sha256=h, size=1)


def action_for(plan, rel):
    return next(f.action for f in plan.files if f.relative_path == rel)


def test_local_only_uploads():
    plan = build_plan("main", {"a": local("a", "h1")}, {}, {})
    assert action_for(plan, "a") is SyncAction.UPLOAD


def test_remote_only_downloads():
    plan = build_plan("main", {}, {"a": remote("a", "h1")}, {})
    assert action_for(plan, "a") is SyncAction.DOWNLOAD


def test_identical_is_in_sync():
    plan = build_plan("main", {"a": local("a", "h1")}, {"a": remote("a", "h1")}, {})
    assert action_for(plan, "a") is SyncAction.IN_SYNC


def test_only_local_changed_uploads():
    # baseline == remote, local differs -> local changed -> upload
    plan = build_plan("main", {"a": local("a", "new")}, {"a": remote("a", "old")}, {"a": "old"})
    assert action_for(plan, "a") is SyncAction.UPLOAD


def test_only_remote_changed_downloads():
    plan = build_plan("main", {"a": local("a", "old")}, {"a": remote("a", "new")}, {"a": "old"})
    assert action_for(plan, "a") is SyncAction.DOWNLOAD


def test_both_changed_is_conflict():
    plan = build_plan("main", {"a": local("a", "lh")}, {"a": remote("a", "rh")}, {"a": "base"})
    assert action_for(plan, "a") is SyncAction.CONFLICT


def test_divergence_without_baseline_is_conflict():
    plan = build_plan("main", {"a": local("a", "lh")}, {"a": remote("a", "rh")}, {})
    assert action_for(plan, "a") is SyncAction.CONFLICT
