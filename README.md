# 휴 스코프 (Hscope)

김상화가 생활과 업무에 필요한 정보를 모아 쓰기 위해 제작·개선하는 개인 서비스입니다.

**현재 버전: v3.66 · build 261004**

- 서비스: https://hscope.onrender.com/
- 소개: https://hscope.onrender.com/intro
- 운영 브랜치: `claude/quirky-euler-agfmp`
- 변경 당시 기록: [CHANGELOG.md](CHANGELOG.md)
- 현재 기능·구조·설정·운영: [DEVNOTE.md](DEVNOTE.md)

## 제공 기능

- **뉴스**: 냥정보·게임정보·NC 뉴스·비영리재단 동향·보안뉴스·행사일정. 동향 뉴스·재단 게시판·유튜브는 하나의 동향 화면에서 탐색합니다.
- **본문 읽기**: 앱에서 기사 본문과 AI 핵심 요약을 확인하며, 추출 실패 시 수집 요약과 원문 링크를 제공합니다.
- **행사**: 뉴스·공공 API·7개 공식 행사장 출처를 병합하고 일반 일정의 리스트·앨범·캘린더 및 관심 행사 큐레이션을 제공합니다.
- **맛집**: 기본 위치 3곳, GPS 내 위치, 주소·장소 검색으로 주변 식당을 조회합니다. 최근 위치·실제 주소 표시·개별 삭제를 지원합니다.
- **주변 맛집 다운로드**: 저장 정보를 먼저 조회하고 사용자 확인 후 신규 식당만 추가합니다. 기존 식당·리뷰·방문 기록을 보존합니다.
- **점심 추천**: 현재는 성향·기분·회피 음식·평점·거리·방문 기록에 따른 점수 기반 규칙 추천입니다.
- **재무세무 beta**: 경제지표·계산기·세무 일정·사업자 상태조회·기업 공시·RSS 브리핑.
- **리포트·개인화**: 재단 동향·월간 보안 리포트, 로그인 사용자의 스크랩·읽음·그룹·맛집 후기와 방문 기록.

## 구조와 저장

Python Flask·Gunicorn으로 실행하고 Render에서 GitHub 운영 브랜치 변경을 자동 배포합니다. PostgreSQL은 `DATABASE_URL`로 연결합니다. 미설정 시 SQLite를 사용하며 임시 호스팅 파일시스템에서 영구 보관을 보장하지 않습니다.

계정 개인 기록은 서버에 저장하고, 보기·관심사·최근 맛집 위치는 해당 브라우저에 저장합니다. 조회 캐시와 백그라운드 작업 상태는 프로세스 단위입니다. 기사와 고정 위치 식당의 기존 갱신 수집, 주변 식당의 신규 삽입 다운로드는 서로 다른 저장 정책입니다.

외부 연동은 Google News RSS·기관 목록 API·YouTube·공공/행사장 일정·Kakao Local·Anthropic·ECOS·Open DART·국세청 API를 사용합니다. API 키는 서버 환경에서 사용합니다. 관리자 수집·초기화·설정·리포트 생성과 공개 조회 권한을 구분합니다.

## 로컬 실행

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

필요한 환경변수는 프로세스 환경에 설정합니다. 상세 설정은 [DEVNOTE.md](DEVNOTE.md), 행사 출처는 [EVENTS.md](EVENTS.md), 재무세무 연동·산식은 [FINANCE.md](FINANCE.md)를 참고합니다. Render 연결 구성은 [render.yaml](render.yaml)과 [DEPLOY.md](DEPLOY.md)를 확인합니다.

## 검사와 기록

```bash
python -m unittest discover -s tests -v
node --test tests/*.cjs
```

변경 범위에 맞는 검사를 선택합니다. 모의 응답 검사와 실제 키·기기에서의 검증을 구분합니다. 기능 변경 시 코드와 버전·패치내역·개발자노트의 관련 절을 함께 갱신하고, 배포 후 운영 화면과 API 응답을 확인합니다.

v3.59~v3.64는 v3.58 이후 버전 표기 없이 배포된 변경을 실제 커밋 순서에 따라 이번 정비에서 복원한 번호입니다. 과거 기록을 당시 화면 표시 버전으로 오인하지 않도록 [CHANGELOG.md](CHANGELOG.md)에 적용 근거를 남겼습니다.
