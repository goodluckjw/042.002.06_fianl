import requests
import xml.etree.ElementTree as ET
from urllib.parse import quote
import re
import os

OC = os.getenv("OC", "chetera")
BASE = "http://www.law.go.kr"

def get_law_list_from_api(query):
    exact_query = f'"{query}"'
    encoded_query = quote(exact_query)
    page = 1
    laws = []
    while True:
        url = f"{BASE}/DRF/lawSearch.do?OC={OC}&target=law&type=XML&display=100&page={page}&search=2&knd=A0002&query={encoded_query}"
        res = requests.get(url, timeout=10)
        res.encoding = 'utf-8'
        if res.status_code != 200:
            break
        root = ET.fromstring(res.content)
        for law in root.findall("law"):
            laws.append({
                "법령명": law.findtext("법령명한글", "").strip(),
                "MST": law.findtext("법령일련번호", ""),
                "URL": BASE + (law.findtext("법령상세링크", "") or "")
            })
        if len(root.findall("law")) < 100:
            break
        page += 1
    return laws

def get_law_text_by_mst(mst):
    url = f"{BASE}/DRF/lawService.do?OC={OC}&target=law&MST={mst}&type=XML"
    try:
        res = requests.get(url, timeout=10)
        res.encoding = 'utf-8'
        return res.content if res.status_code == 200 else None
    except:
        return None

def clean(text):
    return re.sub(r"\s+", "", text or "")

def highlight(text, keyword):
    if not text:
        return ""
    return text.replace(keyword, f"<span style='color:red'>{keyword}</span>")

def get_highlighted_articles(mst, keyword):
    xml_data = get_law_text_by_mst(mst)
    if not xml_data:
        return "⚠️ 본문을 불러올 수 없습니다."

    tree = ET.fromstring(xml_data)
    articles = tree.findall(".//조문단위")
    keyword_clean = clean(keyword)
    results = []

    for article in articles:
        조번호 = article.findtext("조번호", "").strip()
        조제목 = article.findtext("조문제목", "") or ""
        조내용 = article.findtext("조문내용", "") or ""
        항들 = article.findall("항")

        조출력 = False
        항출력 = []

        for i, 항 in enumerate(항들):
            항내용 = 항.findtext("항내용", "") or ""
            호출력 = []

            for 호 in 항.findall("호"):
                호내용 = 호.findtext("호내용", "") or ""
                if keyword_clean in clean(호내용):
                    호출력.append("&nbsp;&nbsp;" + highlight(호내용, keyword))
            for 목 in 항.findall("목"):
                줄단위 = []
                for m in 목.findall("목내용"):
                    if m.text and keyword_clean in clean(m.text):
                        줄단위.extend([
                            "&nbsp;&nbsp;&nbsp;&nbsp;" + highlight(line.strip(), keyword)
                            for line in m.text.splitlines() if line.strip()
                        ])
                if 줄단위:
                    호출력.extend(줄단위)

            if keyword_clean in clean(항내용):
                항출력.append(highlight(항내용, keyword))
                if 호출력:
                    항출력.extend(호출력)
            elif 호출력:
                항출력.append(highlight(항내용, keyword) + "<br>" + "<br>".join(호출력))

        if keyword_clean in clean(조제목) or keyword_clean in clean(조내용) or 항출력:
            output = f"{highlight(조내용, keyword)}"
            if 항출력:
                output += " " + 항출력[0]
                if len(항출력) > 1:
                    output += "<br>" + "<br>".join([f"&nbsp;&nbsp;{a}" for a in 항출력[1:]])
            results.append(output)

    return "<br><br>".join(results) if results else "🔍 해당 검색어를 포함한 조문이 없습니다."

def run_search_logic(query, unit):
    result = {}
    for law in get_law_list_from_api(query):
        mst = law["MST"]
        html = get_highlighted_articles(mst, query)
        if html and "해당 검색어를 포함한 조문이 없습니다" not in html:
            result[law["법령명"]] = html.split("<br><br>")
    return result

def run_amendment_logic(find_word, replace_word):
    조사 = "을" if (ord(find_word[-1]) - 44032) % 28 else "를"
    amendments = []
    for law in get_law_list_from_api(find_word):
        mst = law["MST"]
        xml = get_law_text_by_mst(mst)
        if not xml:
            continue
        tree = ET.fromstring(xml)
        articles = tree.findall(".//조문단위")
        조문들 = []
        for article in articles:
            조번호 = article.findtext("조번호", "").strip()
            조제목 = article.findtext("조문제목", "") or ""
            조내용 = article.findtext("조문내용", "") or ""
            if find_word in 조제목:
                조문들.append(f"제{조번호}조의 제목")
            if find_word in 조내용:
                조문들.append(f"제{조번호}조")
            for 항 in article.findall("항"):
                항번호 = 항.findtext("항번호", "") or ""
                항내용 = 항.findtext("항내용", "") or ""
                if find_word in 항내용:
                    조문들.append(f"제{조번호}조제{항번호}항")
        if 조문들:
            조문_str = " 및 ".join(sorted(set(조문들)))
            amendments.append(f"① {law['법령명']} 일부를 다음과 같이 개정한다. {조문_str} 중 “{find_word}”{조사} 각각 “{replace_word}”로 한다.")
    return amendments or ["⚠️ 개정 대상 조문이 없습니다."]

