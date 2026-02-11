# AI-Powered SD Prompt Tag Generator

## Project Overview
자연어 이미지 설명을 입력하면 LLM이 Stable Diffusion 프롬프트 태그를 생성하고, FAISS 벡터 유사도 검색으로 실제 danbooru 태그에 매칭/교정하여 유효한 태그를 제공하는 로컬 웹 애플리케이션.

## Architecture
- **Backend**: Python FastAPI (backend/main.py)
- **Frontend**: Vanilla HTML/CSS/JS (frontend/)
- **LLM**: LangChain 기반 다중 프로바이더 (OpenAI, Gemini, Ollama)
- **Vector Search**: FAISS + sentence-transformers (all-MiniLM-L6-v2)
- **Tag Database**: danbooru_tags.csv + anima_danbooru.csv → merged 183,700 tags
- **Config**: config.yaml (YAML, Pydantic validation)

## Project Structure
```
backend/
  main.py              # FastAPI 엔트리포인트, API 라우트, static 서빙
  config_loader.py     # config.yaml 로드/저장 (Pydantic BaseModel)
  models.py            # API 요청/응답 Pydantic 스키마
  tag_database.py      # 인메모리 태그 DB (exact/alias/fuzzy 매칭)
  tag_matcher.py       # 4단계 매칭 파이프라인 (핵심 로직)
  vector_search.py     # FAISS 인덱스 로드 및 유사도 검색
  llm_service.py       # LangChain LLM 추상화 (OpenAI/Gemini/Ollama)
  prompt_templates.py  # SD 태그 생성 프롬프트 템플릿
frontend/
  index.html           # 싱글 페이지 UI
  css/style.css        # 다크 테마 스타일
  js/api.js            # fetch 기반 API 클라이언트
  js/tag-editor.js     # TagEditor 클래스 (태그 칩 UI 컴포넌트)
  js/app.js            # 메인 앱 컨트롤러 (IIFE)
scripts/
  build_embeddings.py  # 1회성: CSV 병합 → FAISS 인덱스 생성
data/
  merged_tags.json     # 생성됨: 병합된 태그 DB
  faiss_index/         # 생성됨: FAISS 벡터 인덱스 (60,059 vectors)
```

## Key Commands
```bash
# 서버 실행
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000

# FAISS 인덱스 재빌드 (CSV 변경 시)
python scripts/build_embeddings.py

# 원클릭 실행 (Windows / Mac)
start.bat   # Windows
./start.sh  # Mac/Linux

# 의존성 설치
pip install -r requirements.txt
```

## API Endpoints
| Method | Path | Description |
|--------|------|-------------|
| POST | /api/generate | 자연어 → LLM 태그 생성 + 매칭 |
| POST | /api/match | 단일 태그 매칭 |
| GET | /api/config | LLM 설정 조회 |
| PUT | /api/config | LLM 설정 변경 (런타임) |
| GET | /api/tags/search?q= | 태그 자동완성 (prefix) |
| GET | /api/health | 서버 상태 확인 |

## Core Pipeline (tag_matcher.py)
태그 매칭 4단계 (short-circuit 방식):
1. **Exact Match** → 정규화(lowercase, _ 변환) 후 태그명 직접 조회
2. **Alias Match** → alias_map 딕셔너리 조회 (다국어 alias 포함)
3. **Fuzzy Match** → rapidfuzz 편집거리 (threshold ≥ 80)
4. **Vector Search** → FAISS 코사인 유사도 (k=10, min_score=0.3)

Stage 1-2는 매칭시 즉시 반환. Stage 3-4는 병합 후 `score * 0.9 + popularity * 0.1` 랭킹.

## Coding Conventions

### Python (Backend)
- Python 3.9+ 호환 (`str | None` 대신 `Optional[str]` 사용)
- Pydantic v2 BaseModel로 모든 API 스키마 정의
- FastAPI async 엔드포인트
- 타입 힌트 필수 (함수 시그니처)
- import 순서: stdlib → third-party → local (backend.*)

### JavaScript (Frontend)
- Vanilla JS (프레임워크 없음), ES6+
- innerHTML 사용 금지 → textContent + DOM API 사용 (XSS 방지)
- API 호출은 반드시 api.js의 API 객체를 통해
- TagEditor 클래스가 태그 UI 상태 관리
- app.js는 IIFE로 글로벌 오염 방지

### CSS
- CSS 변수 기반 다크 테마 (:root에 정의)
- 매칭 방식별 색상: exact=green, alias=blue, fuzzy=yellow, vector=orange

## Configuration
- `config.yaml`: 사용자 설정 (API 키 포함, gitignore 대상)
- `config.example.yaml`: 기본 템플릿 (git 추적)
- 설정은 PUT /api/config로 런타임 변경 가능 (서버 재시작 불필요)

## Data Sources
- `danbooru_tags.csv`: 32,259 tags (cat 0=general, 3=copyright, 4=character), 다국어 alias
- `anima_danbooru.csv`: 183,174 tags (cat 0,1=artist,3,4,5=meta), 영문 alias
- 병합 시 anima를 base로 사용, alias는 union, count는 max
- 임베딩 대상: general(cat 0) 전체 + copyright/character(cat 3,4) count≥100 → 60,059개

## Agent & Tool Usage Rules (필수 준수)

### 원칙: 서브에이전트, MCP, 플러그인을 적극적으로 활용할 것
단순 파일 읽기/검색을 넘어서는 모든 작업에서 아래 도구들을 **능동적으로** 사용해야 한다.
독립적인 작업은 반드시 **병렬 실행**하여 효율을 극대화할 것.

---

### MCP Servers

#### Serena (코드 분석/편집)
- **반드시 사용**: Python 백엔드 심볼 탐색, 리팩토링, 참조 추적
- `find_symbol`: 클래스/함수 위치 및 시그니처 확인 (예: `TagMatcher/match_single_tag`)
- `find_referencing_symbols`: 함수 수정 시 모든 호출처 확인 (하위 호환성 보장)
- `get_symbols_overview`: 파일의 전체 심볼 구조 파악 (파일 전체 읽기 전에 먼저 호출)
- `replace_symbol_body`: 함수/클래스 단위 정밀 교체
- `search_for_pattern`: 정규식 기반 코드베이스 전체 검색
- 편집 시 `replace_content`(regex)로 부분 수정, `replace_symbol_body`로 전체 교체 구분 사용
- `think_about_collected_information`: 검색 후 정보 충분성 평가
- `think_about_task_adherence`: 코드 수정 전 작업 방향 재확인

#### Context7 (라이브러리 문서)
- **반드시 사용**: LangChain, FastAPI, FAISS, sentence-transformers 등 라이브러리 API 불확실 시
- `resolve-library-id` → `query-docs` 순서로 호출
- 예: LangChain 새 체인 문법, FastAPI 라이프사이클, FAISS 인덱스 옵션 확인

#### Playwright (브라우저 테스트)
- **반드시 사용**: 프론트엔드 변경 후 시각적 검증
- `browser_navigate` → `browser_snapshot`으로 UI 상태 확인
- `browser_click`, `browser_type`으로 사용자 인터랙션 시뮬레이션
- 서버가 http://127.0.0.1:8000 에서 실행 중이어야 함
- 프론트엔드 수정 후에는 반드시 스냅샷으로 렌더링 결과 확인

#### GitHub MCP
- 이슈 생성/관리: `create_issue`, `list_issues`
- PR 워크플로우: `create_pull_request`, `get_pull_request`
- 코드 검색: `search_code`로 유사 구현 참고

---

### Subagents (Task tool)

#### 탐색/조사 (읽기 전용)
- **Explore** (`subagent_type=Explore`): 코드베이스 구조 파악, 파일 패턴 검색
  - 3회 이상 Grep/Glob이 필요한 넓은 범위 탐색 시 사용
  - 예: "벡터 검색 관련 코드 전체 흐름 파악"
- **Plan** (`subagent_type=Plan`): 구현 전략 설계, 여러 접근법 비교
  - 복잡한 기능 추가 전 아키텍처 검토

#### 구현/실행
- **developer** (`subagent_type=developer`): 아키텍처 문서 기반 코드 구현
- **feature-dev:code-architect**: 기존 패턴 분석 후 새 기능 설계도 작성
- **feature-dev:code-explorer**: 실행 경로 추적, 아키텍처 레이어 매핑

#### 품질 관리
- **code-reviewer** (`subagent_type=code-reviewer`): 코드 변경 후 품질 리뷰 (필수)
  - 주요 기능 구현 완료 시 반드시 실행
- **feature-dev:code-reviewer**: 버그, 보안, 성능 이슈 필터링
- **test-designer** (`subagent_type=test-designer`): 구현 전 테스트 케이스 정의 (TDD)
- **code-simplifier:code-simplifier**: 복잡한 코드 정리/간소화

#### 대규모 작업
- **orchestrator** (`subagent_type=orchestrator`): 다단계 개발 파이프라인 조율
- **planner** (`subagent_type=planner`): 작업 분해, 의존성 파악, 로드맵 생성

#### 병렬 실행 규칙
- 독립적인 서브에이전트는 **하나의 메시지에서 동시에** 여러 개 실행
- 예: Explore(백엔드 구조) + Explore(프론트엔드 구조) 동시 실행
- 예: code-reviewer(backend 변경) + playwright 테스트 동시 실행

---

### Skills (슬래시 커맨드)

| Skill | 사용 시점 |
|-------|----------|
| `/commit` | 코드 변경 커밋 |
| `/commit-push-pr` | 커밋 + 푸시 + PR 생성 |
| `/code-review` | PR 코드 리뷰 |
| `/feature-dev` | 가이드 기반 기능 개발 시작 |
| `/frontend-design` | UI 컴포넌트 설계/구현 |
| `/ralph-loop` | 반복 패턴 자동 수정 루프 |
| `/brainstorming` | 새 기능/변경 전 요구사항 탐색 (창작 작업 전 필수) |
| `/writing-plans` | 멀티스텝 구현 계획 작성 |
| `/test-driven-development` | TDD 방식 구현 시작 |
| `/systematic-debugging` | 버그/테스트 실패 체계적 디버깅 |
| `/verification-before-completion` | 완료 선언 전 검증 (필수) |
| `/requesting-code-review` | 코드 리뷰 요청 |
| `/finishing-a-development-branch` | 브랜치 작업 마무리 (merge/PR/cleanup) |

---

### 플러그인 활용 워크플로우

#### 1. UI 컴포넌트 개발
```
frontend-design → 디자인 시스템 기반 컴포넌트 설계
Context7       → FastAPI, LangChain 최신 API 확인
playwright     → 변경 후 브라우저 스냅샷으로 시각 검증
```

#### 2. 코드 품질 관리
```
code-review    → 변경된 코드 리뷰
serena         → 심볼 기반 참조 추적, 리팩토링 영향 분석
code-simplifier → 복잡한 로직 정리
```

#### 3. 테스트 자동화
```
playwright     → E2E 테스트 시나리오 (navigate → interact → snapshot)
test-designer  → API 엔드포인트별 테스트 케이스 설계 (subagent)
```

#### 4. 대규모 변경 작업
```
ralph-loop     → 반복적인 패턴 수정 자동화
superpowers    → 복잡한 멀티스텝 (dispatching-parallel-agents 등)
orchestrator   → 다단계 개발 파이프라인 (subagent)
```

#### 5. 신규 기능 개발 표준 절차
```
1. /brainstorming           → 요구사항/디자인 탐색
2. /writing-plans           → 구현 계획 작성
3. /test-driven-development → 테스트 먼저 정의
4. feature-dev 또는 developer subagent → 코드 구현
5. playwright snapshot      → UI 검증
6. code-reviewer subagent   → 품질 리뷰
7. /verification-before-completion → 최종 검증
8. /commit                  → 커밋
```

#### 6. 버그 수정 표준 절차
```
1. /systematic-debugging    → 원인 분석
2. serena find_referencing_symbols → 영향 범위 확인
3. 수정 구현
4. playwright 테스트         → 회귀 확인
5. /verification-before-completion → 검증
```

---

### 도구 선택 우선순위

| 상황 | 우선 사용 | 보조 사용 |
|------|----------|----------|
| Python 심볼 탐색 | Serena `find_symbol` | Grep |
| Python 함수 수정 | Serena `replace_symbol_body` | Edit |
| Python 부분 수정 (몇 줄) | Serena `replace_content` (regex) | Edit |
| Python 참조 추적 | Serena `find_referencing_symbols` | Grep |
| 파일 구조 파악 | Serena `get_symbols_overview` | Read |
| 라이브러리 API 확인 | Context7 `query-docs` | WebSearch |
| 프론트엔드 검증 | Playwright `browser_snapshot` | Read |
| 넓은 코드베이스 탐색 | Explore subagent | Grep + Glob |
| 코드 리뷰 | code-reviewer subagent | 수동 Read |
| 테스트 설계 | test-designer subagent | 수동 작성 |

## Important Notes
- `config.yaml`은 API 키를 포함하므로 절대 커밋하지 않음
- `data/` 디렉토리의 생성 파일들도 gitignore 대상
- FAISS 인덱스 재빌드는 CPU에서 약 25초 소요 (60K tags)
- 서버 시작 시 FAISS 인덱스 + embedding 모델 로드로 약 10-15초 소요
- LLM 미설정 시에도 태그 검색/매칭 API는 독립적으로 동작
