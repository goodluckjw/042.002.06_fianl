
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
                "MST": law.findtext("법령일련번호", "")
            })
        total_count = int(root.findtext("totalCnt", "0"))
        if len(laws) >= total_count:
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
    return text.replace(keyword, f"<span style='color:red'>{keyword}</span>") if text else ""

def run_search_logic(query, unit):
    result_dict = {}
    keyword_clean = clean(query)

    for law in get_law_list_from_api(query):
        mst = law["MST"]
        xml_data = get_law_text_by_mst(mst)
        if not xml_data:
            continue

        tree = ET.fromstring(xml_data)
        articles = tree.findall(".//조문단위")
        law_results = []

        for article in articles:
            조내용 = article.findtext("조문내용") or ""
            항들 = article.findall("항")
            출력덩어리 = []
            첫_항출력됨 = False
            첫_항내용_텍스트 = ""

            조출력 = keyword_clean in clean(조내용)
            if 조출력:
                출력덩어리.append(highlight(조내용, query))

            for 항 in 항들:
                항내용 = 항.findtext("항내용") or ""
                항출력 = keyword_clean in clean(항내용)
                항덩어리 = []
                호출력된 = False

                for 호 in 항.findall("호"):
                    호내용 = 호.findtext("호내용") or ""
                    if keyword_clean in clean(호내용):
                        if not 항출력:
                            항덩어리.append(highlight(항내용, query))
                            항출력 = True
                        항덩어리.append("&nbsp;&nbsp;" + highlight(호내용, query))
                        호출력된 = True

                    for 목 in 호.findall("목"):
                        목내용_list = 목.findall("목내용")
                        if 목내용_list:
                            combined_lines = []
                            for m in 목내용_list:
                                if m.text and keyword_clean in clean(m.text):
                                    combined_lines.extend([
                                        highlight(line.strip(), query)
                                        for line in m.text.splitlines() if line.strip()
                                    ])
                            if combined_lines:
                                if not 항출력:
                                    항덩어리.append(highlight(항내용, query))
                                    항출력 = True
                                if not 호출력된:
                                    항덩어리.append("&nbsp;&nbsp;" + highlight(호내용, query))
                                항덩어리.extend(["&nbsp;&nbsp;&nbsp;&nbsp;" + l for l in combined_lines])

                if 항출력 or 항덩어리:
                    if not 조출력 and not 첫_항출력됨:
                        if 항덩어리:
                            출력덩어리.append(highlight(조내용, query) + " " + 항덩어리[0])
                            출력덩어리.extend(항덩어리[1:])
                        else:
                            출력덩어리.append(highlight(조내용, query) + " " + highlight(항내용, query))
                        첫_항내용_텍스트 = 항내용.strip()
                        첫_항출력됨 = True
                        조출력 = True
                    elif 항내용.strip() != 첫_항내용_텍스트:
                        if 항출력:
                            출력덩어리.append(highlight(항내용, query))
                        출력덩어리.extend(항덩어리)

            if 출력덩어리:
                law_results.append("<br>".join(출력덩어리))

        if law_results:
            result_dict[law["법령명"]] = law_results

    return result_dict
