import os
import sys
import shutil
import re
from datetime import datetime
from xml.etree import ElementTree as ET
from google import genai
from google.genai import types

CHANNELS = [
    # 라디오
    {"broadcaster": "KBS", "name": "KBS 제1라디오", "id": "kbs.1radio", "frequency": "711kHz"},
    {"broadcaster": "KBS", "name": "KBS 제2라디오 해피FM", "id": "kbs.2radio", "frequency": "106.1MHz"},
    {"broadcaster": "KBS", "name": "KBS 클래식FM", "id": "kbs.classicfm", "frequency": "93.1MHz"},
    {"broadcaster": "KBS", "name": "KBS Cool FM", "id": "kbs.coolfm", "frequency": "89.1MHz"},
    {"broadcaster": "KBS", "name": "KBS 제3라디오", "id": "kbs.3radio", "frequency": "104.9MHz"},
    {"broadcaster": "SBS", "name": "SBS 러브FM", "id": "sbs.lovefm", "frequency": "103.5MHz"},
    {"broadcaster": "SBS", "name": "SBS 파워FM", "id": "sbs.powerfm", "frequency": "107.7MHz"},
    {"broadcaster": "MBC", "name": "MBC 표준FM", "id": "mbc.standardfm", "frequency": "95.9MHz"},
    {"broadcaster": "MBC", "name": "MBC FM4U", "id": "mbc.fm4u", "frequency": "91.9MHz"},
    {"broadcaster": "CBS", "name": "CBS 표준FM", "id": "cbs.standardfm", "frequency": "98.1MHz"},
    {"broadcaster": "CBS", "name": "CBS 음악FM", "id": "cbs.musicfm", "frequency": "93.9MHz"},
    {"broadcaster": "CBS", "name": "CBS JOY4U", "id": "cbs.joy4u", "frequency": ""},
    # TV
    {"broadcaster": "KBS", "name": "KBS 1TV", "id": "kbs.1tv", "frequency": ""},
    {"broadcaster": "KBS", "name": "KBS 2TV", "id": "kbs.2tv", "frequency": ""},
    {"broadcaster": "MBC", "name": "MBC TV", "id": "mbc.tv", "frequency": ""},
    {"broadcaster": "SBS", "name": "SBS TV", "id": "sbs.tv", "frequency": ""},
    {"broadcaster": "EBS", "name": "EBS 1TV", "id": "ebs.1tv", "frequency": ""},
    {"broadcaster": "tvN", "name": "tvN", "id": "tvn", "frequency": ""},
    {"broadcaster": "JTBC", "name": "JTBC", "id": "jtbc", "frequency": ""},
    {"broadcaster": "TV조선", "name": "TV조선", "id": "tvchosun", "frequency": ""},
    {"broadcaster": "채널A", "name": "채널A", "id": "channela", "frequency": ""},
    {"broadcaster": "MBN", "name": "MBN", "id": "mbn", "frequency": ""},
]


def fix_xml_entities(xml_content):
    """태그 밖의 & 를 &amp; 로 치환하고 DOCTYPE을 제거해 파싱 안전하게 만듦"""
    # DOCTYPE 제거 (외부 DTD 참조 파싱 오류 방지)
    xml_content = re.sub(r'<!DOCTYPE[^>]*>', '', xml_content)

    # 태그 속성값과 텍스트 노드에서 이스케이프되지 않은 & 수정
    # 태그 바깥 텍스트의 & → &amp; (이미 &amp; &lt; &gt; &quot; &apos; 인 것은 제외)
    def replace_bare_ampersand(m):
        s = m.group(0)
        # 이미 올바른 엔티티면 그대로
        if re.match(r'&(amp|lt|gt|quot|apos|#\d+|#x[0-9a-fA-F]+);', s):
            return s
        return '&amp;'

    xml_content = re.sub(r'&(?:[^;]{0,10})?', replace_bare_ampersand, xml_content)
    return xml_content


def validate_xml(xml_content):
    """XML 파싱 유효성 검사"""
    try:
        ET.fromstring(xml_content.encode('utf-8'))
        return True
    except ET.ParseError as e:
        print(f"XML 유효성 오류: {e}")
        return False


def generate_radio_xml():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("에러: GEMINI_API_KEY 환경변수가 설정되지 않았습니다.")
        sys.exit(1)

    client = genai.Client(api_key=api_key)
    today_str = datetime.today().strftime('%Y-%m-%d')
    os.makedirs("public", exist_ok=True)

    channel_list = "\n".join(
        f"       - {ch['broadcaster']}: {ch['name']}" + (f" ({ch['frequency']})" if ch['frequency'] else "")
        for ch in CHANNELS
    )

    prompt = f"""
    당신은 대한민국 방송 편성표를 XMLTV 표준 형식으로 변환하는 데이터 엔지니어 로봇입니다.

    1. 오늘 날짜({today_str}) 기준으로 아래 채널들의 24시간 전체 편성표를 웹 검색으로 수집하세요:
{channel_list}

    2. XMLTV 표준 포맷으로 출력하세요. 반드시 '<?xml'로 시작하고 '</tv>'로 끝나야 합니다.
    3. 마크다운 기호(```xml 등)나 설명 텍스트를 절대 포함하지 마세요.
    4. XML 텍스트 내에 특수문자(&, <, >, ", ')가 있으면 반드시 XML 엔티티(&amp; &lt; &gt; &quot; &apos;)로 이스케이프하세요.
    5. 각 채널의 id는 아래 매핑을 사용하세요:
{chr(10).join(f"       {ch['name']} -> {ch['id']}" for ch in CHANNELS)}

    6. XMLTV 포맷 예시:
    <?xml version="1.0" encoding="UTF-8"?>
    <tv date="{today_str.replace('-','')}">
      <channel id="kbs.1radio">
        <display-name lang="ko">KBS 제1라디오</display-name>
      </channel>
      <programme start="20260620060000 +0900" stop="20260620070000 +0900" channel="kbs.1radio">
        <title lang="ko">프로그램명</title>
        <desc lang="ko">프로그램 설명</desc>
      </programme>
    </tv>

    7. start/stop 시간 형식: YYYYMMDDHHmmss +0900 (KST)
    8. stop 시간은 다음 프로그램 start 시간과 동일하게 설정하세요.
    9. 모든 채널을 포함하세요.
    """

    print(f"Gemini API 호출 중... ({len(CHANNELS)}개 채널)")

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

        if not xml_content.startswith("<?xml"):
            raise ValueError("유효하지 않은 XML 응답")

        # 특수문자 정제
        xml_content = fix_xml_entities(xml_content)

        # 유효성 검증
        if not validate_xml(xml_content):
            raise ValueError("XML 파싱 실패 - 유효하지 않은 XML")

        history_dir = os.path.join("public", "history")
        os.makedirs(history_dir, exist_ok=True)
        history_path = os.path.join(history_dir, f"radio-{today_str}.xml")

        xml_path = os.path.join("public", "radio.xml")

        if os.path.exists(xml_path):
            shutil.copy2(xml_path, os.path.join("public", "radio.backup.xml"))

        with open(xml_path, "w", encoding="utf-8") as f:
            f.write(xml_content)

        with open(history_path, "w", encoding="utf-8") as f:
            f.write(xml_content)

        channels_dir = os.path.join("public", "channels")
        os.makedirs(channels_dir, exist_ok=True)
        generate_channel_files(xml_content, channels_dir, today_str)

        generate_index(today_str)

        print(f"성공: {xml_path} 저장 완료")
        print(f"히스토리: {history_path} 저장 완료")

    except Exception as e:
        print(f"오류 발생: {e}")
        backup = os.path.join("public", "radio.backup.xml")
        if os.path.exists(backup):
            shutil.copy2(backup, os.path.join("public", "radio.xml"))
            print("이전 데이터로 복구했습니다.")
        sys.exit(1)


def generate_channel_files(xml_content, channels_dir, today_str):
    try:
        for ch in CHANNELS:
            cid = ch['id']
            channel_def = re.findall(
                rf'<channel id="{re.escape(cid)}".*?</channel>', xml_content, re.DOTALL
            )
            programmes = re.findall(
                rf'<programme[^>]+channel="{re.escape(cid)}".*?</programme>', xml_content, re.DOTALL
            )
            if not programmes:
                continue

            content = f'<?xml version="1.0" encoding="UTF-8"?>\n<tv date="{today_str.replace("-","")}">\n'
            if channel_def:
                content += f"  {channel_def[0]}\n"
            for p in programmes:
                content += f"  {p}\n"
            content += "</tv>"

            with open(os.path.join(channels_dir, f"{cid}.xml"), "w", encoding="utf-8") as f:
                f.write(content)
        print("채널별 XML 생성 완료")
    except Exception as e:
        print(f"채널별 파일 생성 중 오류 (무시): {e}")


def generate_index(today_str):
    channel_links = "\n".join(
        f'    <li><a href="channels/{ch["id"]}.xml">{ch["name"]}</a></li>'
        for ch in CHANNELS
    )
    html = f"""<!DOCTYPE html>
<html lang="ko">
<head><meta charset="UTF-8"><title>한국 방송 편성표 EPG</title></head>
<body>
  <h1>한국 방송 편성표 EPG</h1>
  <p>기준일: {today_str} | <a href="radio.xml">전체 XMLTV 다운로드</a></p>
  <h2>채널별</h2>
  <ul>
{channel_links}
  </ul>
  <h2>히스토리</h2>
  <p><a href="history/">날짜별 보관함</a></p>
</body>
</html>"""
    with open(os.path.join("public", "index.html"), "w", encoding="utf-8") as f:
        f.write(html)


if __name__ == "__main__":
    generate_radio_xml()
