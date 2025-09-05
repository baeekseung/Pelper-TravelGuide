from typing import List, Dict
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage
from ..config import settings

SYSTEM_PROMPT = """당신은 지역 맞춤 여행 가이드입니다.
- 한국어 존댓말로 간결하게 답하세요.
- 사용자가 알려준 중심 위치 반경 내의 정보만 우선 제안합니다.
- 추천마다 '이유'와 '거리(대략)'를 함께 적고, 마지막에 참고한 출처를 나열하세요.
- 안전/영업시간/휴무일은 불확실하면 '확인 필요'라고 명시하세요.
- 링크는 너무 많이 넣지 말고 핵심 출처만 제공합니다.
"""

def build_context_block(collected: List[Dict]) -> str:
    lines = []
    for i, c in enumerate(collected, 1):
        lines.append(f"[{i}] {c['title']} | {c['url']} | type={c['type']}")
        if "snippet" in c and c["snippet"]:
            lines.append(f"snippet: {c['snippet'][:240]}")
    return "\n".join(lines)

async def run_chain(user_query: str, collected: List[Dict], model_name: str = "gpt-4o-mini") -> str:
    llm = ChatOpenAI(api_key=settings.openai_api_key, model=model_name, temperature=0.2)
    ctx = build_context_block(collected)
    messages = [
        SystemMessage(content=SYSTEM_PROMPT + "\n\n자료:\n" + ctx),
        HumanMessage(content=user_query),
    ]
    resp = await llm.ainvoke(messages)
    return resp.content
