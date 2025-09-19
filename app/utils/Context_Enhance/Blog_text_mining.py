import os
import asyncio
from typing import Dict, List, Optional
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from app.config import settings


class BlogRefiner:
    def __init__(self, model_name: str = "gpt-4o", temperature: float = 0.01):
        self.llm = ChatOpenAI(
            model_name=model_name,
            temperature=temperature,
            openai_api_key=settings.openai_api_key
        )
        
    async def refine_blog_content(
        self, 
        blog_text: str, 
        place_name: str, 
        query: str,
        max_length: int = 1024
    ) -> str:
            
        # 시스템 프롬프트
        system_prompt = f"""당신은 여행 블로그 내용을 정제하는 전문가입니다.
다음 원칙에 따라 블로그 내용을 정제해주세요:

1. **핵심 정보 추출**: 장소명 "{place_name}"과 관련된 핵심 정보만 추출
2. **불필요한 내용 제거**: 개인적인 일상, 광고, 중복된 내용 제거
3. **한국어**: 한국어로 자연스럽게 작성

장소명: "{place_name}"
"""

        # 사용자 메시지
        user_prompt = f"""다음 블로그 내용을 정제해주세요:

{blog_text}

위 내용에서 "{place_name}"과 관련된 정보만 추출하여 정제된 글로 제공해주세요."""

        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]
            
            response = await self.llm.ainvoke(messages)
            refined_content = response.content.strip()
                
            return refined_content
            
        except Exception as e:
            print(f"블로그 정제 실패: {e}")
            # 실패 시 원본 텍스트의 앞부분만 반환
            return blog_text[:max_length] + "..." if len(blog_text) > max_length else blog_text

    async def refine_multiple_blogs(
        self, 
        blog_contents: List[Dict[str, str]], 
        place_name: str, 
        query: str,
        max_length_per_blog: int = 800
    ) -> List[Dict[str, str]]:

        if not blog_contents:
            return []
            
        # 병렬 처리로 정제
        tasks = []
        for blog in blog_contents:
            task = self.refine_blog_content(
                blog.get("text", ""),
                place_name,
                query,
                max_length_per_blog
            )
            tasks.append(task)
            
        try:
            refined_texts = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 결과 정리
            refined_blogs = []
            for i, (blog, refined_text) in enumerate(zip(blog_contents, refined_texts)):
                if isinstance(refined_text, Exception):
                    print(f"블로그 {i+1} 정제 실패: {refined_text}")
                    refined_text = blog.get("text", "")[:max_length_per_blog]
                    
                refined_blog = blog.copy()
                refined_blog["text"] = refined_text
                refined_blog["refined"] = True
                refined_blogs.append(refined_blog)
                
            return refined_blogs
            
        except Exception as e:
            print(f"블로그 정제 중 오류 발생: {e}")
            # 실패 시 원본 반환
            for blog in blog_contents:
                blog["refined"] = False
            return blog_contents


# 전역 인스턴스
_blog_refiner: Optional[BlogRefiner] = None


def get_blog_refiner() -> BlogRefiner:
    """BlogRefiner 싱글톤 인스턴스 반환"""
    global _blog_refiner
    if _blog_refiner is None:
        _blog_refiner = BlogRefiner()
    return _blog_refiner


async def refine_blog_content_async(
    blog_text: str, 
    place_name: str, 
    query: str,
    max_length: int = 1000
) -> str:
    """블로그 내용 정제 (편의 함수)"""
    refiner = get_blog_refiner()
    return await refiner.refine_blog_content(blog_text, place_name, query, max_length)


async def refine_multiple_blogs_async(
    blog_contents: List[Dict[str, str]], 
    place_name: str, 
    query: str,
    max_length_per_blog: int = 800
) -> List[Dict[str, str]]:
    """여러 블로그 내용 정제 (편의 함수)"""
    refiner = get_blog_refiner()
    return await refiner.refine_multiple_blogs(blog_contents, place_name, query, max_length_per_blog)
