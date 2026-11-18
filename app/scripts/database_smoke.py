"""SQLite/PostgreSQL 共用的治理仓储 smoke test。"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Event, local
from uuid import uuid4

from app.config.settings import Settings
from app.infrastructure.database import configure_database
from app.repositories.plan_runs import SqlPlanRunRepository
from app.repositories.policies import RiskRuleSchema, SqlRiskRuleRepository
from app.scripts.case_creation_smoke import run_case_creation_smoke
from app.scripts.refund_delivery_smoke import run_refund_delivery_smoke
from app.scripts.run_queue_smoke import run_queue_smoke
from app.services.actions import ActionService, digest
from app.services.providers import SqlWebhookDeduplicator, WebhookEvent
from sqlalchemy import event


def run_policy_transition_smoke(database_url):
    """Start rollback while another activation holds an uncommitted write."""
    policies = SqlRiskRuleRepository(database_url)
    prefix = "transition-" + uuid4().hex
    first, previous, published = [f"{prefix}-{n}" for n in range(3)]
    for version in (first, previous, published):
        policies.save_draft(RiskRuleSchema(version=version), "ci")
    policies.activate(first, "ci")
    policies.activate(previous, "ci")

    activated_write = Event()
    rollback_write = Event()
    worker = local()

    def after_write(_conn, _cursor, statement, *_args):
        if (
            getattr(worker, "name", None) == "publish"
            and not activated_write.is_set()
            and statement.upper().startswith("UPDATE RISK_RULE_VERSIONS")
        ):
            activated_write.set()
            if not rollback_write.wait(10):
                raise AssertionError("rollback did not reach its writer lock")

    def before_write(_conn, _cursor, statement, *_args):
        if getattr(worker, "name", None) == "rollback" and statement.upper().startswith(
            (
                "BEGIN IMMEDIATE",
                "LOCK TABLE RISK_RULE_VERSIONS",
                "UPDATE RISK_RULE_VERSIONS",
            )
        ):
            rollback_write.set()

    def publish():
        worker.name = "publish"
        return policies.activate(published, "publisher")

    def rollback():
        worker.name = "rollback"
        return policies.rollback("reviewer")

    event.listen(policies.engine, "after_cursor_execute", after_write)
    event.listen(policies.engine, "before_cursor_execute", before_write)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            publishing = pool.submit(publish)
            if not activated_write.wait(10):
                raise AssertionError("publish did not write the active rule")
            rolling_back = pool.submit(rollback)
            published_rule = publishing.result()
            restored_rule = rolling_back.result()
    finally:
        event.remove(policies.engine, "after_cursor_execute", after_write)
        event.remove(policies.engine, "before_cursor_execute", before_write)
    active = [row.version for row in policies.list() if row.status == "active"]
    if (
        published_rule.version,
        published_rule.status,
        restored_rule.version,
        active,
    ) != (published, "active", previous, [previous]):
        raise AssertionError(
            "Concurrent rollback did not restore the preceding active rule"
        )
    return {
        "overlapping_writes": 2,
        "active_rules": len(active),
        "previous_restored": True,
    }


def main() -> None:
    config = Settings(database_auto_create=False, commerce_seed_demo_data=False)
    configure_database(config.database_url, auto_create=False)
    suffix = uuid4().hex
    runs = SqlPlanRunRepository(config.database_url)
    run = runs.claim(
        plan_id=uuid4().hex,
        session_key=f"smoke-{suffix}",
        user_id="ci",
        worker_id="ci-worker",
        lease_seconds=30,
    )
    runs.finish(
        run.run_id,
        "completed",
        worker_id=run.worker_id,
        fencing_token=run.fencing_token,
    )
    print(f"policy_transition_smoke={run_policy_transition_smoke(config.database_url)}")
    webhook = SqlWebhookDeduplicator(config.database_url)
    event = WebhookEvent("ci", suffix, "smoke", {})
    if not webhook.accept(event) or webhook.accept(event):
        raise SystemExit("回调去重 smoke test 失败")
    actions = ActionService(config.database_url)
    proposal = actions.propose("ci", suffix, "smoke", {"value": 1}, "v1")
    actions.confirm(
        proposal["action_id"], "ci", suffix, digest({"value": 1}), "v1", channel="smoke"
    )
    confirmed = actions.get(proposal["action_id"], "ci", suffix)
    with ThreadPoolExecutor(max_workers=8) as pool:
        claims = list(pool.map(lambda _: actions.claim(confirmed), range(8)))
    if sum(claims) != 1:
        raise SystemExit("并发确认一次性消费 smoke test 失败")
    actions.finish(proposal["action_id"], {"success": True})
    report = run_case_creation_smoke(config.database_url)
    print(f"case_creation_smoke={report}")
    print(f"run_queue_smoke={run_queue_smoke(config.database_url)}")
    print(f"refund_delivery_smoke={run_refund_delivery_smoke(config.database_url)}")
    print("database_smoke=ok")


if __name__ == "__main__":
    main()
