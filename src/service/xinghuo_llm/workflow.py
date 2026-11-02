from typing import List, Dict, Any, Callable, Optional
import time


class WorkflowStep:
    def __init__(self, name: str, func, inputs: dict = None,
                 condition: Callable = None, max_retries: int = 0,
                 timeout: Optional[float] = None):
        self.name = name
        self.func = func
        self.inputs = inputs or {}
        self.condition = condition
        self.max_retries = max_retries
        self.timeout = timeout
        self.output = None
        self.status = "pending"
        self.error = None
        self.elapsed = 0.0

    def should_run(self, context: dict) -> bool:
        if self.condition is None:
            return True
        try:
            return bool(self.condition(context))
        except Exception as e:
            self.error = f"条件判断异常: {e}"
            return False


class WorkflowEngine:
    def __init__(self):
        self.steps: List[WorkflowStep] = []
        self.context = {}

    def add_step(self, name: str, func, inputs: dict = None,
                 condition: Callable = None, max_retries: int = 0,
                 timeout: Optional[float] = None):
        self.steps.append(WorkflowStep(name, func, inputs, condition,
                                       max_retries, timeout))
        return self

    def execute(self, initial_context: dict = None) -> List[dict]:
        if initial_context:
            self.context.update(initial_context)
        results = []
        for step in self.steps:
            if not step.should_run(self.context):
                step.status = "skipped"
                results.append({"step": step.name, "status": "skipped",
                                "output": None, "error": None, "elapsed": 0.0})
                continue
            start = time.time()
            attempts = 0
            output = None
            while True:
                attempts += 1
                try:
                    combined = {**self.context, **step.inputs}
                    output = step.func(**combined)
                    step.output = output
                    step.status = "success"
                    self.context[step.name] = output
                    break
                except Exception as e:
                    step.error = str(e)
                    if attempts <= step.max_retries:
                        time.sleep(min(1.0 * attempts, 3.0))
                        continue
                    step.status = "failed"
                    output = {"error": str(e)}
                    break
            step.elapsed = time.time() - start
            results.append({"step": step.name, "status": step.status,
                            "output": output, "error": step.error,
                            "elapsed": round(step.elapsed, 3)})
        return results