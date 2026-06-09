"""
scripts/run_batch_10.py
-----------------------
Runs the 10-company ESG analysis batch.

Usage (from project root):
    .\\venv\\Scripts\\python.exe scripts\\run_batch_10.py

Options:
    --parallel N   Run N analyses in parallel (default: 1 = sequential)
    --only NAMES   Comma-separated subset, e.g. --only "Microsoft,Tesla"
    --dry-run      Print commands without executing
    --log-dir DIR  Override log directory (default: logs/batch/)
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

# ── Configuration ─────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
VENV_PYTHON  = PROJECT_ROOT / "venv" / "Scripts" / "python.exe"
if not VENV_PYTHON.exists():
    VENV_PYTHON = PROJECT_ROOT / "venv" / "bin" / "python"
if not VENV_PYTHON.exists():
    VENV_PYTHON = Path(sys.executable)

MAIN_SCRIPT = PROJECT_ROOT / "main_langgraph.py"

# ── The 10 target companies ───────────────────────────────────────────────────
TARGETS = [
    {
        "company":  "JPMorgan Chase",
        "claim":    "Committed to financing and facilitating $2.5 trillion toward sustainable development and climate action by 2030",
        "industry": "Banking",
    },
    {
        "company":  "Microsoft",
        "claim":    "Microsoft will be carbon negative by 2030",
        "industry": "Technology",
    },
    {
        "company":  "Shell",
        "claim":    "Net zero emissions by 2050",
        "industry": "Oil & Gas",
    },
    {
        "company":  "Volkswagen",
        "claim":    "Committed to sustainable mobility and decarbonization",
        "industry": "Automotive",
    },
    {
        "company":  "Tesla",
        "claim":    "Accelerating the world's transition to sustainable energy",
        "industry": "Automotive",
    },
    {
        "company":  "Unilever",
        "claim":    "Making sustainable living commonplace",
        "industry": "Consumer Goods",
    },
    {
        "company":  "H&M Group",
        "claim":    "Becoming climate positive and achieving net-zero emissions by 2040",
        "industry": "Fashion",
    },
    {
        "company":  "AstraZeneca",
        "claim":    "Delivering zero-carbon healthcare and achieving net zero by 2045",
        "industry": "Pharmaceuticals",
    },
    {
        "company":  "Walmart",
        "claim":    "Achieve zero emissions across global operations by 2040",
        "industry": "Retail",
    },
    {
        "company":  "Amazon",
        "claim":    "Net-zero carbon by 2040 through The Climate Pledge",
        "industry": "Technology",
    },
]

# ── Colours (Windows-safe via ANSI) ───────────────────────────────────────────
os.system("")  # enable ANSI on Windows
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"


def banner():
    print(f"\n{BOLD}{CYAN}{'='*70}")
    print(f"  ESGLens — Batch Analysis Runner (10 Companies)")
    print(f"  {datetime.now().strftime('%Y-%m-%d  %H:%M:%S')}")
    print(f"{'='*70}{RESET}\n")


def run_single(target: dict, log_dir: Path, dry_run: bool) -> dict:
    company  = target["company"]
    claim    = target["claim"]
    industry = target["industry"]

    slug     = company.lower().replace(" ", "_").replace("&", "and")
    ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"{slug}_{ts}.log"

    cmd = [
        str(VENV_PYTHON),
        str(MAIN_SCRIPT),
        "--company",  company,
        "--claim",    claim,
        "--industry", industry,
    ]

    print(f"{CYAN}>> START{RESET}  {BOLD}{company}{RESET}  [{industry}]")
    print(f"         {YELLOW}Claim:{RESET} {claim[:80]}{'...' if len(claim) > 80 else ''}")
    print(f"         {YELLOW}Log:  {RESET} {log_file.name}")

    if dry_run:
        print(f"         {YELLOW}[DRY-RUN] Command:{RESET} {' '.join(cmd)}\n")
        return {"company": company, "status": "dry_run", "duration": 0, "log": str(log_file)}

    t0 = time.time()
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        with open(log_file, "w", encoding="utf-8") as lf:
            lf.write(f"# ESGLens batch run — {company}\n")
            lf.write(f"# Started: {datetime.now().isoformat()}\n")
            lf.write(f"# Command: {' '.join(cmd)}\n\n")
            proc = subprocess.run(
                cmd,
                cwd=str(PROJECT_ROOT),
                stdout=lf,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                env={**os.environ, "PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8"},
            )
        duration = time.time() - t0
        rc = proc.returncode

        # Find most recent JSON report for this company
        reports_dir = PROJECT_ROOT / "reports"
        report_path = None
        if reports_dir.exists():
            candidates = sorted(
                [p for p in reports_dir.glob("*.json")
                 if slug in p.stem.lower()
                 and "lineage" not in p.stem
                 and "FULL" not in p.stem
                 and "_brief" not in p.stem.lower()
                 and "research_runs" not in p.stem],
                key=lambda f: f.stat().st_mtime,
                reverse=True,
            )
            if candidates:
                report_path = candidates[0]

        if rc != 0:
            print(f"{RED}FAIL  {RESET}  {BOLD}{company}{RESET}  exit={rc}  [{duration:.0f}s]")
            return {"company": company, "status": "error", "rc": rc,
                    "duration": duration, "log": str(log_file), "report": None}

        if report_path is None:
            print(f"{YELLOW}!! DONE  {RESET}  {BOLD}{company}{RESET}  no JSON found  [{duration:.0f}s]")
            return {"company": company, "status": "no_report", "duration": duration,
                    "log": str(log_file), "report": None}

        # Quick-read headline score from report JSON
        score_str = ""
        try:
            with open(report_path, encoding="utf-8") as rf:
                rdata = json.load(rf)
            score = (rdata.get("overall_risk_score")
                     or rdata.get("esg_score")
                     or rdata.get("headline_score")
                     or rdata.get("scores", {}).get("overall_greenwashing_risk"))
            verdict = (rdata.get("final_verdict")
                       or rdata.get("verdict")
                       or rdata.get("risk_level", ""))
            if isinstance(verdict, dict):
                verdict = verdict.get("verdict") or verdict.get("risk_level", "")
            if score is not None:
                score_str = f"  score={score}  verdict={verdict}"
        except Exception:
            pass

        print(f"{GREEN}OK DONE  {RESET}  {BOLD}{company}{RESET}{score_str}  [{duration:.0f}s]")
        print(f"         Report -> {report_path.name}\n")
        return {"company": company, "status": "ok", "duration": duration,
                "log": str(log_file), "report": str(report_path)}

    except Exception as exc:
        duration = time.time() - t0
        print(f"{RED}ERROR {RESET}  {BOLD}{company}{RESET}  {exc}  [{duration:.0f}s]\n")
        return {"company": company, "status": "exception", "error": str(exc),
                "duration": duration, "log": str(log_file), "report": None}


def print_summary(results: list[dict], total_time: float):
    print(f"\n{BOLD}{CYAN}{'='*70}")
    print(f"  BATCH SUMMARY")
    print(f"{'='*70}{RESET}")

    ok    = [r for r in results if r["status"] == "ok"]
    fails = [r for r in results if r["status"] not in ("ok", "dry_run")]

    print(f"\n  {'Company':<24} {'Status':<12} {'Duration':>10}  Report")
    print(f"  {'-'*66}")
    for r in results:
        status = r["status"]
        dur    = f"{r['duration']:.0f}s" if r.get("duration") else "-"
        rep    = Path(r["report"]).name if r.get("report") else "-"
        col    = GREEN if status == "ok" else (YELLOW if status in ("no_report", "dry_run") else RED)
        tag    = "[OK]" if status == "ok" else ("[" + status[:8] + "]")
        print(f"  {r['company']:<24} {col}{tag:<12}{RESET} {dur:>10}  {rep}")

    print(f"\n  Passed : {GREEN}{len(ok)}/{len(results)}{RESET}")
    print(f"  Failed : {RED}{len(fails)}/{len(results)}{RESET}")
    print(f"  Total  : {total_time:.0f}s  (~{total_time/60:.1f} min)")
    print(f"{BOLD}{CYAN}{'='*70}{RESET}\n")

    # Write JSON summary
    summary_path = PROJECT_ROOT / "logs" / "batch_summary.json"
    summary_path.parent.mkdir(exist_ok=True)
    with open(summary_path, "w", encoding="utf-8") as sf:
        json.dump({"run_at": datetime.now().isoformat(), "results": results}, sf, indent=2)
    print(f"  Summary JSON -> {summary_path}\n")


def main():
    parser = argparse.ArgumentParser(
        description="Run ESGLens batch analysis for 10 companies",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run all 10 sequentially (default)
  .\\venv\\Scripts\\python scripts\\run_batch_10.py

  # Run only Microsoft and Tesla
  .\\venv\\Scripts\\python scripts\\run_batch_10.py --only "Microsoft,Tesla"

  # Preview commands without running
  .\\venv\\Scripts\\python scripts\\run_batch_10.py --dry-run

  # Run 2 in parallel (uses more RAM/CPU)
  .\\venv\\Scripts\\python scripts\\run_batch_10.py --parallel 2
""",
    )
    parser.add_argument("--parallel", type=int, default=1,
                        help="Number of parallel workers (default: 1 = sequential)")
    parser.add_argument("--only", type=str, default="",
                        help="Comma-separated company names to run (subset)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print commands without running")
    parser.add_argument("--log-dir", type=str,
                        default=str(PROJECT_ROOT / "logs" / "batch"),
                        help="Directory to write log files")
    args = parser.parse_args()

    log_dir = Path(args.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    # Filter targets
    targets = TARGETS
    if args.only:
        allowed = {n.strip().lower() for n in args.only.split(",")}
        targets = [t for t in TARGETS if t["company"].lower() in allowed]
        if not targets:
            print(f"{RED}No matching companies for --only '{args.only}'{RESET}")
            sys.exit(1)

    banner()
    print(f"  Companies to run : {BOLD}{len(targets)}{RESET}")
    print(f"  Parallel workers : {BOLD}{args.parallel}{RESET}")
    print(f"  Log directory    : {log_dir}")
    print(f"  Python           : {VENV_PYTHON}\n")

    t0 = time.time()
    results = []

    if args.parallel == 1:
        # Sequential — simplest, safest, most readable output
        for i, target in enumerate(targets, 1):
            print(f"{BOLD}[{i}/{len(targets)}]{RESET} ", end="")
            result = run_single(target, log_dir, args.dry_run)
            results.append(result)
    else:
        # Parallel — faster but output interleaves
        print(f"{YELLOW}Running {args.parallel} workers in parallel…{RESET}\n")
        with ThreadPoolExecutor(max_workers=args.parallel) as pool:
            futures = {
                pool.submit(run_single, t, log_dir, args.dry_run): t
                for t in targets
            }
            for future in as_completed(futures):
                results.append(future.result())

    total = time.time() - t0
    print_summary(results, total)


if __name__ == "__main__":
    main()
