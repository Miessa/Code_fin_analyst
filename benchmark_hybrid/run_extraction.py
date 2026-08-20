"""Run benchmark discovery. Approved reference data is never overwritten."""

import argparse
from .pipeline import HybridBenchmarkPipeline


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--use-llm", action="store_true", help="Use bounded Gemini assistance")
    parser.add_argument("--max-llm-calls", type=int, default=3)
    args = parser.parse_args(argv)
    staged, path = HybridBenchmarkPipeline().run(args.use_llm, args.max_llm_calls)
    ok = sum(x["status"] == "EXTRACTED" for x in staged["sources"])
    print(f"Sources extracted: {ok}/{len(staged['sources'])}")
    print(f"Staging: {path}")


if __name__ == "__main__":
    main()
