"""s15 后台任务：后台 bash + 完成通知队列。"""
import queue
import subprocess
import threading

from tools import WORKDIR

BACKGROUND_RESULTS: "queue.Queue[str]" = queue.Queue()
BG_COUNTER = [0]

def start_background_task(command:str)-> str:
    """在守护线程里跑命令；完成后把 <task_notification> 放进队列，由循环注入。"""
    BG_COUNTER[0] += 1
    task_id=BG_COUNTER[0]

    def worker():
        try:
            r = subprocess.run(command, shell=True, cwd=WORKDIR, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
            out = (r.stdout + r.stderr).strip() or "(no output)"
            status = "completed" if r.returncode == 0 else f"failed (exit {r.returncode})"
        except Exception as e:
            out = f"Error: {e}"
            status = "failed"

        BACKGROUND_RESULTS.put(
            f"<task_notification>[background #{task_id}] {status}:\n{out[:4000]}</task_notification>"
        )
    threading.Thread(target=worker).start()
    return f"started background task {task_id};its result will arrive as a notification"



