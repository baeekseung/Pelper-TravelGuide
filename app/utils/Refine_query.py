from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

async def refine_query(location_text: str, query: str) -> str:

    llm = ChatOpenAI(model_name="gpt-4o", temperature=0.0001, max_tokens=64)

    prompt = f"""당신은 검색 쿼리를 작성하는 역할을 수행해야합니다.
    사용자의 위치와 사용자의 쿼리를 기반으로 검색쿼리를 작성해주세요.

    예를 들어서,
    사용자의 위치: 청도군 화양읍
    사용자의 쿼리: 소금빵이 맛있는 카페를 추천해줘,
    검색 쿼리: 청도군 화양읍 소금빵 맛집 카페

    사용자의 위치: 서울시 강남구
    사용자의 쿼리: 값싼 숙소를 추천해줘.
    검색 쿼리: 서울시 강남구 가성비 숙소

    사용자의 위치: 서울시 종로구
    사용자의 쿼리: 종로구에 있는 맛집을 추천해줘.
    검색 쿼리: 서울시 종로구 맛집

    사용자의 위치: 부산시 해운대구
    사용자의 쿼리: 바다가 보이는 맛집을 추천해줘.
    검색 쿼리: 부산시 해운대구 오션뷰 맛집

    사용자의 위치: 경산시 중앙동
    사용자의 쿼리: 여기에서 청도로 가는 방법을 알려줘.
    검색 쿼리: 경산시 중앙동에서 청도로 가는 방법

    사용자의 위치: 제주시 서귀포시
    사용자의 쿼리: 가장 가까운 야시장을 찾아줘
    검색 쿼리: 제주시 서귀포시 야시장

    사용자의 위치: {location_text}
    사용자의 쿼리: {query}
    검색 쿼리: 
    """

    prompt = PromptTemplate(
        template=prompt,
        input_variables=["query", "location_text"]
    )
    
    chain = prompt | llm | StrOutputParser()

    return chain.invoke({"query": query, "location_text": location_text})
