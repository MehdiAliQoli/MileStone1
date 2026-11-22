import queue
import time
from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from src.config import LANDING_DIR
from src.ingestion.db import init_schema
from src.ingestion.loader import load_file
from src.ingestion.metrics import utcnow

VALID_EXT = {".csv", ".xlsx"}
q = queue.Queue()
pending = set()
detected = {}


def _enqueue(path_str):
    p = Path(path_str)
    if p.suffix.lower() not in VALID_EXT or p.name.startswith(("~$", ".")):
        return
    if path_str not in pending:
        pending.add(path_str)
        detected[path_str] = utcnow()      # file arrival time (UTC)
        q.put(path_str)
        print(f"[watch]  detected {p.name}")


class Handler(FileSystemEventHandler):
    def on_created(self, event):
        if not event.is_directory:
            _enqueue(event.src_path)

    def on_moved(self, event):          # generator writes .tmp then renames
        if not event.is_directory:
            _enqueue(event.dest_path)


def wait_until_stable(path, checks=3, interval=1.0):
    """Wait until the file size stops changing (file fully written)."""
    last, stable = -1, 0
    while stable < checks:
        try:
            size = path.stat().st_size
        except FileNotFoundError:
            return False
        if size == last and size > 0:
            stable += 1
        else:
            stable, last = 0, size
        time.sleep(interval)
    return True


def main():
    init_schema()
    LANDING_DIR.mkdir(parents=True, exist_ok=True)

    for f in sorted(LANDING_DIR.iterdir()):      # files already waiting
        _enqueue(str(f))

    observer = Observer()
    observer.schedule(Handler(), str(LANDING_DIR), recursive=False)
    observer.start()
    print(f"Watching {LANDING_DIR}  (Ctrl+C to stop)")

    try:
        while True:
            try:
                path_str = q.get(timeout=1)
            except queue.Empty:
                continue
            pending.discard(path_str)
            det = detected.pop(path_str, None)
            p = Path(path_str)
            if wait_until_stable(p):
                load_file(p, move=True, detected_at=det)
    except KeyboardInterrupt:
        pass
    finally:
        observer.stop()
        observer.join()


if __name__ == "__main__":
    main()