# SD Prompt Tag Generator

자연어 이미지 설명을 입력하면 AI가 Stable Diffusion 프롬프트 태그를 자동 생성하고, 실제 Danbooru 태그 데이터베이스에서 검증된 태그로 매칭해주는 로컬 웹 애플리케이션입니다.

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green)
![LangChain](https://img.shields.io/badge/LangChain-0.3+-orange)
![License](https://img.shields.io/badge/License-MIT-yellow)

---

## 주요 기능

- **자연어 → 태그 변환**: 한국어/영어로 이미지를 설명하면 AI가 SD 프롬프트 태그를 생성
- **Danbooru 태그 검증**: 183,700개 실제 태그 DB에서 4단계 매칭 (Exact → Alias → Fuzzy → Vector)
- **3가지 생성 모드**:
  - **Generate**: 이미지 설명 → 태그 생성
  - **Random Expand**: 기본 태그에서 랜덤 확장 (NSFW 레벨 지원)
  - **Scene Expand**: 기본 태그 + 장면 설명으로 확장
- **실시간 스트리밍**: SSE 기반 실시간 생성 과정 확인
- **다중 AI 프로바이더**: OpenAI, Google Gemini, Ollama (로컬) 지원
- **태그 편집**: 생성된 태그를 클릭으로 선택/해제, 커스텀 태그 추가 (자동완성)
- **원클릭 복사**: 최종 프롬프트를 클립보드에 바로 복사

---

## 빠른 시작

### 사전 준비

- **Python 3.10** 이상 ([다운로드](https://www.python.org/downloads/))
- **OpenAI API 키** 또는 **Google Gemini API 키** (둘 중 하나)
  - OpenAI: https://platform.openai.com/api-keys
  - Gemini: https://aistudio.google.com/apikey
  - 또는 **Ollama**를 로컬에 설치하면 API 키 없이 사용 가능

### 1단계: 다운로드

#### 방법 A — Release 다운로드 (권장)

[Releases 페이지](https://github.com/M3GU-1/ai_powered_prompt_generator/releases/latest)에서 최신 버전을 다운로드합니다:

- **Windows**: `.zip` 파일 다운로드 → 압축 해제
- **Mac / Linux**: `.tar.gz` 파일 다운로드 → 압축 해제

```bash
# Mac/Linux 터미널에서:
tar -xzf sd-prompt-tag-generator-v*.tar.gz
cd sd-prompt-tag-generator-v*
```

**태그 인덱스 다운로드 (선택 — 임베딩 빌드 10~20분 스킵):**

같은 Releases 페이지에서 태그 인덱스 파일을 다운로드하면 첫 실행 시 빌드 과정을 건너뛸 수 있습니다:

| 파일 | 설명 | 태그 수 |
|------|------|---------|
| `tag-index-merged.tar.gz` | 통합 (권장) | 183,700 |
| `tag-index-danbooru.tar.gz` | Danbooru만 | 32,259 |
| `tag-index-anima.tar.gz` | Anima만 | 183,174 |

```bash
# data/ 폴더에 압축 해제 (1개 이상 선택)
tar -xzf tag-index-merged.tar.gz -C data/
```

> 태그 소스는 웹 UI의 Settings에서 언제든 전환할 수 있습니다.

#### 방법 B — Git Clone

```bash
git clone https://github.com/M3GU-1/ai_powered_prompt_generator.git
cd ai_powered_prompt_generator
```

> Git LFS가 설치되어 있으면 pre-built 인덱스가 자동으로 포함됩니다.
> LFS 미설치 시: `git lfs install && git lfs pull`

### 2단계: 설정 파일 생성

```bash
cp config.example.yaml config.yaml
```

`config.yaml`을 열어 AI 프로바이더와 API 키를 설정합니다:

```yaml
llm:
  provider: "openai"          # "openai" | "gemini" | "ollama"
  model: "gpt-4o-mini"        # 사용할 모델
  api_key: "sk-your-key"      # API 키 입력
  temperature: 0.7
```

> API 키는 나중에 웹 UI의 Settings 패널에서도 변경할 수 있습니다.

### 3단계: 실행

**Mac / Linux:**
```bash
chmod +x start.sh
./start.sh
```

**Windows:**
```
start.bat
```

첫 실행 시 자동으로 다음 작업이 수행됩니다:
1. Python 패키지 설치 (`requirements.txt`)
2. 태그 임베딩 인덱스 빌드 (10~20분 소요, **최초 1회만** — pre-built 인덱스가 있으면 자동 스킵)
3. 서버 시작 + 브라우저 자동 열림

서버가 시작되면 **http://127.0.0.1:8000** 에서 접속할 수 있습니다.

---

## 사용 방법

### Generate 모드 (기본)

1. 텍스트 입력란에 원하는 이미지를 설명합니다
   - 예: `파란 눈의 금발 소녀가 벚꽃 나무 아래에서 교복을 입고 앉아 있는 모습`
2. 태그 수를 조절합니다 (기본 20개)
3. **Generate Tags** 버튼을 클릭합니다
4. AI가 실시간으로 태그를 생성하고 Danbooru DB에서 검증합니다
5. 결과에서 원하는 태그를 선택/해제합니다
6. **Copy** 버튼으로 최종 프롬프트를 복사합니다

### Random Expand 모드

1. 기본 태그를 쉼표로 구분하여 입력합니다
   - 예: `1girl, blue_hair, school_uniform`
2. 필요 시 NSFW 레벨을 선택합니다 (Spicy / Boost / Explicit)
3. **Expand Tags**를 클릭하면 기본 태그를 기반으로 랜덤 확장됩니다

### Scene Expand 모드

1. 기본 태그를 입력합니다
2. 장면 설명을 추가합니다
   - 예: `교실 창가에 앉아 석양을 바라보며, 따뜻한 빛이 얼굴을 비추는 장면`
3. **Expand with Scene**을 클릭합니다

### 설정 변경

우측 상단 톱니바퀴 아이콘을 클릭하면 Settings 패널이 열립니다:

| 설정 | 설명 |
|------|------|
| **Tag Source** | 태그 데이터베이스 선택 (Merged / Danbooru / Anima) |
| **Provider** | OpenAI, Google Gemini, Ollama 중 선택 |
| **Model** | 프로바이더별 최신 모델 드롭다운 제공 |
| **API Key** | 선택한 프로바이더의 API 키 |
| **Ollama URL** | Ollama 사용 시 서버 주소 (기본: `http://localhost:11434`) |
| **Temperature** | 생성 다양성 (0=일관적, 2=창의적) |

설정 변경 후 **Save Settings**를 클릭하면 서버 재시작 없이 즉시 반영됩니다.

### 지원 모델

**OpenAI:**
GPT-4.1, GPT-4.1 Mini, GPT-4.1 Nano, GPT-4o, GPT-4o Mini, o4 Mini, o3, o3 Mini

**Google Gemini:**
Gemini 2.5 Pro, Gemini 2.5 Flash, Gemini 2.0 Flash, Gemini 1.5 Pro, Gemini 1.5 Flash

**Ollama (로컬):**
Llama 3.2, Llama 3.1, Mistral, Mixtral, Qwen 2.5, Gemma 2, Phi 3 등 설치된 모든 모델

> 드롭다운 목록에 없는 모델은 "Custom..." 옵션으로 직접 입력할 수 있습니다.

---

## 태그 매칭 방식

생성된 태그는 4단계 파이프라인을 거쳐 실제 Danbooru 태그로 검증됩니다:

| 단계 | 방식 | 설명 |
|------|------|------|
| 1 | **Exact** (초록) | 정규화 후 태그명 직접 매칭 |
| 2 | **Alias** (파랑) | 다국어 별칭 사전으로 매칭 |
| 3 | **Fuzzy** (노랑) | 편집 거리 기반 유사 태그 (rapidfuzz) |
| 4 | **Vector** (주황) | FAISS 벡터 유사도 검색 (의미 기반) |

칩 색상으로 매칭 방식을 구분할 수 있으며, 각 태그에 마우스를 올리면 상세 정보 (원본 → 매칭 태그, 유사도 점수, 카테고리, 사용 횟수)를 확인할 수 있습니다.

---

## 수동 설치 (고급)

원클릭 스크립트 대신 수동으로 설치할 수 있습니다:

```bash
# 1. 의존성 설치
pip install -r requirements.txt

# 2. 태그 임베딩 인덱스 빌드 (최초 1회)
# Git Clone 사용자는 LFS로 인덱스가 포함되어 있으므로 이 단계를 건너뛸 수 있습니다.
# Release 사용자는 tag-index-*.tar.gz를 data/에 압축 해제하면 건너뛸 수 있습니다.
python scripts/build_embeddings.py

# 3. 설정 파일 생성
cp config.example.yaml config.yaml
# config.yaml에 API 키 입력

# 4. 서버 실행
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

---

## 프로젝트 구조

```
ai_powered_prompt_generator/
├── backend/                  # Python FastAPI 백엔드
│   ├── main.py              # API 엔트리포인트 + static 파일 서빙
│   ├── llm_service.py       # LangChain 기반 LLM 추상화
│   ├── tag_matcher.py       # 4단계 태그 매칭 파이프라인
│   ├── tag_database.py      # 인메모리 태그 데이터베이스
│   ├── vector_search.py     # FAISS 벡터 검색
│   ├── config_loader.py     # YAML 설정 관리
│   ├── models.py            # Pydantic 스키마
│   └── prompt_templates.py  # LLM 프롬프트 템플릿
├── frontend/                 # Vanilla HTML/CSS/JS 프론트엔드
│   ├── index.html
│   ├── css/style.css
│   └── js/
│       ├── api.js           # API 클라이언트 (REST + SSE)
│       ├── tag-editor.js    # 태그 칩 UI 컴포넌트
│       └── app.js           # 메인 앱 컨트롤러
├── scripts/
│   ├── build_embeddings.py  # CSV → FAISS 인덱스 빌드 스크립트
│   └── package.sh           # 배포용 아카이브 생성
├── .github/workflows/
│   └── release.yml          # 자동 릴리즈 (태그 푸시 시)
├── data/                     # (자동 생성) 태그 DB + 벡터 인덱스
├── danbooru_tags.csv         # Danbooru 태그 데이터 (32K)
├── anima_danbooru.csv        # Anima Danbooru 태그 데이터 (183K)
├── config.example.yaml       # 설정 템플릿
├── config.yaml               # 사용자 설정 (gitignore)
├── requirements.txt          # Python 의존성
├── start.sh                  # Mac/Linux 실행 스크립트
└── start.bat                 # Windows 실행 스크립트
```

---

## 기술 스택

| 영역 | 기술 |
|------|------|
| 백엔드 | Python, FastAPI, Uvicorn |
| AI/LLM | LangChain (OpenAI, Gemini, Ollama) |
| 벡터 검색 | FAISS, sentence-transformers (all-MiniLM-L6-v2) |
| 퍼지 매칭 | rapidfuzz |
| 프론트엔드 | Vanilla HTML/CSS/JS (프레임워크 없음) |
| 설정 관리 | YAML + Pydantic v2 |

---

## 문제 해결

### 서버가 시작되지 않아요
- Python 3.10 이상이 설치되어 있는지 확인하세요: `python3 --version`
- 의존성이 모두 설치되었는지 확인하세요: `pip install -r requirements.txt`

### 임베딩 빌드가 실패해요
- `danbooru_tags.csv`와 `anima_danbooru.csv`가 프로젝트 루트에 있는지 확인하세요
- 디스크 공간이 충분한지 확인하세요 (약 500MB 필요)

### API 키 오류가 나요
- `config.yaml`의 `api_key` 필드에 유효한 키가 입력되었는지 확인하세요
- 또는 웹 UI의 Settings에서 키를 입력하고 Save를 클릭하세요

### Ollama를 사용하고 싶어요
1. [Ollama](https://ollama.com/)를 설치합니다
2. 원하는 모델을 다운로드합니다: `ollama pull llama3.2`
3. Settings에서 Provider를 "Ollama"로 변경하고 모델을 선택합니다
4. API 키는 필요 없습니다

### 태그가 잘 매칭되지 않아요
- Settings에서 Temperature를 낮추면 더 정확한 태그가 생성됩니다
- "Detailed" 옵션을 체크하면 더 구체적인 태그를 생성합니다

---

## API 엔드포인트

직접 API를 호출할 수도 있습니다:

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `POST` | `/api/generate` | 자연어 → 태그 생성 + 매칭 |
| `POST` | `/api/generate/stream` | 스트리밍 태그 생성 (SSE) |
| `POST` | `/api/generate/random-expand/stream` | 랜덤 확장 스트리밍 |
| `POST` | `/api/generate/scene-expand/stream` | 장면 확장 스트리밍 |
| `POST` | `/api/match` | 단일 태그 매칭 |
| `GET` | `/api/tags/search?q=` | 태그 자동완성 검색 |
| `GET` | `/api/config` | 현재 설정 조회 |
| `PUT` | `/api/config` | 설정 변경 (런타임) |
| `GET` | `/api/health` | 서버 상태 확인 |

---

## 릴리즈 배포 (개발자용)

### 자동 릴리즈 (GitHub Actions)

태그를 푸시하면 GitHub Actions가 자동으로 Release를 생성하고 소스 패키지 + 태그 인덱스 아카이브를 첨부합니다:

```bash
git tag v1.0.0
git push origin v1.0.0
```

Release에 포함되는 파일:
- `sd-prompt-tag-generator-v*.zip / .tar.gz` — 소스 코드 패키지
- `tag-index-danbooru.tar.gz` — Danbooru 태그 인덱스
- `tag-index-anima.tar.gz` — Anima 태그 인덱스
- `tag-index-merged.tar.gz` — 통합 태그 인덱스

### 수동 패키징

로컬에서 배포용 아카이브를 직접 생성할 수 있습니다:

```bash
./scripts/package.sh v1.0.0
# → dist/sd-prompt-tag-generator-v1.0.0.zip
# → dist/sd-prompt-tag-generator-v1.0.0.tar.gz
```
