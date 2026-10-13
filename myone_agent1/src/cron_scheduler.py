"""cron 定时（一次性相对延迟）。"""
import queue
import threading
import time
from threading import Thread

from langchain_core.tools import tool

CRON_JOBS:list[dict] = []
CRON_COUNTER = [0]
CRON_QUEUE: "queue.Queue[str]" = queue.Queue()

@tool
def list_crons() ->str:
    """列出计划的cron任务及其每项触发前的剩余时间。"""
    if not CRON_JOBS:
        return "(no cron jobs)"
    now = time.time()
    return "\n".join(
        f"#{j['id']} due_in={int(j['due'] - now)}s delivered={j['delivered']} {j['prompt']}"
        for j in CRON_JOBS
    )

@tool
def schedule_cron(prompt: str, seconds: int = 30) ->str:
    """安排一个一次性定时提醒：seconds 秒后把 prompt 注入会话。"""
    if seconds < 1:
        return "Error: seconds 必须 >= 1"
    CRON_COUNTER[0] += 1
    job_id = CRON_COUNTER[0]
    CRON_JOBS.append({
        "id": job_id,
        "prompt": prompt,
        "due": time.time() + seconds,
        "delivered": False,
    })
    return f"scheduled cron #{job_id} in {seconds}s"

@tool
def cancel_cron(job_id:int) ->str:
    """取消指定的cron任务。"""
    for j in CRON_JOBS:
        if j["id"] == job_id:
            j["delivered"] = True
            j["due"] = 0
            return f"cancelled cron #{job_id}"
    return f"unknown cron #{job_id}"

def cron_worker():
    """守护线程，每秒扫描一次到期任务，把 prompt 放进 CRON_QUEUE。"""
    while True:
        time.sleep(1)
        now=time.time()
        for j in CRON_JOBS:
            if not j["delivered"] and j["due"] <= now:
                j["delivered"] = True
                CRON_QUEUE.put(j["prompt"])



threading.Thread(target=cron_worker,daemon=True).start()
