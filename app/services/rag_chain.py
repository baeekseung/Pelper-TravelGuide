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

USER_PROMPT = """
"""


async def run_chain(user_query: str, context: str, model_name: str = "gpt-4o-mini") -> str:
    llm = ChatOpenAI(api_key=settings.openai_api_key, model=model_name, temperature=0.2)
    ctx = context
    messages = [
        SystemMessage(content=SYSTEM_PROMPT + "\n\n자료:\n" + ctx),
        HumanMessage(content=USER_PROMPT),
    ]
    resp = await llm.ainvoke(messages)
    return resp.content
