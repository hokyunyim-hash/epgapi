# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

두 개의 독립적인 EPG(전자 편성표) 시스템으로 구성됩니다:

1. **Node.js Express API** (`src/`) — 방송사 웹사이트를 스크래핑해 편성표를 제공하는 REST API (로컬/서버 실행용)
2. **Python 서버리스 파이프라인** (`update_schedule.py`) — GitHub Actions + Gemini AI + Cloudflare Pages 기반 자동화 (메인 운영 시스템)

## Commands

```bash
# Node.js API 실행
npm start          # 포트 3000
npm run dev        # nodemon으로 핫리로드

# Python 스크립트 로컬 테스트
pip install -r requirements.txt
GEMINI_API_KEY=<key> python update_schedule.py
```

## Architecture

### Python 서버리스 파이프라인 (운영 중)

```
GitHub Actions (매일 KST 05:00)
  → update_schedule.py
    → Gemini 2.5 Flash (google_search 툴로 실시간 웹 검색)
    → XMLTV 표준 포맷 XML 생성
    → fix_xml_entities() 로 & 등 특수문자 이스케이프
    → validate_xml() 로 파싱 유효성 검증
    → public/ 폴더에 저장
      ├── radio.xml          # 전체 채널 통합
      ├── radio.backup.xml   # 직전 성공본 (fallback)
      ├── channels/{id}.xml  # 채널별 개별 파일
      ├── history/radio-YYYY-MM-DD.xml
      └── index.html
  → Cloudflare Pages 배포 (public/ 디렉토리)
```

`CHANNELS` 리스트가 채널 목록의 단일 소스입니다. 채널 추가/변경은 이 리스트만 수정하면 프롬프트, 채널별 파일 생성, index.html 모두 자동 반영됩니다.

### Node.js API (보조)

- `src/app.js` — Express 진입점
- `src/routes/epg.js` — 라우터 + 캐싱 로직 (30분, node-cache)
- `src/scrapers/{kbs,mbc,sbs,ebs}.js` — 방송사별 HTML 스크래퍼 (cheerio)

## GitHub Actions Secrets 필요값

| Secret | 용도 |
|---|---|
| `GEMINI_API_KEY` | Google AI Studio |
| `CLOUDFLARE_API_TOKEN` | Cloudflare Pages 배포 |
| `CLOUDFLARE_ACCOUNT_ID` | Cloudflare 계정 ID |

## Cloudflare Pages

- 프로젝트명: `radio-schedule`
- 배포 URL: `https://radio-schedule.pages.dev/radio.xml`
- 채널별: `https://radio-schedule.pages.dev/channels/{channel-id}.xml`

## XMLTV 채널 ID 규칙

`{broadcaster}.{type}` 형식 — 예: `kbs.1radio`, `mbc.tv`, `cbs.joy4u`
