# deploy

GitHub Actions 워크플로우를 즉시 실행해 편성표 XML을 생성하고 Cloudflare Pages에 배포합니다.

## Steps

1. `mcp__github__actions_run_trigger` 로 `cron.yml` 워크플로우를 `main` 브랜치에서 실행
2. `mcp__github__actions_list` 로 실행 상태 확인
3. 완료 후 결과 보고

## Usage

```
/deploy
```
