"""Pure sync decision logic.

Given the local secret files, the remote profile metadata and the last-synced
baseline hashes, produce a :class:`SyncPlan`. No I/O and no prompts happen here,
which is exactly why this is the most thoroughly unit-tested module.
"""

from __future__ import annotations

from envsyncer.models import FilePlan, RemoteFile, SecretFile, SyncAction, SyncPlan


def build_plan(
    profile: str,
    local: dict[str, SecretFile],
    remote: dict[str, RemoteFile],
    baseline: dict[str, str],
) -> SyncPlan:
    """Compare each relative path across local/remote/baseline.

    ``local``/``remote`` are keyed by relative path; ``baseline`` maps relative
    path -> sha256 recorded at the previous successful sync.
    """
    plan = SyncPlan(profile=profile)

    for rel in sorted(set(local) | set(remote)):
        local_file = local.get(rel)
        remote_file = remote.get(rel)
        plan.files.append(_decide(rel, local_file, remote_file, baseline.get(rel)))

    return plan


def _decide(
    rel: str,
    local: SecretFile | None,
    remote: RemoteFile | None,
    baseline: str | None,
) -> FilePlan:
    # Present on only one side -> unambiguous direction.
    if local and not remote:
        return FilePlan(rel, SyncAction.UPLOAD, local=local, reason="local only")
    if remote and not local:
        return FilePlan(rel, SyncAction.DOWNLOAD, remote=remote, reason="remote only")

    assert local and remote  # both present from here on

    if local.sha256 == remote.sha256:
        return FilePlan(rel, SyncAction.IN_SYNC, local=local, remote=remote, reason="identical")

    # They differ. Use the baseline to attribute the change.
    if baseline is None:
        return FilePlan(rel, SyncAction.CONFLICT, local=local, remote=remote,
                        reason="differ, no baseline")
    if local.sha256 == baseline and remote.sha256 != baseline:
        return FilePlan(rel, SyncAction.DOWNLOAD, local=local, remote=remote,
                        reason="remote changed")
    if remote.sha256 == baseline and local.sha256 != baseline:
        return FilePlan(rel, SyncAction.UPLOAD, local=local, remote=remote,
                        reason="local changed")
    return FilePlan(rel, SyncAction.CONFLICT, local=local, remote=remote,
                    reason="both changed")
