# service/task_manager.py
"""轻量级后台任务管理器（线程池），用于异步执行耗时任务（如报告生成）"""
import threading
import time
import uuid


class TaskManager:
    def __init__(self, max_workers=2):
        self._lock = threading.Lock()
        self._tasks = {}
        self._active = 0
        self._max_workers = max_workers

    def submit(self, name, func, *args, **kwargs):
        """提交任务，返回 task_id；func 可接收 kwargs 中的 progress_cb 回调更新进度"""
        task_id = uuid.uuid4().hex[:12]
        with self._lock:
            self._tasks[task_id] = {
                "id": task_id,
                "name": name,
                "status": "pending",
                "progress": 0,
                "message": "排队中",
                "result": None,
                "error": None,
                "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
        self._start_worker(task_id, func, args, kwargs)
        return task_id

    def _start_worker(self, task_id, func, args, kwargs):
        def worker():
            with self._lock:
                self._active += 1
                self._tasks[task_id]["status"] = "running"
                self._tasks[task_id]["message"] = "执行中"

            def progress_cb(pct, msg):
                self.update(task_id, progress=int(pct), message=str(msg))

            try:
                result = func(*args, **kwargs, progress_cb=progress_cb)
                with self._lock:
                    self._tasks[task_id]["status"] = "success"
                    self._tasks[task_id]["progress"] = 100
                    self._tasks[task_id]["message"] = "完成"
                    self._tasks[task_id]["result"] = result
            except TypeError:
                # func 不接受 progress_cb 参数
                try:
                    result = func(*args, **kwargs)
                    with self._lock:
                        self._tasks[task_id]["status"] = "success"
                        self._tasks[task_id]["progress"] = 100
                        self._tasks[task_id]["message"] = "完成"
                        self._tasks[task_id]["result"] = result
                except Exception as e:
                    with self._lock:
                        self._tasks[task_id]["status"] = "failed"
                        self._tasks[task_id]["error"] = str(e)
                        self._tasks[task_id]["message"] = "失败"
            except Exception as e:
                with self._lock:
                    self._tasks[task_id]["status"] = "failed"
                    self._tasks[task_id]["error"] = str(e)
                    self._tasks[task_id]["message"] = "失败"
            finally:
                with self._lock:
                    self._active -= 1

        t = threading.Thread(target=worker, daemon=True)
        t.start()

    def get(self, task_id):
        with self._lock:
            return self._tasks.get(task_id)

    def update(self, task_id, **kwargs):
        with self._lock:
            if task_id in self._tasks:
                self._tasks[task_id].update(kwargs)


task_manager = TaskManager()