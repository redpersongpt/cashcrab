from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

from modules.config import section, ROOT
from modules import ui

DB_PATH = ROOT / "jobs.sqlite"


def _make_scheduler() -> BlockingScheduler:
    return BlockingScheduler(
        jobstores={"default": SQLAlchemyJobStore(url=f"sqlite:///{DB_PATH}")},
        job_defaults={"coalesce": True, "max_instances": 1},
    )


def _twitter_job():
    from modules import twitter
    try:
        twitter.run_batch(count=1, affiliate_ratio=0.3)
        ui.success("Scheduler posted to Twitter / X.")
    except Exception as e:
        try:
            from modules import notify

            notify.error("scheduler twitter job", str(e))
        except Exception:
            pass
        ui.fail(f"Scheduler Twitter job failed: {e}")


def _x_engage_job():
    from modules import x_engage
    from modules.config import optional_section

    try:
        cfg = optional_section("twitter") or {}
        engage_cfg = cfg.get("engage", {})
        duration = engage_cfg.get("autopilot_duration_minutes", 30)
        x_engage.thought_leader_cycle(duration_minutes=min(duration, 45))
        ui.success("Scheduler completed X engagement cycle.")
    except Exception as e:
        try:
            from modules import notify

            notify.error("scheduler x engage job", str(e))
        except Exception:
            pass
        ui.fail(f"Scheduler X engagement job failed: {e}")


def start():
    scheduler = _make_scheduler()

    tw_cfg = section("twitter")
    interval = tw_cfg.get("schedule_interval_minutes", 60)

    scheduler.add_job(
        _twitter_job, "interval", minutes=interval,
        id="twitter_bot", replace_existing=True,
    )
    ui.info(f"X post job scheduled every {interval} minutes")

    scheduler.add_job(
        _x_engage_job, "interval", minutes=interval,
        id="x_engage_bot", replace_existing=True,
        misfire_grace_time=300,
    )
    ui.info(f"X engagement autopilot scheduled every {interval} minutes")

    ui.success("Scheduler is running. Press Ctrl+C to stop it.")
    try:
        scheduler.start()
    except KeyboardInterrupt:
        scheduler.shutdown()
        ui.warn("Scheduler stopped.")
