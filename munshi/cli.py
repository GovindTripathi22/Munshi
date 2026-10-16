# munshi/cli.py
import sys
import json
from .graph import MunshiOrchestrator
from .evaluation.benchmark import run_munshi_benchmark

def main():
    if len(sys.argv) > 1 and sys.argv[1] == "benchmark":
        print(json.dumps(run_munshi_benchmark(), indent=2))
        return
    orch = MunshiOrchestrator()
    prompt = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Sold SaaS subscription to Bengaluru client for ₹50,000"
    res = orch.process_transaction(prompt)
    print(res["report_markdown"])

if __name__ == "__main__":
    main()
