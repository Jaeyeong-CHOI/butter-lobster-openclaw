# Memory Management

## 구조

- **Daily log:** `memory/YYYY-MM-DD.md` — 그날 있었던 일의 원시 기록
- **Long-term:** `MEMORY.md` — daily log에서 중요한 것만 추출한 정제된 기억
- **Projects:** `memory/projects/*.md` — 프로젝트별 상세 상태
- **Plans:** `memory/plans/*.md` — 실행 계획 (일급 아티팩트)
- **State:** `memory/*.json` — heartbeat/cron 등 상태 추적

## 규칙

### 기록 원칙
- "Mental note" 금지. 기억하고 싶으면 **파일에 쓸 것**
- `memory/YYYY-MM-DD.md` 또는 관련 파일에 즉시 기록
- 교훈 → `docs/patterns.md` 업데이트
- 실수 → 문서화해서 미래의 내가 반복하지 않도록

### MEMORY.md 관리
- **Main session에서만** 로드 (보안: 그룹챗/Discord에서는 로드 금지)
- 자유롭게 읽기/편집/업데이트 가능
- 중요한 이벤트, 결정, 의견, 교훈을 기록
- 정기적으로(며칠에 한 번) daily file 리뷰 → MEMORY.md 갱신

### 메모리 유지보수 (Heartbeat 중)
1. 최근 `memory/YYYY-MM-DD.md` 파일 리뷰
2. 장기 보존할 인사이트 식별
3. MEMORY.md에 정제된 내용 추가
4. 더 이상 관련 없는 오래된 정보 제거

> 비유: daily file = 일기장, MEMORY.md = 정제된 지혜
