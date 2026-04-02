import time
from pathlib import Path

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from modules.config import section, ROOT
from modules.auth import youtube_credentials


def _service():
    creds = youtube_credentials()
    return build("youtube", "v3", credentials=creds)


def upload(file_path: str, title: str, description: str = "",
           tags: list[str] | None = None, privacy: str | None = None) -> str:
    cfg = section("youtube")
    tags = tags or cfg.get("default_tags", [])
    privacy = privacy or cfg.get("privacy_status", "public")

    youtube = _service()
    body = {
        "snippet": {
            "title": title[:100],
            "description": description[:5000],
            "tags": tags,
            "categoryId": cfg.get("category_id", "22"),
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(file_path, mimetype="video/mp4", resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    print(f"Uploading: {Path(file_path).name}")
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            pct = int(status.progress() * 100)
            print(f"  {pct}%", end="\r")

    video_id = response["id"]
    url = f"https://youtube.com/shorts/{video_id}"
    print(f"  Uploaded: {url}")
    return video_id


def upload_pending():
    cfg = section("youtube")
    folder = Path(cfg.get("shorts_folder", "./shorts"))
    if not folder.exists():
        print(f"Shorts folder not found: {folder}")
        return []

    videos = sorted(folder.glob("*.mp4"))
    uploaded_log = folder / ".uploaded"
    done = set()
    if uploaded_log.exists():
        done = set(uploaded_log.read_text().strip().splitlines())

    pending = [v for v in videos if v.name not in done]
    if not pending:
        print("No pending videos.")
        return []

    print(f"{len(pending)} video(s) to upload.")
    tags = cfg.get("default_tags", [])
    ids = []

    for v in pending:
        title = v.stem.replace("_", " ").replace("-", " ").title()
        try:
            vid = upload(str(v), title, tags=tags)
            with open(uploaded_log, "a") as f:
                f.write(v.name + "\n")
            ids.append(vid)
            time.sleep(3)
        except Exception as e:
            print(f"  Failed: {v.name} - {e}")

    return ids


def status():
    cfg = section("youtube")
    folder = Path(cfg.get("shorts_folder", "./shorts"))
    if not folder.exists():
        print(f"Shorts folder not found: {folder}")
        return

    videos = sorted(folder.glob("*.mp4"))
    uploaded_log = folder / ".uploaded"
    done = set()
    if uploaded_log.exists():
        done = set(uploaded_log.read_text().strip().splitlines())

    pending = [v for v in videos if v.name not in done]
    print(f"Total: {len(videos)} | Uploaded: {len(done)} | Pending: {len(pending)}")
    for v in pending:
        print(f"  pending: {v.name}")
    for d in sorted(done):
        print(f"  done:    {d}")
