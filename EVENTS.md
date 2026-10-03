# 행사 수집 (구조화 소스)

행사 탭은 기본적으로 **구글 뉴스 RSS**(기사화된 행사)에서 모으지만, 누락이 많다.
`collector/event_sources.py`가 **행사를 목록으로 직접 제공하는 공공 Open API**를 추가로 수집해
날짜·장소가 확정된 행사를 채운다. 각 소스는 **env 미설정 시 자동 skip, 실패 시 degrade**(날조 없음).

## 1) 한국관광공사 TourAPI — 행사/축제 (추천 1순위)

전국 축제·문화행사를 날짜·장소·이미지까지 구조화해 제공. 커버리지가 가장 크다.

- 발급: [공공데이터포털](https://www.data.go.kr) → **“한국관광공사_국문 관광정보 서비스”** 활용신청 → **서비스키(디코딩, Decoding)** 복사.
- Render(hscope) → Environment 에 추가 후 재배포:
  - `TOURAPI_KEY = <디코딩 서비스키>`
  - (선택) `TOURAPI_FESTIVAL_URL` — 기본값 `https://apis.data.go.kr/B551011/KorService2/searchFestival2`. 서비스 버전이 다르면(KorService1 등) 이 값으로 교체.
- 매핑: `eventstartdate/eventenddate`(YYYYMMDD) → 시작/종료일, `addr1` → 장소·지역, `firstimage` → 이미지, `contentid` → 상세 링크.

## 2) 문화포털/공공 문화행사 API (선택)

제공처마다 응답 필드가 달라 **URL과 키를 모두 env로** 받는다(둘 다 있어야 동작).

- `CULTURE_API_KEY = <서비스키>`
- `CULTURE_API_URL = <문화행사 목록 JSON 엔드포인트>`
- 흔한 필드명(title/startDate/endDate/place/url 등)을 넓게 시도하며, 안 맞으면 진단으로 보정.

## 확인 · 진단

브라우저로 **`/api/eventcheck`** 를 열면(로그인 불필요) 소스별로 다음을 보여준다(서비스키 비노출):

- `configured` (env 설정 여부), `parsed` (파싱된 행사 수)
- `raw.status` (HTTP 상태), `raw.rows` (응답 행수), `raw.first_keys` (첫 항목 필드명), `raw.sample` (원문 일부)

`parsed > 0` 이면 성공. `configured`인데 `parsed=0`이면 `raw.first_keys`/`raw.sample`로 **필드 매핑을 보정**한다(엔드포인트가 틀리면 `raw.status`/`sample`에 오류가 보인다).

## 동작

- 수집 실행(행사) 또는 4시간 배치에서 `events.crawl`이 구글 뉴스 결과에 **구조화 소스 결과를 병합**(제목+시작일로 중복 제거)한다.
- 종료된 행사(end_date < 오늘)는 `db.list_events`가 자동으로 제외한다.
