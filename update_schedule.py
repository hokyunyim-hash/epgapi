import os
import sys
from datetime import datetime
from google import genai
from google.genai import types

def generate_radio_xml():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("에러: GEMINI_API_KEY 환경변수가 설정되지 않았습니다.")
        sys.exit(1)

    client = genai.Client(api_key=api_key)
    today_str = datetime.today().strftime('%Y-%m-%d')

    prompt = f"""
    당신은 대한민국 라디오 방송국 편성표를 수집하여 제공하는 데이터 엔지니어 로봇입니다.

    1. 오늘 날짜({today_str}) 기준으로 아래 11개 라디오 채널의 24시간 주중 평일 전체 편성표 데이터를 웹 검색(Google Search Grounding) 기능을 활용하여 수집하세요.
       - KBS: 제1라디오, 제2라디오(해피FM), 클래식FM, Cool FM, 제3라디오
       - SBS: 러브FM, 파워FM
       - MBC: 표준FM, FM4U
       - CBS: 표준FM, 음악FM

    2. 수집한 모든 타임라인 데이터를 유효한 XML 구조로 완벽하게 포맷팅하여 텍스트로만 반환하세요.
    3. 마크다운 기호(예: ```xml)나 앞뒤 설명 멘트를 절대 포함하지 마십시오. 오직 '<?xml'로 시작해서 '</radioSchedules>'로 끝나는 내용만 출력해야 합니다.
    4. XML 구조는 <radioSchedules date="{today_str}">을 루트로 하고, 내부에 <broadcaster name="..."> -> <channel name="..." frequency="..."> -> <program> 구조로 정리하세요. 각 프로그램은 <startTime>, <title> 요소를 반드시 가져야 합니다.
    """

    print("Gemini API 호출 및 실시간 웹 검색 기반 XML 생성 시작...")

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[{"google_search": {}}],
                temperature=0.1,
            )
        )

        xml_content = response.text.strip()

        if xml_content.startswith("```xml"):
            xml_content = xml_content.split("```xml")[1].split("```")[0].strip()
        elif xml_content.startswith("```"):
            xml_content = xml_content.split("```")[1].split("```")[0].strip()

        os.makedirs("public", exist_ok=True)
        xml_path = os.path.join("public", "radio.xml")

        with open(xml_path, "w", encoding="utf-8") as f:
            f.write(xml_content)

        print(f"성공: XML 파일이 {xml_path} 에 저장되었습니다.")

    except Exception as e:
        print(f"오류 발생: {e}")
        sys.exit(1)

if __name__ == "__main__":
    generate_radio_xml()
