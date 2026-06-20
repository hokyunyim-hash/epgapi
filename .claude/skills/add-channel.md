# add-channel

`update_schedule.py`의 `CHANNELS` 리스트에 새 채널을 추가하고 GitHub에 푸시합니다.

## Steps

1. 사용자에게 채널 정보 확인: broadcaster, name, id, frequency
2. `mcp__github__get_file_contents`로 현재 `update_schedule.py` SHA 조회
3. CHANNELS 리스트에 항목 추가
4. `mcp__github__create_or_update_file`로 main 브랜치에 푸시
5. 워크플로우 실행 여부 확인

## Channel ID 규칙

`{broadcaster}.{type}` 형식 — 예: `kbs.1radio`, `jtbc.tv`, `cbs.joy4u`

## Usage

```
/add-channel CBS JOY4U
```
