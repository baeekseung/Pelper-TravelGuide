from typing import List, Dict
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage
from ..config import settings
from dotenv import load_dotenv
load_dotenv()

from langchain_teddynote import logging
logging.langsmith("PELPER")

SYSTEM_PROMPT = """당신은 여행 가이드입니다.
사용자는 당신에게 여행에 대한 요청사항을 알려주면 그에 맞는 여행 정보를 제공합니다.
주어지는 자료는 사용자의 요청사항에 맞게 네이버에서 추천장소 정보와 그에 해당하는 블로그 및 리뷰 내용입니다.
5개 이하의 장소정보가 제공되고, 당신은 이를 기반으로 자료에 포함된 모든 장소의 정보를 요약해서 제공합니다.
답변은 주어진 자료를 최대한 자세하게, 사용자의 요청에 적절한 답변을 해주세요.
답변에서 블로그 내용을 언급할때 출처 링크를 달아주세요.
만약 주어진 자료가 없다면 "주변에 알맞는 장소가 없습니다" 라고 답변해줘.
주 언어는 한국어를 사용하시고, 존댓말로 답변해주세요."""


USER_PROMPT = """사용자의 요청사항: 
{user_query}

자료: 
{context}
"""

async def run_chain(user_query: str, context: str, model_name: str = "gpt-4.1-2025-04-14") -> str:
    llm = ChatOpenAI(api_key=settings.openai_api_key, model=model_name, temperature=0.1)
    ctx = context
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=USER_PROMPT.format(user_query=user_query, context=ctx)),
    ]
    resp = await llm.ainvoke(messages)
    return resp.content
