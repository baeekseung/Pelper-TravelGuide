import pandas as pd
import openpyxl
import os
import sys
import time
from selenium import webdriver
from bs4 import BeautifulSoup
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from pyparsing import col
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import NoSuchElementException
from tqdm import tqdm 
import re

# 식당 데이터 임포트
name_data = pd.read_csv('마포구.csv', encoding='utf-8-sig')
print(name_data)

#지역명이 포함된 식당명을 변수로 지정
items = name_data['name']
print(items)

#검색할 식당 데이터와 url을 담을 데이터 프레임 생성
df = pd.DataFrame(columns=['name', 'naverURL'])

#데이터 프레임이 잘 만들어졌는지 확인
df['name'] = items
df

# 식당 url 얻기
options = webdriver.ChromeOptions()
options.add_experimental_option("excludeSwitches", ["enable-logging"])
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

res = driver.page_source  # 페이지 소스 가져오기
soup = BeautifulSoup(res, 'html.parser')  # html 파싱하여  가져온다

# frame 변경 메소드
def switch_frame(frame):
    driver.switch_to.default_content()  # frame 초기화
    driver.switch_to.frame(frame)  # frame 변경
    res
    soup

for i, keyword in enumerate(df['name'].tolist()):
    # 검색 url 만들기
    naver_map_search_url = f'https://map.naver.com/v5/search/{keyword}/place'  
    # 검색 url 접속 = 검색하기
    driver.get(naver_map_search_url)
    time.sleep(2) 
    # 검색 프레임 변경
    driver.switch_to.frame("searchIframe")
    time.sleep(1) 
     
    
    try:     
        #식당 정보가 있다면 첫번째 식당의 url을 가져오기
        
        if len(driver.find_elements(By.XPATH, '//*[@id="_pcmap_list_scroll_container"]/ul/li')) != 0:   
            #식당 정보 클릭        
            driver.execute_script('return document.querySelector("#_pcmap_list_scroll_container > ul > li:nth-child(1) > div.ouxiq > a:nth-child(1) > div").click()')
            time.sleep(2)
            
            # 검색한 플레이스의 개별 페이지 저장
            tmp = driver.current_url  
            res_code = re.findall(r"place/(\d+)", tmp)
            final_url = 'https://pcmap.place.naver.com/restaurant/'+res_code[0]+'/review/visitor#' 
        
            print(final_url)
            df['naverURL'][i]=final_url 
        
    except: 
        df['naverURL'][i]= ''
        print('none') 
    
driver.close()

#식당명과 url이 잘 얻어져왔는지 확인하기
print(df)

#url을 얻어오지 못한 식당 확인
print(df.loc[df['naverURL']==''])
#결측치로 입력된 식당 확인
print(df.loc[df['naverURL'].isna()])
## 식당 리뷰 url이 들어가있지 않은 경우 직접 검색하여 데이터에 넣어주기!!! ##

# csv 파일로도 저장하여 url이 빈 값이 있는지 반드시 확인할 것 !
#url이 없으면 코드 실행이 중단되므로 반드시 url 데이터를 확인할 것!!
df.to_csv('마포구url.csv', encoding='utf-8-sig')

options = webdriver.ChromeOptions()
options.add_experimental_option("excludeSwitches", ["enable-logging"])
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
driver.maximize_window()


count = 0 #
current = 0 #현재 진행 상황

goal = len(df['name']) #총 식당 수

#데이터 프레임으로 만들 빈 리스트 생성
rev_list=[]


for i in range(len(df)): 
    
    current += 1
    print('진행상황 : ', current,'/',goal,sep="")
    
    
    # 식당 리뷰 개별 url 접속
    driver.get(df['naverURL'][i]) 
    thisurl = df['naverURL'][i]
    time.sleep(2)
    print('현재 수집중인 식당 : ', df['name'][i])
    
    #리뷰 더보기 버튼 누르기
    while True: 
        try:
            driver.find_element(By.CSS_SELECTOR, '#app-root > div > div > div > div:nth-child(7) > div:nth-child(2) > div.place_section.lcndr > div.lfH3O > a')
            driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.END)
            time.sleep(1)
            driver.execute_script('return document.querySelector("#app-root > div > div > div > div:nth-child(7) > div:nth-child(2) > div.place_section.lcndr > div.lfH3O > a").click()')
            time.sleep(2) 
                        
        except NoSuchElementException:
            print("-모든 리뷰 더보기 완료-")
            break    
        
    #식당 평균 별점 수집
    try:
        rating = driver.find_element(By.CSS_SELECTOR, '#app-root > div > div > div > div:nth-child(7) > div:nth-child(2) > div.place_section.no_margin.mdJ86 > div.place_section_content > div > div.Xj_yJ > span.m7jAR.ohonc > em').text
        print('식당 평균 별점 : ', rating)
        rev_list.append(
            [df['name'][i],
             rating
             ]
        )
    except:
        pass
    
    

     
        
    #리뷰 데이터 스크래핑을 위한 html 파싱
    html = driver.page_source
    soup = BeautifulSoup(html, 'html.parser')
    
    try:
        #키워드 리뷰가 아닌 리뷰글 리스트 검색
        review_lists = soup.select('#app-root > div > div > div > div:nth-child(7) > div:nth-child(2) > div.place_section.lcndr > div.place_section_content > ul > li')
        
        print('총 리뷰 수 : ', len(review_lists))
        
        #리뷰 수가 0이 아닌 경우 리뷰 수집
        if len(review_lists) > 0 :
            
            for j, review in enumerate(review_lists):
                
                try:
                    
                    #내용 더보기가 있는 경우 내용 더보기를 눌러주기
                    try:
                        review.find(' div.ZZ4OK > a > span.rvCSr > svg')
                        more_content = review.select(' div.ZZ4OK > a > span.rvCSr > svg')
                        more_content.click()
                        time.sleep(1)
   
                        #리뷰 정보
                        user_review = review.select(' div.ZZ4OK > a > span')
                           
                
                        #리뷰 정보가 있는 경우 식당 이름, 평점, 리뷰 텍스트, 작성 시간을 가져와서 데이터 프레임으로 만들기
                        if len(user_review) > 0:
                             rev_list.append(
                                [
                                    df['name'][i],
                                    '',
                                    user_review[0].text
                                ]
                                )      
                       
                        time.sleep(1)            
                
                    
                    
                    except:
                        #리뷰 정보
                        user_review = review.select(' div.ZZ4OK.IwhtZ > a > span')
                        
        
                        #리뷰 정보가 있는 경우 식당 이름, 평점, 리뷰 텍스트, 작성 시간을 가져와서 데이터 프레임으로 만들기
                        if len(user_review) > 0:
                            rev_list.append(
                                [
                                    df['name'][i],
                                    '',
                                    user_review[0].text
                                ]
                                )      
                        
                        time.sleep(1) 
                        
                except NoSuchElementException:
                    print('리뷰 텍스트가 인식되지 않음')
                    continue  
                
        else:
            print('리뷰 선택자가 인식되지 않음')
            time.sleep(1)                
        
       
        


    # 리뷰가 없는 경우        
    except NoSuchElementException: 
               
        rev_list.append(
        [
            df['name'][i],
            rating,
        ]
        ) 
        time.sleep(2)           
        print("리뷰가 존재하지 않음")

    
            
    #검색한 창 닫고 검색 페이지로 돌아가기    
    # driver.close()
    # driver.switch_to.window(tabs[0])
    print("기본 페이지로 돌아가기")

        
driver.close()

#스크래핑한 데이터를 데이터 프레임으로 만들기  
column = ["name", 'rate', "review"]
df2 = pd.DataFrame(rev_list, columns=column)
df2   