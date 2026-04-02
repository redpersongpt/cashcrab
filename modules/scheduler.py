from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

from modules.config import section, ROOT

DB_PATH = ROOT / "jobs.sqlite"


def _make_scheduler() -> BlockingScheduler:
    return BlockingScheduler(
        jobstores={"default": SQLAlchemyJobStore(url=f"sqlite:///{DB_PATH}")},
        job_defaults={"coalesce": True, "max_instances": 1},
    )


def _youtube_job():
    from modules import video, youtube
    try:
        result = video.generate_short()
        youtube.upload(
            result["video_path"],
            result["title"],
            result["description"],
        )
        print(f"[scheduler] YouTube short uploaded: {result['title']}")
    except Exception as e:
        print(f"[scheduler] YouTube job failed: {e}")


def _twitter_job():
    from modules import twitter
    try:
        twitter.run_batch(count=1, affiliate_ratio=0.3)
        print("[scheduler] Twitter post done")
    except Exception as e:
        print(f"[scheduler] Twitter job failed: {e}")


def start():
    scheduler = _make_scheduler()

    yt_cfg = section("youtube")
    hours = yt_cfg.get("schedule_hours", [9])
    for h in hours:
        scheduler.add_job(
            _youtube_job, "cron", hour=h, minute=0,
            id=f"youtube_{h}", replace_existing=True,
        )
        print(f"YouTube job scheduled at {h:02d}:00 daily")

    tw_cfg = section("twitter")
    interval = tw_cfg.get("schedule_interval_minutes", 120)
    scheduler.add_job(
        _twitter_job, "interval", minutes=interval,
        id="twitter_bot", replace_existing=True,
    )
    print(f"Twitter job scheduled every {interval} minutes")

    print("\nScheduler running. Ctrl+C to stop.")
    try:
        scheduler.start()
    except KeyboardInterrupt:
        scheduler.shutdown()
        print("Scheduler stopped.")
