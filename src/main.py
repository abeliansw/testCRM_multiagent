"""
증권사 영업 CRM 멀티에이전트 시스템
사용법:
  python src/main.py [customer_id]        # 단일 고객 분석
  python src/main.py --all                # 전체 고객 분석
  python src/main.py C001 --task "..."    # 커스텀 태스크
"""

import sys
import io
import argparse
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env", override=True)

# UTF-8 설정
if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr.encoding != "utf-8":
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).parent))

from agents.orchestrator import OrchestratorAgent
from tools import data_tools as dt

BANNER = """
╔══════════════════════════════════════════════════════════════╗
║   증권사 영업 CRM  멀티에이전트 시스템                       ║
║   Persona | NBA | Activity | QC | Orchestrator              ║
╚══════════════════════════════════════════════════════════════╝
"""


def run_single(customer_id: str, task: str | None = None) -> None:
    customer = dt.get_customer(customer_id)
    if not customer:
        print(f"[오류] 고객 ID '{customer_id}'를 찾을 수 없습니다.")
        print(f"사용 가능한 고객 ID: {[c['customer_id'] for c in dt.get_all_customers()]}")
        sys.exit(1)

    print(f"\n대상 고객: {customer['company_name']} ({customer_id})")
    print(f"담당자: {customer['contact']['name']} {customer['contact']['title']}")
    print(f"AUM: {customer['aum_billion_krw']:,}억원 | 등급: {customer['tier']}\n")

    orchestrator = OrchestratorAgent()
    orchestrator.run(customer_id, task)


def run_all() -> None:
    customers = dt.get_all_customers()
    print(f"\n전체 {len(customers)}개 고객 순차 분석 시작\n")
    for customer in customers:
        print(f"\n{'='*60}")
        print(f"  고객 {customer['customer_id']}: {customer['company_name']}")
        print(f"{'='*60}")
        orchestrator = OrchestratorAgent()
        orchestrator.run(customer["customer_id"])


def main() -> None:
    print(BANNER)

    parser = argparse.ArgumentParser(description="CRM 멀티에이전트 분석 시스템")
    parser.add_argument("customer_id", nargs="?", default="C001",
                        help="분석할 고객 ID (기본값: C001)")
    parser.add_argument("--all", action="store_true",
                        help="전체 고객 분석")
    parser.add_argument("--task", type=str, default=None,
                        help="커스텀 분석 태스크 설명")
    args = parser.parse_args()

    if args.all:
        run_all()
    else:
        run_single(args.customer_id, args.task)


if __name__ == "__main__":
    main()
