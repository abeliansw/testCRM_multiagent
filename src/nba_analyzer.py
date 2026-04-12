"""
증권사 영업 CRM - Next Best Action (NBA) 분석기
자산운용사 및 연기금 고객 대상 최적 다음 행동 추천 시스템
"""

import json
import os
import sys
import io
from pathlib import Path
from anthropic import Anthropic

# Windows 콘솔 UTF-8 출력 설정
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
if sys.stderr.encoding != 'utf-8':
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# 프로젝트 루트 경로
ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


def load_json(filename: str) -> list:
    with open(DATA_DIR / filename, encoding="utf-8") as f:
        return json.load(f)


def build_customer_context(customer_id: str, customers, sales_notes, action_plans) -> str:
    """특정 고객의 모든 데이터를 컨텍스트 문자열로 조합"""
    customer = next(c for c in customers if c["customer_id"] == customer_id)
    notes = [n for n in sales_notes if n["customer_id"] == customer_id]
    plans = [p for p in action_plans if p["customer_id"] == customer_id]

    # 날짜 최신순 정렬
    notes_sorted = sorted(notes, key=lambda x: x["date"], reverse=True)
    plans_sorted = sorted(plans, key=lambda x: x["created_date"], reverse=True)

    ctx = f"""
=== 고객 기본 정보 ===
- 회사명: {customer['company_name']} ({customer['company_type']})
- 운용규모(AUM): {customer['aum_billion_krw']:,}억원
- 담당자: {customer['contact']['name']} ({customer['contact']['title']})
- 위탁 운용 전략: {', '.join(customer['investment_mandate'])}
- 벤치마크: {customer['benchmark']}
- 거래 시작: {customer['relationship_since']}
- 고객 등급: {customer['tier']}
- 담당 영업: {customer['assigned_salesperson']}

=== 최근 Sales Notes (최신순) ===
"""
    for note in notes_sorted:
        ctx += f"""
[{note['date']}] [{note['channel']}] {note['title']}
내용: {note['content']}
감정 상태: {note['sentiment']}
핵심 우려사항: {', '.join(note['key_concerns']) if note['key_concerns'] else '없음'}
관심 표명: {', '.join(note['expressed_interests']) if note['expressed_interests'] else '없음'}
{f"체결 거래: {note['deals_executed']}" if note.get('deals_executed') else ''}
후속 필요: {'예' if note.get('follow_up_required') else '아니오'}
---"""

    ctx += "\n\n=== Action Plan 현황 ===\n"
    for plan in plans_sorted:
        ctx += f"""
[{plan['status']}] {plan['title']} (생성: {plan['created_date']})
"""
        for action in plan['actions']:
            status_icon = "✅" if action['status'] == "완료" else "⏳" if action['status'] == "진행중" else "❌"
            result_str = f" → 결과: {action['result']}" if action.get('result') else ""
            ctx += f"  {status_icon} {action['action']} (기한: {action['due']}){result_str}\n"
        if plan.get('outcome'):
            ctx += f"  종합결과: {plan['outcome']}\n"
        ctx += "---"

    return ctx


def analyze_nba(customer_id: str, analysis_date: str = "2025-12-01") -> dict:
    """Claude API를 활용한 멀티턴 NBA 분석"""
    client = Anthropic()

    customers = load_json("customers.json")
    sales_notes = load_json("sales_notes.json")
    action_plans = load_json("action_plans.json")

    context = build_customer_context(customer_id, customers, sales_notes, action_plans)
    customer = next(c for c in customers if c["customer_id"] == customer_id)

    print(f"\n{'='*60}")
    print(f"NBA 분석 시작: {customer['company_name']} ({customer_id})")
    print(f"분석 기준일: {analysis_date}")
    print(f"{'='*60}")

    # 시스템 프롬프트
    system_prompt = """당신은 증권사 기관영업 전문 CRM 분석 AI입니다.
자산운용사와 연기금 고객을 담당하는 영업 담당자(RM)를 보조합니다.

역할:
- 고객의 Sales Notes와 Action Plan 이력을 분석하여 고객 성향과 니즈를 파악
- 현재 미완료 Action Item과 고객 관심사를 종합하여 최적의 Next Best Action 도출
- 각 추천 행동에 대한 구체적인 실행 방법과 예상 효과 제시

분석 원칙:
1. 고객이 명시적으로 관심 표명한 항목 우선
2. 과거 성공 패턴(거래 체결, 긍정 피드백) 반복 활용
3. 미완료 Action Item 중 기한 초과 또는 임박한 항목 긴급 처리
4. 고객의 부정적 경험(차별성 부재, 관심 없는 섹터 연락 등) 회피
5. 경쟁사 대비 당사 강점을 활용한 차별화 포인트 강조"""

    conversation_history = []

    # ─── Turn 1: 고객 성향 분석 ───
    print("\n[Turn 1] 고객 성향 분석 중...")
    turn1_prompt = f"""아래는 분석 기준일({analysis_date}) 기준 고객 데이터입니다.

{context}

먼저 이 고객의 핵심 성향을 분석해주세요:
1. 고객이 가장 중시하는 서비스 요소 (Top 3)
2. 고객의 투자 관심 섹터/테마 우선순위
3. 불만족 또는 회피해야 할 접근 방식
4. 고객과의 관계 현황 (강점/취약점)
5. 경쟁사 대비 당사 포지션"""

    conversation_history.append({"role": "user", "content": turn1_prompt})

    response1 = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=1500,
        system=system_prompt,
        messages=conversation_history
    )
    analysis_result = response1.content[0].text
    conversation_history.append({"role": "assistant", "content": analysis_result})

    print(analysis_result)

    # ─── Turn 2: 미완료 액션 긴급도 평가 ───
    print("\n[Turn 2] 미완료 Action Item 긴급도 평가 중...")
    turn2_prompt = f"""위 성향 분석을 바탕으로, 현재 미완료 상태인 Action Item들의 긴급도를 평가해주세요.

기준일: {analysis_date}
각 미완료 액션에 대해:
- 긴급도: 🔴 긴급 / 🟡 보통 / 🟢 여유
- 기한 초과 여부
- 고객 관계에 미치는 영향
- 처리 순서 추천"""

    conversation_history.append({"role": "user", "content": turn2_prompt})

    response2 = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=1200,
        system=system_prompt,
        messages=conversation_history
    )
    urgency_result = response2.content[0].text
    conversation_history.append({"role": "assistant", "content": urgency_result})

    print(urgency_result)

    # ─── Turn 3: NBA 도출 ───
    print("\n[Turn 3] Next Best Action 도출 중...")
    turn3_prompt = """앞선 분석을 종합하여, 이 고객에 대한 Next Best Action을 다음 형식으로 제시해주세요:

## Next Best Action 추천

### 즉시 실행 (이번 주 내)
[행동 1]
- 구체적 실행 방법:
- 예상 고객 반응:
- 성공 지표:

### 단기 실행 (2주 내)
[행동 2]
...

### 중기 실행 (1개월 내)
[행동 3]
...

### 절대 하지 말아야 할 것
...

### 예상 성과 (향후 3개월)
- 관계 강화 측면:
- 거래 창출 가능성:"""

    conversation_history.append({"role": "user", "content": turn3_prompt})

    response3 = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=2000,
        system=system_prompt,
        messages=conversation_history
    )
    nba_result = response3.content[0].text
    conversation_history.append({"role": "assistant", "content": nba_result})

    print(nba_result)

    # ─── Turn 4: 실행 스크립트 작성 ───
    print("\n[Turn 4] 영업 실행 스크립트 작성 중...")
    turn4_prompt = """최우선 즉시 실행 액션에 대해, 영업 담당자가 바로 사용할 수 있는 실행 스크립트를 작성해주세요:

1. 이메일 초안 (제목 포함, 200자 내외)
2. 전화 오프닝 멘트 (30초 분량)
3. 예상 질문/반론 및 대응 멘트 2가지

실제 담당자 이름과 고객 이름을 사용해주세요."""

    conversation_history.append({"role": "user", "content": turn4_prompt})

    response4 = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=1500,
        system=system_prompt,
        messages=conversation_history
    )
    script_result = response4.content[0].text
    conversation_history.append({"role": "assistant", "content": script_result})

    print(script_result)

    # 결과 저장
    output = {
        "customer_id": customer_id,
        "company_name": customer["company_name"],
        "analysis_date": analysis_date,
        "turn1_persona_analysis": analysis_result,
        "turn2_urgency_assessment": urgency_result,
        "turn3_next_best_actions": nba_result,
        "turn4_execution_scripts": script_result
    }

    output_path = OUTPUT_DIR / f"nba_{customer_id}_{analysis_date}.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 분석 완료. 결과 저장: {output_path}")
    return output


def run_all_customers(analysis_date: str = "2025-12-01"):
    """모든 고객에 대해 NBA 분석 실행"""
    customers = load_json("customers.json")
    results = []
    for customer in customers:
        result = analyze_nba(customer["customer_id"], analysis_date)
        results.append(result)

    # 전체 요약 저장
    summary_path = OUTPUT_DIR / f"nba_summary_{analysis_date}.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n📋 전체 고객 NBA 분석 완료: {summary_path}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        customer_id = sys.argv[1]
        date = sys.argv[2] if len(sys.argv) > 2 else "2025-12-01"
        analyze_nba(customer_id, date)
    else:
        # 기본 실행: C001 한국미래자산운용 단독 분석
        analyze_nba("C001", "2025-12-01")
