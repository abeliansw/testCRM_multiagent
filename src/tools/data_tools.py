"""
CRM 데이터 액세스 레이어
모든 JSON 파일 읽기/쓰기를 담당하는 순수 데이터 함수 모음
"""

import json
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).parent.parent.parent
DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


def _load(filename: str) -> list | dict:
    path = DATA_DIR / filename
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _save(filename: str, data: list | dict) -> None:
    path = DATA_DIR / filename
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ─── 원본 데이터 조회 ───────────────────────────────────────────

def get_customer(customer_id: str) -> dict | None:
    customers = _load("customers.json")
    return next((c for c in customers if c["customer_id"] == customer_id), None)


def get_all_customers() -> list:
    return _load("customers.json")


def get_sales_notes(customer_id: str) -> list:
    notes = _load("sales_notes.json")
    result = [n for n in notes if n["customer_id"] == customer_id]
    return sorted(result, key=lambda x: x["date"], reverse=True)


def get_action_plans(customer_id: str) -> list:
    plans = _load("action_plans.json")
    result = [p for p in plans if p["customer_id"] == customer_id]
    return sorted(result, key=lambda x: x["created_date"], reverse=True)


def get_pending_actions(customer_id: str) -> list:
    """미완료 Action Item만 추출"""
    plans = get_action_plans(customer_id)
    pending = []
    for plan in plans:
        for action in plan.get("actions", []):
            if action["status"] != "완료":
                pending.append({
                    "plan_id": plan["plan_id"],
                    "plan_title": plan["title"],
                    "action": action["action"],
                    "due": action["due"],
                    "status": action["status"],
                })
    return pending


# ─── 페르소나 관리 ──────────────────────────────────────────────

def save_persona(customer_id: str, persona: dict) -> None:
    personas = _load("personas.json") if (DATA_DIR / "personas.json").exists() else []
    if not isinstance(personas, list):
        personas = []
    personas = [p for p in personas if p.get("customer_id") != customer_id]
    persona["customer_id"] = customer_id
    persona["updated_at"] = datetime.now().strftime("%Y-%m-%d")
    personas.append(persona)
    _save("personas.json", personas)


def get_persona(customer_id: str) -> dict | None:
    personas = _load("personas.json") if (DATA_DIR / "personas.json").exists() else []
    return next((p for p in personas if p.get("customer_id") == customer_id), None)


# ─── NBA 추천 관리 ──────────────────────────────────────────────

def save_nba(customer_id: str, nba_data: dict) -> None:
    nba_list = _load("nba_results.json") if (DATA_DIR / "nba_results.json").exists() else []
    if not isinstance(nba_list, list):
        nba_list = []
    nba_list = [n for n in nba_list if n.get("customer_id") != customer_id]
    nba_data["customer_id"] = customer_id
    nba_data["generated_at"] = datetime.now().strftime("%Y-%m-%d")
    nba_list.append(nba_data)
    _save("nba_results.json", nba_list)


def get_nba(customer_id: str) -> dict | None:
    nba_list = _load("nba_results.json") if (DATA_DIR / "nba_results.json").exists() else []
    return next((n for n in nba_list if n.get("customer_id") == customer_id), None)


# ─── 활동 일정 관리 ─────────────────────────────────────────────

def save_activities(customer_id: str, activities: list) -> None:
    all_acts = _load("activities.json") if (DATA_DIR / "activities.json").exists() else []
    if not isinstance(all_acts, list):
        all_acts = []
    all_acts = [a for a in all_acts if a.get("customer_id") != customer_id]
    all_acts.append({"customer_id": customer_id, "activities": activities})
    _save("activities.json", all_acts)


def get_activities(customer_id: str) -> list:
    all_acts = _load("activities.json") if (DATA_DIR / "activities.json").exists() else []
    entry = next((a for a in all_acts if a.get("customer_id") == customer_id), None)
    return entry["activities"] if entry else []


# ─── QC 보고서 관리 ─────────────────────────────────────────────

def save_qc_report(customer_id: str, report: dict) -> None:
    reports = _load("qc_reports.json") if (DATA_DIR / "qc_reports.json").exists() else []
    if not isinstance(reports, list):
        reports = []
    reports = [r for r in reports if r.get("customer_id") != customer_id]
    report["customer_id"] = customer_id
    report["reviewed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    reports.append(report)
    _save("qc_reports.json", reports)


def get_qc_report(customer_id: str) -> dict | None:
    reports = _load("qc_reports.json") if (DATA_DIR / "qc_reports.json").exists() else []
    return next((r for r in reports if r.get("customer_id") == customer_id), None)


# ─── 전체 컨텍스트 조합 ─────────────────────────────────────────

def build_raw_context(customer_id: str) -> dict:
    """에이전트에게 전달할 원본 데이터 전체 조합"""
    return {
        "customer": get_customer(customer_id),
        "sales_notes": get_sales_notes(customer_id),
        "action_plans": get_action_plans(customer_id),
        "pending_actions": get_pending_actions(customer_id),
    }


def build_full_context(customer_id: str) -> dict:
    """에이전트 결과물까지 포함한 전체 컨텍스트"""
    return {
        **build_raw_context(customer_id),
        "persona": get_persona(customer_id),
        "nba": get_nba(customer_id),
        "activities": get_activities(customer_id),
        "qc_report": get_qc_report(customer_id),
    }
