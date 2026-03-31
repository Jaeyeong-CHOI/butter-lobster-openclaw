# butter-lobster-openclaw

![Butter Lobster OpenClaw mascot](assets/butter-lobster-openclaw-v6.png)

실전에서 바로 가져다 쓸 수 있는 **OpenClaw 공개 스타터 키트**입니다.

> English version: [README.md](README.md)

---

## 이 저장소의 목표

- OpenClaw 초기 세팅을 빠르게 시작
- 프롬프트/운영 규칙 md를 재사용
- 개인/팀 환경에 맞게 쉽게 커스터마이즈

---

## 빠른 시작

```bash
git clone <your-repo-url>
cd butter-lobster-openclaw
mkdir -p ~/.openclaw
cp starter/openclaw.sample.json ~/.openclaw/openclaw.json
```

그 다음 `~/.openclaw/openclaw.json`에서 토큰/채널 설정만 채우면 됩니다.

Gateway 실행:

```bash
openclaw gateway start
openclaw gateway status
```

---

## 포함된 구성

- 핵심 프롬프트/운영 규칙
  - `AGENTS.md`, `SOUL.md`, `HEARTBEAT.md`, `docs/*`
- 재사용 프롬프트 템플릿
  - `agent-prompts/*`
- 예시 스킬 (보고서/슬라이드 포맷)
  - `skills/latex-report-format/*`
  - 패키지: `skills/dist/latex-report-format.skill`
- ACP 기본 에이전트 동기화 유틸
  - `config/sync_acp_default_agent.py`
- 샘플 설정
  - `starter/openclaw.sample.json`

---

## 커스터마이즈 포인트

- 어시스턴트 톤/정체성: `SOUL.md`
- 실행 규칙: `AGENTS.md`
- 주기 점검: `HEARTBEAT.md`
- 포맷 스킬: `skills/latex-report-format/`
- 모델 기반 ACP 라우팅 동기화: `config/sync_acp_default_agent.py`

---

## 오픈소스 기본 문서

- 라이선스: [MIT](LICENSE)
- 기여 가이드: [CONTRIBUTING.md](CONTRIBUTING.md)
- 행동 강령: [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)
- 보안 정책: [SECURITY.md](SECURITY.md)

---

## 주의

- 실제 비밀키/토큰은 절대 커밋하지 마세요.
- 개인 메모/민감 파일은 공개 저장소와 분리해 운영하세요.
