"""Daily SQLite backup (systemd: tradewave-rt-backup). Keeps 14 days."""
import datetime
import pathlib
import sqlite3

SRC = "/home/flask/tradewave_realtime/data/tradewave_rt.db"
DST_DIR = pathlib.Path("/home/flask/backups")
DST_DIR.mkdir(exist_ok=True)

dst = DST_DIR / f"tradewave_rt_{datetime.date.today().isoformat()}.db"
src = sqlite3.connect(SRC)
out = sqlite3.connect(dst)
src.backup(out)
out.close()
src.close()
print(f"backed up -> {dst}")

cutoff = datetime.date.today() - datetime.timedelta(days=14)
for f in DST_DIR.glob("tradewave_rt_*.db"):
    if f.stem.replace("tradewave_rt_", "") < cutoff.isoformat():
        f.unlink()
