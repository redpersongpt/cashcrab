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


def _youtube_job():
    from modules import crosspost, video, youtube
    try:
        result = video.generate_short()
        youtube.upload(
            result["video_path"],
            result["title"],
            result["description"],
        )
        crosspost.publish_short(result["video_path"], result["title"], result["description"])
        ui.success(f"Scheduler uploaded a YouTube Short: {result['title']}")
    except Exception as e:
        try:
            from modules import notify

            notify.error("scheduler youtube job", str(e))
        except Exception:
            pass
        ui.fail(f"Scheduler YouTube job failed: {e}")


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


def start():
    scheduler = _make_scheduler()

    yt_cfg = section("youtube")
    hours = yt_cfg.get("schedule_hours", [9])
    for h in hours:
        scheduler.add_job(
            _youtube_job, "cron", hour=h, minute=0,
            id=f"youtube_{h}", replace_existing=True,
        )
        ui.info(f"YouTube job scheduled for {h:02d}:00 every day")

    tw_cfg = section("twitter")
    interval = tw_cfg.get("schedule_interval_minutes", 120)
    scheduler.add_job(
        _twitter_job, "interval", minutes=interval,
        id="twitter_bot", replace_existing=True,
    )
    ui.info(f"Twitter / X job scheduled every {interval} minutes")

    ui.success("Scheduler is running. Press Ctrl+C to stop it.")
    try:
        scheduler.start()
    except KeyboardInterrupt:
        scheduler.shutdown()
        ui.warn("Scheduler stopped.")
