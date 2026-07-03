"""Guardrail matching: correct blocks without the old false positives/negatives."""
from cruxhive_mcp.cli import _guardrail_bash, _guardrail_path, _strip_commit_message


def _blocked(cmd):
    return _guardrail_bash(cmd)[0] is not None


# ── secrets-hygiene ───────────────────────────────────────────────────────────

def test_blocks_adding_secret_file():
    assert _blocked("git add .env")
    assert _blocked("git add config/id_rsa")
    assert _blocked("git commit .env.production -m 'oops'")
    assert _blocked("git add secrets.yaml")


def test_commit_message_mentioning_secret_not_blocked():
    # The old rule matched the secret pattern anywhere, incl. the -m message.
    assert not _blocked('git commit -m "document .env.example in the README"')
    assert not _blocked("git commit -m 'note about credentials handling'")
    assert not _blocked('git commit -am "fix .env loading bug"')
    assert not _blocked('git commit --message="mention secrets.yaml"')


def test_amend_not_swallowed_as_message():
    # --amend must not be mistaken for a -m message flag.
    assert not _blocked('git commit --amend --no-edit')


def test_non_secret_add_not_blocked():
    assert not _blocked("git add src/app.py")
    assert not _blocked("git commit -m 'ship it'")


# ── no-force-push-main ────────────────────────────────────────────────────────

def test_blocks_force_push_to_main():
    assert _blocked("git push --force origin main")
    assert _blocked("git push -f origin master")
    assert _blocked("git push --force origin HEAD:main")
    assert _blocked("git push --force-with-lease origin refs/heads/main")


def test_force_push_to_branch_named_like_main_not_blocked():
    # The old \b(main|master)\b matched inside a branch path.
    assert not _blocked("git push --force origin feature/main-rewrite")
    assert not _blocked("git push -f origin main-cleanup")
    assert not _blocked("git push --force origin domain")


def test_non_force_push_to_main_not_blocked():
    assert not _blocked("git push origin main")


# ── migration-immutable ───────────────────────────────────────────────────────

def test_tracked_migration_blocked_untracked_allowed():
    p = "app/migrations/versions/0001_init.py"
    assert _guardrail_path(p, tracked=True) is not None    # committed → immutable
    assert _guardrail_path(p, tracked=False) is None       # new, being authored


def test_non_migration_path_never_blocked():
    assert _guardrail_path("app/models.py", tracked=True) is None


# ── deploy-safety (warn, not block) ───────────────────────────────────────────

def test_deploy_prod_warns_but_does_not_block():
    block, warn = _guardrail_bash("./deploy_prod.sh")
    assert block is None
    assert warn is not None


# ── extra rules from .llm/guardrails.toml ─────────────────────────────────────

def test_extra_bash_rule_blocks():
    import re
    extra = [(re.compile(r".*"), re.compile(r"rm -rf /"), "no")]
    assert _guardrail_bash("sudo rm -rf /", extra)[0] == "no"


def test_strip_commit_message_leaves_pathspec():
    # add-with-message: filename outside the message survives stripping.
    out = _strip_commit_message("git add .env -m 'ignore me'")
    assert ".env" in out and "ignore me" not in out
