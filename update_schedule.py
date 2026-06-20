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

BATCH_SIZE = 6  # 한 번에 요청할 채널 수


def fix_xml_entities(xml_content):
    xml_content = re.sub(r'<!DOCTYPE[^>]*>', '', xml_content)

    def replace_bare_ampersand(m):
        s = m.group(0)
        if re.match(r'&(amp|lt|gt|quot|apos|#\d+|#x[0-9a-fA-F]+);', s):
            return s
        return '&amp;'

    xml_content = re.sub(r'&(?:[^;]{0,10})?', replace_bare_ampersand, xml_content)
    return xml_content


def validate_xml(xml_content):
    try:
        ET.fromstring(xml_content.encode('utf-8'))
        return True
    except ET.ParseError as e:
        print(f"XML 유효성 오류: {e}")
        return False


def fetch_batch(client, channels_batch, today_str):
    """채널 배치에 대한 XMLTV 데이터를 Gemini로 가져옴"""
    channel_list = "\n".join(
        f"   - {ch['broadcaster']}: {ch['name']}" + (f" ({ch['frequency']})" if ch['frequency'] else "")
        for ch in channels_batch
    )
    id_mapping = "\n".join(f"   {ch['name']} -> {ch['id']}" for ch in channels_batch)
    date_nodash = today_str.replace('-', '')

    prompt = f"""
    대한민국 방송 편성표를 XMLTV 형식으로 변환하는 로봇입니다.

    오늘 날짜({today_str}) 기준으로 아래 채널들의 24시간 편성표를 웹 검색으로 수집하세요:
{channel_list}

    규칙:
    - '<?xml'로 시작하고 '</tv>'로 끝나는 XML만 출력 (마크다운 금지)
    - XML 내 특수문자(&)는 &amp; 로 이스케이프
    - 채널 id 매핑:
{id_mapping}

    포맷:
    <?xml version="1.0" encoding="UTF-8"?>
    <tv date="{date_nodash}">
      <channel id="CHANNEL_ID"><display-name lang="ko">채널명</display-name></channel>
      <programme start="{date_nodash}060000 +0900" stop="{date_nodash}070000 +0900" channel="CHANNEL_ID">
        <title lang="ko">프로그램명</title>
      </programme>
    </tv>

    start/stop: YYYYMMDDHHmmss +0900, stop은 다음 프로그램 start와 동일.
    """

    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
        config=types.GenerateContentConfig(
            tools=[{"google_search": {}}],
            temperature=0.1,
        )
    )

    xml = response.text.strip()
    if xml.startswith("```xml"):
        xml = xml.split("```xml")[1].split("```")[0].strip()
    elif xml.startswith("```"):
        xml = xml.split("```")[1].split("```")[0].strip()

    return xml


def extract_inner(xml_content):
    """<tv> 태그 안의 내용만 추출"""
    match = re.search(r'<tv[^>]*>(.*)</tv>', xml_content, re.DOTALL)
    return match.group(1).strip() if match else ""


def generate_radio_xml():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("에러: GEMINI_API_KEY 환경변수가 설정되지 않았습니다.")
        sys.exit(1)

    client = genai.Client(api_key=api_key)
    today_str = datetime.today().strftime('%Y-%m-%d')
    date_nodash = today_str.replace('-', '')
    os.makedirs("public", exist_ok=True)

    # 배치 분할
    batches = [CHANNELS[i:i+BATCH_SIZE] for i in range(0, len(CHANNELS), BATCH_SIZE)]
    print(f"총 {len(CHANNELS)}개 채널을 {len(batches)}개 배치로 분할 처리")

    all_inner = []
    for i, batch in enumerate(batches):
        names = ", ".join(ch['name'] for ch in batch)
        print(f"배치 {i+1}/{len(batches)}: {names}")
        try:
            xml = fetch_batch(client, batch, today_str)
            xml = fix_xml_entities(xml)
            inner = extract_inner(xml)
            if inner:
                all_inner.append(inner)
            else:
                print(f"  경고: 배치 {i+1} 결과 없음, 건너뜀")
        except Exception as e:
            print(f"  배치 {i+1} 오류 (건너뜀): {e}")

    if not all_inner:
        print("오류: 모든 배치 실패")
        _restore_backup()
        sys.exit(1)

    # 전체 XML 합치기
    xml_content = f'<?xml version="1.0" encoding="UTF-8"?>\n<tv date="{date_nodash}">\n'
    xml_content += "\n".join(all_inner)
    xml_content += "\n</tv>"

    if not validate_xml(xml_content):
        print("오류: 합친 XML 유효성 검증 실패")
        _restore_backup()
        sys.exit(1)

    _save(xml_content, today_str)


def _restore_backup():
    backup = os.path.join("public", "radio.backup.xml")
    if os.path.exists(backup):
        shutil.copy2(backup, os.path.join("public", "radio.xml"))
        print("이전 데이터로 복구했습니다.")


def _save(xml_content, today_str):
    xml_path = os.path.join("public", "radio.xml")
    history_dir = os.path.join("public", "history")
    os.makedirs(history_dir, exist_ok=True)

    if os.path.exists(xml_path):
        shutil.copy2(xml_path, os.path.join("public", "radio.backup.xml"))

    with open(xml_path, "w", encoding="utf-8") as f:
        f.write(xml_content)

    with open(os.path.join(history_dir, f"radio-{today_str}.xml"), "w", encoding="utf-8") as f:
        f.write(xml_content)

    channels_dir = os.path.join("public", "channels")
    os.makedirs(channels_dir, exist_ok=True)
    generate_channel_files(xml_content, channels_dir, today_str)
    generate_index(today_str)

    print(f"성공: {xml_path} 저장 완료")


def generate_channel_files(xml_content, channels_dir, today_str):
    try:
        for ch in CHANNELS:
            cid = ch['id']
            channel_def = re.findall(rf'<channel id="{re.escape(cid)}".*?</channel>', xml_content, re.DOTALL)
            programmes = re.findall(rf'<programme[^>]+channel="{re.escape(cid)}".*?</programme>', xml_content, re.DOTALL)
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
