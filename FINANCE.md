# 재무세무 beta (v2.57)

하단 `재무세무 beta`에서 경제지표, 사업자 상태조회, RSS 브리핑, 기업 공시와 세무 일정 연결 상태를 제공합니다. 기존 하단 메뉴·폰트·색상·버튼을 재사용합니다.

## 연결 설정

`.env.finance.example`은 설정 참고용이며 자동으로 읽지 않습니다. 로컬 프로세스 환경 또는 Render hscope → Environment에 설정하세요. 기존 환경변수를 삭제하거나 대체하지 마세요.

| 환경변수 | 용도 | 미설정 시 |
|---|---|---|
| ECOS_API_KEY | 한국은행 환율, CD 91일·국고채 3년 지표 | 명확히 표시한 예시 숫자 |
| NTS_API_KEY | 국세청 사업자등록 상태조회, 디코딩된 서비스키 | 조회 불가 안내, 사업자 상태를 추측하지 않음 |
| DART_API_KEY | Open DART 최근 90일 공시, 선택한 8자리 고유번호 | 연결 준비 안내와 공식 사이트 링크 |
| BIZINFO_API_KEY | 기업마당 지원사업 RSS 인증키 | 연결 준비 안내 |
| FINANCE_RSS_MOEF/NTS/BIZINFO/PWC/KPMG/JOSEILBO/TAXWATCH/ASSEMBLY | 출처별 검증된 HTTPS RSS URL | 기본값이 없는 출처는 연결 준비 |

- 재정경제부(구 기획재정부) 공식 RSS의 현재 주소를 확인해 기본 연결했습니다. 택스워치 RSS 안내에 기재된 비즈워치 세금 RSS도 기본 연결했습니다(검증 시 정상 XML이나 기사 0건).
- 기업마당 공식 API는 인증키가 필요합니다. `BIZINFO_API_KEY`가 있으면 RSS 형식으로 요청합니다. `FINANCE_RSS_BIZINFO`를 직접 설정하면 그 URL을 우선합니다.
- 국세청·삼일·삼정KPMG·조세일보·국회 피드는 현재 유효한 RSS URL 확인 및 환경변수 설정이 필요합니다. 홈페이지를 RSS로 오인하거나 임의 주소로 수집하지 않습니다.
- RSS는 출처·분류·제목·요약·원문·발행일, 지표는 코드·이름·기준일·값·직전 관측 대비 증감으로 정규화합니다. 지표 값은 시세가 아니라 ECOS의 최근 발표값입니다.
- 대시보드 15분 / 공시 5분 프로세스 캐시. 최초 조회는 대기 응답 후 자동 재조회합니다. 프로세스 재시작 시 캐시가 비워지며 다음 방문에 수집합니다. 영구 기사 보관 및 백그라운드 정기 수집은 포함하지 않습니다.
- 조회 제한시간·병렬 수 제한·RSS 크기 제한·외부 XML 엔티티 차단·HTML 제거·링크 프로토콜 제한을 적용합니다. 키와 사업자번호를 앱 로그/DB에 저장하지 않으며 사업자 응답은 `no-store`입니다.
- 일부 연동이 실패해도 나머지 위젯은 유지됩니다. 빈 공시와 서비스 실패를 구분합니다. API 키를 브라우저로 보내지 않습니다.

## 세무 일정

기획 이미지의 **공공데이터포털 독일 정보 API**는 확인되지 않은 문구이므로 `collector/finance.py`에 TODO로 남겼습니다. 검증된 한국 공휴일 데이터, 신고대상·납기 연장 예외를 검토한 룰셋이 준비되기 전까지 자동 기한과 D-day를 생성하지 않습니다. UI에는 연결 준비 상태와 국세청 바로가기를 제공합니다.

## 근거 문서

- [재정경제부 RSS 안내](https://www.moef.go.kr/mn/siteguide/rssService.do?menuNo=2060000)
- [기업마당 지원사업 API](https://www.bizinfo.go.kr/apiDetail.do?id=bizinfoApi)
- [국세청 사업자등록정보 상태조회](https://www.data.go.kr/data/15081808/openapi.do)
- [ECOS Open API](https://ecos.bok.or.kr/api/)
- [Open DART 개발가이드](https://opendart.fss.or.kr/guide/main.do)
- [택스워치 RSS 안내](https://www1.taxwatch.co.kr/help/rss)

## 검증

`python -m unittest discover -s tests -v`, `node --test tests/test_frontend_data.cjs`, JS 문법 검사, Gunicorn 실행 및 브라우저에서 탭 전환·폼·검색·반응형 레이아웃 확인. 실 API 키를 필요로 하는 유료/인증 호출은 모의 응답으로 정상·실패를 검증하며 실제 계정 키 검증은 별도입니다.
