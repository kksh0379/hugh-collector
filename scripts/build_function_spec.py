"""Build the launcher IA document from reviewed specifications and template controls."""
from pathlib import Path
from bs4 import BeautifulSoup
import html, json, re
ROOT=Path(__file__).resolve().parents[1]
VERSION='3.129'
SOURCE='7d758358c84cff11dbd077eef2316d673a417b36'
REPO='https://github.com/kksh0379/ncfoundation-collector/blob/'
rows=[]
# description / inputs / result / exceptional state / access / persistence / API
D={}
def define(key,desc,inputs='해당 화면에서 선택 또는 실행',result='해당 조건의 화면 상태를 갱신',error='실패·빈 결과 상태를 해당 영역에 표시',access='방문자·로그인 사용자·관리자',store='화면 상태',api=''):
 D[key]=[desc,inputs,result,error,access,store,api]
for key,desc in {
 'features-btn':'일반 사용자와 방문자에게 보일 탭·기능의 표시 설정 팝업을 연다. 관리자는 숨긴 항목도 볼 수 있다.',
 'notes-btn':'관리자 패치내역 팝업에서 날짜별 버전과 변경 사항을 조회한다. 개발자 노트 본문은 이 팝업에서 제공하지 않는다.',
 'runlog-btn':'수집 로그·접속 로그 탭을 가진 관리자 팝업을 연다.',
 'purge-db-btn':'현재 화면에 대응하는 초기화 범위를 확인하고 사용자 확인 후 저장 자료를 삭제한다. 비영리 동향은 별도의 초기화 대상 선택값을 사용한다.',
 'lunch-collect':'기본 위치의 주변 식당 수집 작업을 시작하고 진행 상태를 조회한다. 기존 식당 갱신이 가능한 관리자 경로다.',
 'lunch-add':'현재 등록 위치에 식당명·분류·지도 URL을 입력받아 식당을 직접 추가한다.',
 'lunch-diag':'Kakao 키 설정 여부와 수집 연결 상태를 진단해 표시한다.',
 'run-report':'선택한 재단 분기 또는 보안 월간 리포트 분석을 시작한다. 저장된 기사 근거를 AI에 전달하고 완료 결과를 스냅샷으로 저장한다.',
 'report-del':'확인 후 현재 선택한 리포트 스냅샷을 삭제한다.',
 'report-purge':'확인 후 리포트 스냅샷 초기화를 요청한다. 취소하면 삭제하지 않는다.',
 'biz-reset-scope':'초기화 대상을 동향 전체/동향 뉴스/재단 게시판/재단 영상 중 선택한다. 선택만으로 삭제하지 않고 상단 초기화 버튼에 전달한다.',
}.items():define(key,desc,access='관리자',store='DB 변경 또는 관리자 조회',error='인증 실패·작업 중·연결 실패·취소 상태를 구분')
D['notes-btn'][-1]='GET /api/notes';D['features-btn'][-1]='GET/POST /api/features';D['runlog-btn'][-1]='GET /api/runlog · /api/visitlog';D['purge-db-btn'][-1]='POST /api/admin/purge';D['run-report'][-1]='POST /api/report/run';D['report-del'][-1]=D['report-purge'][-1]='POST /api/report/purge';D['lunch-collect'][-1]='POST /api/lunch/collect';D['lunch-add'][-1]='POST /api/lunch/restaurant';D['lunch-diag'][-1]='GET /api/lunch/diag'
define('login-btn','일반 사용자 기본 로그인 모드로 로그인 팝업을 연다. 관리자/다른 계정 모드로 전환 가능하다.',result='로그인 유형·안내·입력 필드 표시',store='팝업 상태')
define('logout-btn','서버 세션을 종료하고 사용자 전용 표시를 해제한다.',result='비로그인 UI로 전환',store='서버 로그인 세션 종료',api='POST /api/logout')
define('login-submit','선택한 로그인 유형의 인증 정보를 서버에 전송한다. 성공 시 사용자 자료를 불러오며 로그인 전 대기한 스크랩 작업이 있으면 이어서 처리한다.',inputs='일반 기본 계정 또는 직접 입력한 아이디/비밀번호, 관리자 비밀번호',result='세션 생성·사용자명·권한 표시·팝업 닫힘',error='잘못된 인증은 오류를 표시하고 팝업 유지. 연결 실패 시 재시도 안내',store='서버 세션',api='POST /api/login · GET /api/mydata')
define('login-other','일반 사용자 모드에서 기본 테스트 계정 안내와 직접 아이디·비밀번호 입력 모드를 전환한다.',store='팝업 상태')
define('tab-search','현재 뉴스/행사 탭의 항목을 검색한다. 한글 초성·부분 문자열·유사 입력 처리와 현재 탭 분류 조건을 함께 사용한다.',inputs='검색 문자열; 현재 탭',result='목록과 결과 건수 갱신',error='일치 항목 없으면 빈 결과 표시',store='탭별 화면 검색 상태')
define('search-btn','현재 입력된 탭 검색어를 적용한다. Enter 입력과 같은 검색 동작이다.',result='분류와 검색의 교집합 목록 표시',store='탭별 화면 검색 상태')
define('search-clear','현재 탭의 검색어를 지우고 현재 분류 조건의 목록으로 돌아간다.',inputs='검색어가 있을 때 버튼 표시',store='탭별 화면 검색 상태')
for group in ['cat','game','news','biz','security','event']:
 define('status-'+group+'-btn','해당 수집 그룹의 저장 건수·최근 수집 시각·연결/작업 상태를 관리자 상태창에 표시한다.',access='관리자',store='조회만',api='GET /api/crawl/status 및 그룹별 진단')
 define('collect-'+group,'해당 그룹의 수집 작업을 비동기로 시작하고 진행 상태와 신규/갱신 건수를 표시한다. 표시된 기존 목록은 결과 갱신 전까지 유지한다.',inputs='관리자; 진행 중 중복 실행 억제',result='상태 폴링 후 목록 갱신',error='실패·일부 수집·보류 출처 표시; 기존 자료 유지',access='관리자',store='DB 수집 자료',api='POST /api/crawl/<group>/start · GET /api/crawl/<group>/status')
for key,name in [('collect-boards','재단 게시판'),('collect-social','재단 영상')]:
 define(key,name+'의 고정 출처 또는 검색 수집을 실행한다. 출처별 실패·보류·확보 건수를 결과 상세에 표시한다.',result='신규·갱신 건수 및 출처별 상태',access='관리자',store='DB',api='POST /api/crawl/<group>/start')
define('ed-settings','관심 분야·키워드 설정창을 연다. 버튼을 누르는 것만으로 AI API를 호출하지 않는다.',result='관심사 설정 대화상자',store='설정창 상태')
for key,desc,api in [
 ('lunch-loc-btn','기본 위치 3곳·내 위치·최근 위치 목록을 펼친다. 선택한 위치명·주소·반경을 요약 표시한다.','GET /api/lunch/locations'),
 ('lunch-address-open','주소로 위치 지정 팝업을 열어 주소 또는 장소명 검색을 준비한다.',''),
 ('lunch-address-query','주소나 장소명을 2~100자로 입력한다. 식당 다운로드를 자동 시작하지 않는다.',''),
 ('lunch-address-submit','Kakao 주소 검색, 없으면 장소 키워드 검색으로 최대 8개 위치 후보를 받아 표시한다.','POST /api/lunch/address/search'),
 ('lunch-gps-radius','GPS·주소 위치의 반경을 500m/1km/2km로 선택하고 저장된 주변 식당을 다시 조회한다.','POST /api/lunch/nearby'),
 ('lunch-gps-refresh','브라우저에 GPS 위치를 다시 요청한다. 성공 후 저장된 주변 식당 조회와 주소 변환을 실행한다.','POST /api/lunch/nearby · /api/lunch/address/reverse'),
 ('lunch-gps-download','미확보 영역의 주변 맛집 다운로드 확인창을 연다. 클릭만으로 수집하지 않는다.',''),
 ('lunch-download-cancel','다운로드를 시작하지 않고 확인창을 닫는다. 기존 식당 목록으로 계속 탐색한다.',''),
 ('lunch-download-confirm','확인값과 좌표를 보내 백그라운드 다운로드를 시작한다. 새 식당만 저장하고 기존 식당·리뷰·방문은 유지한다.','POST /api/lunch/nearby/download · GET /api/lunch/nearby/download/status'),
 ('lunch-search','현재 위치에 로드된 식당명·음식 분류를 검색한다.',''),
 ('lunch-search-btn','현재 식당 검색어를 적용하고 음식 분류/검증된 곳 조건의 결과를 갱신한다.',''),
 ('lunch-ai-btn','성향·기분·회피 음식 선택 화면으로 전환한다. 현재 추천 엔진은 LLM이 아닌 규칙 기반이며 토큰을 쓰지 않는다.',''),
 ('lunch-rev-back','식당 후기 화면에서 이전 맛집 목록으로 돌아간다.',''),
 ('lunch-ai-back','추천 설정/결과 화면에서 맛집 목록으로 돌아간다.',''),
]:define(key,desc,store='화면·최근 위치는 브라우저 저장; 다운로드 결과는 DB',error='위치 권한 거절·시간 초과·Kakao 연결 실패·빈 결과를 안내',api=api)
define('scrap-open-btn','하단 스크랩 화면을 연다. 비로그인 방문자는 로그인 창으로 안내하고 로그인 후 사용자 저장 자료를 표시한다.',inputs='표시 설정에서 스크랩 활성; 개인 자료는 로그인 필요',result='로그인창 또는 내 스크랩',error='인증 실패·자료 없음 안내',store='사용자 스크랩 DB 조회',api='GET /api/mydata')
define('report-open-btn','하단 AI 리포트 화면을 열고 선택 유형의 저장 스냅샷 목록을 읽는다. 이 버튼은 AI 분석을 시작하지 않는다.',inputs='표시 설정에서 리포트 활성',result='리포트 화면·스냅샷 선택',store='조회만',api='GET /api/report/list')
define('report-snap','저장된 리포트 스냅샷 중 하나를 선택해 기간·작성 시점·본문을 조회한다.',result='선택한 리포트 상세',error='스냅샷 없으면 빈 상태; 삭제된 항목은 재조회',store='조회만',api='GET /api/report/list · /api/report/get')
define('report-pdf','현재 리포트를 인쇄용 문서로 열고 브라우저 인쇄에서 PDF로 저장한다. 보고서의 출처 링크를 유지한다.',inputs='표시된 리포트; 브라우저 인쇄 기능',result='인쇄 또는 PDF 저장 창',error='브라우저에서 사용자가 취소 가능',store='사용자 기기에 저장')
define('to-top','스크롤 위치가 내려가면 나타나며 화면 맨 위로 이동한다.',store='스크롤 위치')
define('share-url','선택한 자료의 공유 URL을 읽기 전용으로 표시한다. 복사 실패 시 직접 선택·복사가 가능하다.',store='저장하지 않음')
define('share-sms','문자 공유를 준비한다. iOS는 기본 공유창에서 메시지를 선택하고 다른 환경은 sms URI로 작성창을 연다. 수신인 선택과 전송은 사용자가 한다.',result='기기의 메시지/공유 화면',error='지원하지 않는 기기·브라우저는 URL 복사 안내',store='앱 서버에 저장하지 않음')
define('reader-theme','기사 읽기 화면의 밝은/어두운 테마를 전환한다.',store='읽기 화면 설정')
define('reader-retry','본문 추출을 다시 요청한다. 이전 실패 안내를 로딩 상태로 바꾼다.',result='본문 또는 추출 실패 안내',api='기사 읽기 API',store='추출/요약 캐시')
define('reader-source','선택한 기사의 원문 사이트를 새 창으로 연다.',result='외부 기사 원문',error='원문 삭제·로그인 요구는 해당 사이트에 따름',store='열람 상태')
# Video controls are reviewed independently; they do not call an AI.
video={
 'videos-search':'작품 제목을 검색하고 검색 결과 수·작품 목록을 갱신한다.',
 'videos-all':'전체 작품 목록 범위로 전환한다.', 'videos-saved':'현재 브라우저에 저장한 내 목록만 표시한다.',
 'videos-back':'작품 상세에서 탐색 목록으로 돌아간다. 재생 진행 상태는 브라우저 저장 경로를 따른다.',
 'videos-detail-save':'작품을 내 목록에 추가하거나 제거한다. 로그인 여부와 무관한 현재 브라우저 저장이다.',
 'videos-inspection-toggle':'회차 재생 가능 검사 작업을 중지하거나 재개한다. 실제 전체 영상 감상이 아닌 재생 경로 확인이다.',
 'videos-inspection-all':'선택한 작품의 전체 회차 검사 범위로 전환한다. 진행률과 상태를 표시한다.',
 'videos-original':'선택한 작품·시리즈·회차의 원본 사이트 이동 주소를 연다. 관리자에게만 표시한다.',
 'videos-seek':'재생 길이가 확인된 경우 슬라이더로 재생 위치를 이동한다.',
 'videos-rewind':'현재 재생 시각에서 10초 전으로 이동한다. 시작 시각 아래로 이동하지 않는다.',
 'videos-toggle-play':'현재 영상 재생/일시정지 상태를 전환한다.',
 'videos-forward':'현재 재생 시각에서 10초 뒤로 이동한다. 재생 길이 범위를 따른다.',
 'videos-airplay':'지원 기기와 브라우저에서 AirPlay 대상 선택 UI를 요청한다. 기기 연결은 OS 기능이다.',
 'videos-airplay-return':'원격 재생을 해제하고 현재 기기의 플레이어로 돌아가도록 요청한다.',
 'videos-subtitle-earlier':'자막 시각을 0.1초 빠르게 조정하고 작품별 설정을 저장한다. AirPlay에는 기기 재선택 안내가 있다.',
 'videos-subtitle-later':'자막 시각을 0.1초 늦게 조정하고 작품별 설정을 저장한다.',
 'videos-prev':'이전 회차로 선택을 이동한다. 유효 범위와 재생 확인 상태를 따른다.',
 'videos-next':'다음 회차로 선택을 이동한다. 회차가 없거나 실패하면 안내한다.',
 'videos-picker-open':'회차 선택 바텀시트/대화상자를 열고 현재 선택 회차를 표시한다.',
 'videos-picker-close':'회차 선택창을 닫고 원래 회차 선택 버튼으로 돌아간다.',
 'videos-series':'작품 안의 시리즈를 선택하고 해당 시리즈 회차 목록을 갱신한다.',
 'videos-current-page':'현재 선택한 회차가 속한 회차 구간으로 이동한다.',
 'videos-latest-page':'선택한 시리즈의 마지막 회차 구간으로 이동한다.',
 'videos-range-prev':'회차 목록의 이전 100화 구간으로 이동한다.',
 'videos-range-next':'회차 목록의 다음 100화 구간으로 이동한다.',
 'videos-range':'회차 구간을 직접 선택하고 그 범위의 회차 버튼을 표시한다.',
 'videos-jump':'1 이상의 정수 회차 번호를 입력한다. 실제 존재하는 회차인지 제출 시 검증한다.',
 'videos-jump-submit':'입력한 회차로 선택을 이동한다. 존재하지 않으면 상태 안내를 표시한다.',
 'videos-play':'선택한 회차의 재생 URL과 자막을 확보해 플레이어를 시작한다. 저장된 재생 시점이 있으면 이어보기를 준비한다.',
}
for key,desc in video.items():define(key,desc,inputs='작품/시리즈/회차·기기 지원·현재 선택 상태',result='작품 목록·회차 선택·플레이어 또는 OS 연결 상태 갱신',error='미지원·회차 미존재·재생 실패·자동재생 제한 안내',store='내 목록·진행·검사·자막 설정은 현재 브라우저',api='/api/videos/library · /catalog · /playback')
D['videos-original'][4]='관리자';D['videos-original'][-1]='GET /api/videos/original'
calc={
 'calc-salary-annual':('연봉 (만원)','연봉을 만원 단위로 입력하면 월 급여·공제·실수령액 근사치를 갱신한다. 2025년 요율과 코드의 소득세 근사를 사용하며 최신 공식 급여 정산을 보장하지 않는다.'),
 'calc-salary-family':('부양가족 수','본인 포함 1명 이상으로 입력하고 소득세 근사 공제 조건에 반영한다.'),
 'calc-salary-nontax':('월 비과세 (원)','월 비과세 금액을 원 단위로 입력해 계산 대상 급여를 조정한다.'),
 'calc-save-type':('저축 유형','매월 납입 적금 또는 목돈 거치 예금을 선택하고 금액 입력의 의미·계산식을 바꾼다.'),
 'calc-save-comp':('이자 방식','단리 또는 월복리를 선택해 이자를 계산한다.'),
 'calc-save-amount':('납입/거치금 (원)','적금은 월 납입액, 예금은 거치금액을 원 단위로 입력한다.'),
 'calc-save-rate':('연이율 (%)','0 이상 연이율을 입력해 세전·세후 이자를 계산한다.'),
 'calc-save-months':('저축 기간 (개월)','1 이상의 기간을 입력해 원금·세전 이자·15.4% 세금·세후 수령액을 갱신한다.'),
 'calc-loan-amount':('대출금 (원)','대출 원금을 입력해 월 상환액·이자 합계를 계산한다.'),
 'calc-loan-rate':('대출 연이율 (%)','연이율을 입력한다. 0%도 처리하며 월 이율로 변환한다.'),
 'calc-loan-months':('대출 기간 (개월)','1 이상의 개월 수를 입력해 상환 회차를 결정한다.'),
 'calc-loan-type':('상환 방식','원리금균등/원금균등을 선택한다. 거치기간·중도상환수수료는 계산하지 않는다.'),
}
for key,(label,desc) in calc.items():define(key,desc,inputs=label+'; 숫자 입력 또는 정해진 옵션 선택',result='입력 변경 시 브라우저에서 계산 결과 즉시 갱신',error='미입력·음수·불가능한 기간은 계산 안내/빈 결과 처리',store='서버 저장·외부 API·AI 요청 없음')
define('finance-business-number','사업자등록번호 10자리 또는 000-00-00000 형식으로 입력한다. DART 조회 번호와 구분한다.',inputs='사업자등록번호',result='제출을 위한 형식 검증',store='번호를 서버 DB에 저장하지 않음')
define('finance-business-submit','국세청 사업자 상태 API를 호출해 계속·휴업·폐업 상태와 과세 유형을 표시한다.',inputs='유효한 사업자등록번호·API 연결',result='조회 결과·기준일/연결 상태',error='형식 오류·키 미설정·등록 안 됨·API 실패 안내',store='입력 번호 DB 저장 없음',api='POST /api/finance/business-status')
define('finance-corp-code','상장사 종목코드 6자리 또는 DART 고유번호 8자리를 입력한다. 사업자등록번호 조회는 지원하지 않는다.',inputs='6/8자리 숫자 또는 빈값',store='화면 상태')
define('finance-dart-nc','(주)엔씨 공시만 보기 조건을 적용/해제하고 최근 공시 목록을 다시 조회한다.',result='대상 기업 공시 필터',store='화면 상태',api='GET /api/finance/disclosures')
define('finance-dart-submit','6자리 종목코드는 DART 고유번호로 변환한 후 최근 90일 공시를 조회한다. 빈값은 서버 기본 목록을 조회한다.',result='기업명·공시명·접수일 표',error='코드 오류·키 미설정·매핑/조회 실패 안내',store='서버 조회 캐시·화면 목록',api='GET /api/finance/disclosures')
define('finance-search','브리핑 제목·요약·출처를 한글 유사 검색으로 필터링한다. 선택한 분류 조건과 함께 적용한다.',result='브리핑 기사 목록',error='일치 결과가 없으면 빈 결과 안내',store='화면 상태')
define('app-install','공식 도메인에서 브라우저 설치 프롬프트가 준비되면 직접 설치창을 연다. iOS는 그림이 포함된 홈 화면 추가 도움말로 이동한다.',inputs='설치 가능한 브라우저·공식 도메인·미설치 상태',result='OS 설치창 또는 /hscope/install 도움말',error='미지원이면 설치 카드 숨김; 취소 후 상태 갱신; 설치 완료 시 비활성',store='OS 홈 화면/앱 등록',api='브라우저 beforeinstallprompt / navigator.install')
define('mobile-install-url','Safari에 붙여넣을 공식 설치 주소 https://hscope.onrender.com/hscope를 읽기 전용으로 표시한다.',store='저장하지 않음')
define('mobile-install-copy','공식 휴스코프 설치 주소를 복사하고 성공·실패 상태를 표시한다.',result='클립보드 또는 수동 복사 안내',error='권한/지원 실패 시 주소 선택 후 직접 복사',store='기기 클립보드')
define('maeum-password','마음기록 기획서 접근용 비밀번호를 입력한다. 앱 관리자 로그인과 별개다.',inputs='비밀번호; 서버 challenge',store='입력은 화면, 허가는 서버 세션')
define('maeum-submit','비밀번호와 challenge를 서버에 제출하고 성공하면 마음기록 기획서로 이동한다.',result='40페이지 기획서 또는 오류',error='비밀번호 불일치·challenge 오류 시 오류 메시지',store='허가 세션',api='POST /maeum-record')
# Fine-grained features created at runtime, including displays and data rules.
EXTRA=[]
def feature(screen,zone,group,name,desc,inputs='해당 기능 진입',result='화면 표시 또는 상태 갱신',error='빈 결과·실패 시 안내',access='방문자·로그인 사용자·관리자',store='화면 상태',ref='static/js/app.js',api=''):
 EXTRA.append((screen,zone,group,name,[desc,inputs,result,error,access,store,api],ref))
for screen,name,desc in [
 ('공통','사용자명·권한','로그인 상태의 표시 이름을 상단에 표시하고 관리자 전용 버튼 노출을 동기화한다. 일반 로그인과 관리자 로그인은 별개 권한이다.'),
 ('공통','읽음 표시','기사·게시물의 읽음 상태를 시각적으로 구분한다. 로그인 사용자 읽음 기록은 사용자 데이터 API로 동기화하며 저장 실패해도 현재 화면 읽음 표시는 유지할 수 있다.'),
 ('공통','고양이 로딩','첫 정지 장면을 즉시 표시하고 애니메이션 로드 후 전환한다. 캣휠 회전과 진행 문구를 함께 표시하며 동작 줄이기 설정에서는 정지 장면을 사용한다.'),
 ('공통','DB 상태 배지','푸터에 DB 확인 중·정상·오류 등 저장소 상태를 표시한다. AI 잔액 상태와 구분한다.'),
 ('공통','버전·저작권','푸터에 김상화 저작권, 현재 화면 버전과 build를 표시한다.'),
 ('공통','탭별 표시 권한','관리자의 기능 표시 설정에 따라 방문자·일반 사용자에게 탭/리포트/스크랩을 숨긴다. 관리자는 숨긴 기능도 표시한다. UI 숨김을 서버 API 권한 통제와 동일시하지 않는다.'),
 ('공통','빈 상태·연결 오류','자료 없음·검색 결과 없음·네트워크 지연·실패를 별도 텍스트로 표시한다. 재시도 제공 여부는 개별 화면에 따른다.'),
 ('공통','접근성 상태 안내','상태·건수·진행 표시에는 aria-live/role=status를 사용하고 아이콘 버튼에는 의미 있는 이름을 제공한다. 대화상자 닫기 후 관련 버튼으로 복귀한다.'),
]:feature(screen,'탑' if name=='사용자명·권한' else '푸터' if name in ['DB 상태 배지','버전·저작권'] else '바디','상태·표시',name,desc)
for screen in ['냥정보','게임정보','NC뉴스','비영리재단 동향','보안뉴스']:
 for name,desc in [
 ('목록 결과 건수','검색·분류 조건 적용 후 현재 결과 건수를 표시한다.'),
 ('리스트 보기','제목과 메타 중심의 리스트 형태로 같은 자료를 표시한다.'),
 ('카드 보기','썸네일·제목·요약·메타·행동 버튼이 있는 카드 형태로 표시한다.'),
 ('기사 제목·원문 이동','일반 뉴스 제목은 앱 리더로 열고 실제 원문 링크도 제공한다. 동향 게시판·영상 자료는 원문으로 직접 연다. 제목을 AI가 새로 생성하지 않는다.'),
 ('썸네일·대체 이미지','제공된 이미지 또는 안전한 이미지 프록시를 사용한다. 주소가 없거나 로딩 실패면 공통 대체 표시를 사용한다.'),
 ('출처·날짜·분류','저장된 출처·게시 시각·분류를 표시하며 자료 종류에 따라 표시 항목이 달라진다.'),
 ('스크랩 토글','자료를 내 스크랩에 추가/삭제한다. 비로그인이면 로그인 창으로 유도하고 성공 후 대기 동작을 이어간다. 서버 저장 실패 시 낙관적으로 바뀐 UI를 복구한다.'),
 ('공유하기','공유창에 제목과 URL을 전달한다. 복사·카카오톡·문자·다른 앱은 공통 공유 기능을 재사용한다.'),
 ('본문 읽기(앱)','선택 자료의 URL·제목을 리더에 전달하고 본문 추출과 핵심 요약 상태를 표시한다. 원문 직접 열기는 별도 동작이다.'),
 ('목록 추가 표시','목록/카드가 많을 때 화면에 필요한 항목을 추가 렌더링한다. 한 번에 전체 DOM을 만들지 않으며 끝·빈 상태를 표시한다.'),
 ]:feature(screen,'바디','콘텐츠 목록',name,desc,access='로그인 사용자·관리자' if name=='스크랩 토글' else '방문자·로그인 사용자·관리자',store='사용자 DB' if name=='스크랩 토글' else '읽음은 사용자 상태; 보기는 브라우저 설정; 목록은 조회',api='POST /api/scrap' if name=='스크랩 토글' else '')
feature('비영리재단 동향','바디','동향·게시판·영상','혼합 출처 목록','뉴스·고정 게시판·유튜브 등 자료 유형을 합쳐 표시하고 자료별 원문/본문/영상 링크를 구분한다. 동향 전체/게시판/영상 선택은 목록 필터이고 수집 버튼은 별도 관리자 작업이다.')
feature('비영리재단 동향','바디','수집 결과','출처별 상세 펼치기','일부 실패·보류 출처의 이름·확보 건수·이유·다음 재요청 가능 시각을 펼쳐 읽는다. 확인 보류는 이번 요청 생략 상태이며 오류와 구분한다.',access='관리자',store='수집 상태 조회')
feature('보안뉴스','바디','AI 분석 정보','중요도·태그·근거','분석된 기사에 중요도·기관·CVE·피해·조치 등 저장된 근거 필드를 표시한다. 미분석 기사에 사실을 새로 만들어 넣지 않는다.',store='DB 저장 분석 조회')
for name,desc in [
 ('관심 분야 선택','8종 분야를 복수 선택한다. 여러 분야는 합집합이고 각 행사에 복수 분야가 있을 수 있다.'),
 ('키워드 입력','키워드를 최대 8개, 각 40자까지 입력해 공백 정리·중복 제거 후 관심사에 추가한다.'),
 ('키워드 제거','추가된 키워드 칩의 제거 버튼으로 삭제하고 설정 상태를 갱신한다.'),
 ('설정하고 추천받기','관심사를 저장하고 명시적으로 서버 AI 추천 요청을 시작한다. 단순 탭 진입·검색·설정창 열기는 AI 호출을 하지 않는다.'),
 ('설정창 닫기','설정창을 닫고 현재 목록으로 돌아간다. 닫기 자체로 AI 추천 작업을 시작하지 않는다.'),
 ('규칙 큐레이션','이미 로드한 행사에서 종료 여부·분야·키워드 점수로 최대 12개를 즉시 추천한다. 관심사 없음이면 분야별 대표 행사를 우선한다.'),
 ('AI 큐레이션 결과','저장된 최대 60개 후보에서 AI가 유효한 후보 인덱스를 최대 8개 선택한다. 원본 일정·장소·이미지는 유지하고 이유와 순서만 반영한다.'),
 ('AI 추천 대기·중복 억제','현재 관심사/10분 구간 캐시와 프로세스 동시 2개 제한을 적용한다. pending을 1.5초 간격 최대 50회 확인하고 조건 변경 후 늦은 응답은 무시한다.'),
 ('크레딧 부족·대체 결과','잔액 부족은 기부 안내와 규칙 추천으로 대체한다. 키 미설정도 규칙 추천이며, 전체 자료 조회 실패는 별도 오류다.'),
 ('추천 배너 원문','제목·기간·장소·썸네일을 배너에 표시하고 원문 URL로 이동한다. 현재 화면에서 표시 가능한 URL만 결과에 남긴다.'),
 ('앨범 카드','포스터 중심 행사 카드에 기간·장소·원문 링크를 표시한다. 이미지 누락은 대체 표시하며 AI가 포스터를 생성하지 않는다.'),
 ('일정 리스트','일반 일정의 리스트형 자료를 표시한다. 일반 보기 설정은 뉴스 보기와 독립적으로 저장한다.'),
 ('월 이전·다음','달력을 이전/다음 달로 이동하고 해당 월의 개최 날짜·건수를 다시 표시한다.'),
 ('오늘 이동','달력의 오늘 날짜와 해당 일정으로 이동하고 선택 강조를 표시한다.'),
 ('날짜 선택','행사 날짜를 선택해 당일 목록을 표시한다. 여러 날 행사는 시작~종료일과 표시 날짜의 교집합으로 집계한다.'),
 ('선택일 목록·주간 띠','선택한 날의 행사와 주간 날짜 이동 UI를 표시한다. 월 이동·오늘 이동과 선택일 상태를 연결한다.'),
 ('일정 원문 확인 안내','뉴스 기반 날짜 오류나 일정 변경 가능성을 설명하고 참여 전 원문 확인을 안내한다.'),
]:feature('행사일정','팝업' if name in ['관심 분야 선택','키워드 입력','키워드 제거','설정하고 추천받기','설정창 닫기'] else '바디','관심사 설정' if name in ['관심 분야 선택','키워드 입력','키워드 제거','설정하고 추천받기','설정창 닫기'] else '큐레이션·캘린더',name,desc,store='관심사는 브라우저 event-interests; AI 결과는 서버 메모리 캐시; 행사 원본은 DB',ref='static/js/events-ui.js',api='POST /api/events/recommend' if name in ['설정하고 추천받기','AI 추천 대기·중복 억제'] else '')
for name,desc in [
 ('제목·원문·메타','선택 기사 제목·원문 링크·출처 정보를 리더 상단에 표시한다.'),
 ('본문 추출','저장된 원문 주소에서 읽을 수 있는 텍스트를 추출한다. 추출 제한·실패 시 원문 이동 안내를 유지한다.'),
 ('AI 핵심 요약','확보한 본문을 근거로 AI 핵심 요약을 비동기 생성한다. 1~3개 요약 포인트와 본문 캐시를 사용하며 실제 AI 호출에 토큰이 든다.'),
 ('요약 강조 구간','유효한 요약 문장 안의 짧은 핵심 구간만 강조한다. 전체 문장 강조와 겹치는 강조를 제한한다.'),
 ('잔액 부족·기부 안내','AI 크레딧 부족, 기부하면 충전한다는 문구, 계좌와 예금주를 줄바꿈해 강조한다. 본문은 아래에서 읽을 수 있다는 안내를 별도 문단으로 표시한다.'),
 ('본문 읽기 유지','AI 요약 실패·잔액 부족에도 이미 확보한 본문과 원문 이동을 계속 제공한다.'),
 ('글자 크기 조절','상단 가−/가+ 버튼으로 읽기 글자 크기를 바꾼다. 읽기 화면 설정과 본문 내용을 분리한다.'),
]:feature('기사 본문 리더','팝업','본문·요약',name,desc,store='본문·요약은 서버 캐시; 읽기 설정은 화면/브라우저',ref='static/js/reader.js')
for name,desc in [
 ('기본 위치 3곳','NC문화재단 사옥/NC 판교R&D센터/프로젝토리 성남지점의 주소·반경을 선택하고 저장된 식당을 조회한다.'),
 ('내 위치','GPS 권한을 요청하고 국내 좌표·허용 반경을 검증한다. 선택 후 저장 식당부터 조회하고 다운로드는 별도로 확인한다.'),
 ('주소 결과 선택','최대 8개 주소/장소 결과 중 하나를 선택해 GPS와 같은 이동형 주변 조회 경로에 전달한다.'),
 ('최근 위치 재사용','GPS/주소 선택 성공 기록을 최대 20개 브라우저에 저장하고 최근 순으로 표시한다. 선택 시 저장 좌표를 사용해 GPS 권한을 다시 요청하지 않는다.'),
 ('최근 위치 X 삭제','해당 브라우저의 최근 위치 기록만 지운다. 식당 DB·후기·방문을 삭제하지 않는다.'),
 ('주소 자동 보완','GPS 좌표를 Kakao 역지오코딩으로 도로명/지번 주소로 변환한다. 늦은 결과가 다른 위치나 삭제된 기록을 되살리지 않도록 비교한다.'),
 ('음식 카테고리','현재 위치의 실제 카테고리와 건수를 표시하고 한 가지 분류를 선택한다.'),
 ('검증된 곳 필터','휴스코프에 평점·리뷰가 있는 식당만 보여준다. 외부 위생·가격·안전 인증을 뜻하지 않는다.'),
 ('식당 카드','상호·음식 분류·주소·전화·거리·예상 도보·평점·리뷰 수를 보유한 범위만 표시한다. 미보유 메뉴·가격·영업시간은 만들지 않는다.'),
 ('전화','전화번호가 있으면 tel 링크를 열어 기기의 통화 화면을 요청한다. 실제 발신은 사용자가 결정한다.'),
 ('지도 상세·공유','Kakao 장소 URL을 새 창으로 열거나 공통 공유창으로 전달한다.'),
 ('숨기기·숨김해제','관리자가 식당 제외 상태를 변경한다. 사용자 기본 목록과 추천에는 제외 식당이 빠지며 후기·방문은 삭제하지 않는다.'),
 ('다운로드 진행','신규 영역 수집 동안 버튼 대신 진행 스피너·텍스트를 표시하고 상태를 폴링한다. 실패해도 기존 데이터와 영역 기록을 완료로 덮어쓰지 않는다.'),
 ('다시 시도','위치 목록/식당 조회가 실패하면 현재 선택 위치를 기준으로 다시 조회한다.'),
]:feature('맛집 목록','바디','위치·식당',name,desc,access='관리자' if name=='숨기기·숨김해제' else '방문자·로그인 사용자·관리자',store='식당/제외 상태는 DB; 최근 위치는 브라우저',api='POST /api/lunch/exclude' if name=='숨기기·숨김해제' else '')
for name,desc in [
 ('후기 목록','선택 식당의 별점·작성자·후기·시각과 집계 평점을 표시한다. 이관 예시 리뷰를 실사용자 인증으로 해석하지 않는다.'),
 ('별점 선택 1~5','후기 등록 폼에서 별점을 1~5점 중 선택한다. 선택 시각 표시와 저장은 별개다.'),
 ('후기 내용','선택 식당에 남길 후기 텍스트를 최대 300자 입력한다.'),
 ('오늘 방문 체크','후기를 등록하면서 방문 이력도 함께 남길지 선택한다. 기본 체크 상태를 제공한다.'),
 ('평점 등록','로그인 사용자가 별점·후기를 저장하고 선택하면 방문 이력도 등록한다. 저장 후 목록·평점 집계를 갱신한다.'),
 ('비로그인 안내','후기 읽기는 허용하지만 후기·방문 쓰기는 로그인하도록 안내한다.'),
]:feature('식당 평점·후기','바디','후기 등록',name,desc,access='로그인 사용자·관리자' if name in ['별점 선택 1~5','후기 내용','오늘 방문 체크','평점 등록'] else '방문자·로그인 사용자·관리자',store='후기·방문 DB',api='GET /api/lunch/reviews · POST /api/lunch/review')
for name,desc in [
 ('성향 선택 8종','안전빵/모험/월급루팡/오늘은 제대로/빨리 먹자/세계여행/숨은 맛집/오랜만이야 중 한 성향을 고른다. 가격·조리시간 실측 없이 점수 선호를 바꾼다.'),
 ('회피 음식 종류','현재 지역의 음식 카테고리를 복수 회피 대상으로 선택한다.'),
 ('기분·상황','가까운 데/새로운 곳/빨리/든든/속 편하게/위로/가볍게/얼큰/비 오는 날/혼밥/달달/느끼한 것 회피 등의 선택을 함께 점수에 반영한다. 날씨 API 확인은 없다.'),
 ('검증된 곳 우선','평점·리뷰 신뢰 비중을 높인다. 목록의 검증된 곳 필터와 달리 후보를 전부 제거하는 필터가 아닌 가중치다.'),
 ('추천 방식 안내','거리·평점·다양성·탐색·상황·방문·무작위 점수와 선택 조건의 역할을 설명하는 팝업을 연다.'),
 ('추천받기','현재 식당 ID·선택 위치·성향·기분·회피 종류를 서버에 전달한다. 서버는 상위 5개 후보에서 가중 추첨하고 대안 최대 2곳을 반환한다.'),
 ('랜덤 조건 주사위','성향 1개와 기분 1~2개를 무작위로 고른 뒤 즉시 추천한다.'),
 ('추천 로딩 슬롯','추천을 기다리는 동안 음식 슬롯 애니메이션을 표시하고 선택 음식 분류로 정지한다. 시각 효과 오류가 추천 결과를 막지 않게 한다.'),
 ('추천 결과','식당명·분류·도보·평점·태그·이유·지도·후기·대안을 표시한다. 추천 클릭 자체로 방문 기록을 저장하지 않는다.'),
 ('다시 추천','현재 조건으로 다시 추천 요청을 실행한다. 결과가 같을 수도 있고 대체 엔진은 후보 여럿이면 직전 식당을 뺀다.'),
 ('조건 바꾸기','결과 화면에서 성향·기분·회피 선택 화면으로 돌아간다.'),
 ('대안 선택','추천 대안 식당을 눌러 해당 식당 평점·후기 화면을 연다.'),
 ('5초 대체 추천','서버 실패·5초 지연·무효 후보 시 브라우저의 현재 목록에서 회피 조건을 유지한 간단한 점수 추첨으로 대체한다. 개인 최근 이력 전체를 동일 재현하지 않는다.'),
 ('조건 완화·빈 후보','서버는 최근 방문 제외, 회피 종류를 순차 완화할 수 있지만 브라우저는 회피 종류를 다시 엄격히 검증한다. 모두 회피 대상이면 조건 축소 안내를 표시한다.'),
]:feature('점심 추천','바디','추천 설정·결과',name,desc,store='선택 상태·직전 추천은 화면; 개인 이력은 DB 조회; LLM 토큰 사용 없음',api='POST /api/lunch/recommend' if name in ['추천받기','다시 추천'] else '')
for name,desc in [
 ('전체·그룹','전체 스크랩과 사용자 그룹별 자료·건수를 조회한다.'),
 ('스크랩 검색','저장한 제목·요약 등 현재 자료를 검색하고 선택 그룹 조건과 함께 적용한다.'),
 ('그룹 추가','이름을 입력해 사용자 그룹을 생성한다. 저장 실패 시 안내하고 서버 반환 그룹 목록을 반영한다.'),
 ('그룹 이름 변경','선택 그룹의 이름을 수정한다. 그룹 소속 기사 자체는 바꾸지 않는다.'),
 ('그룹 삭제','선택 그룹을 삭제한다. 스크랩 기사 자체의 삭제와 구분한다.'),
 ('기사 그룹 배정','한 스크랩의 소속 그룹을 선택해 서버에 저장한다. 다중 그룹 소속을 지원한다.'),
 ('스크랩 해제','저장 자료를 삭제하고 관련 카드·건수·배지를 갱신한다. 저장 실패 시 UI를 복구한다.'),
 ('저장 당시 자료 표시','기사 스냅샷·원문·본문 읽기·공유 기능을 제공한다. 원문이 삭제돼도 저장 스냅샷과 실제 원문 접근 가능성은 별개다.'),
 ('푸터 저장 배지','저장한 항목 수를 푸터 스크랩 메뉴 배지에 표시한다.'),
]:feature('스크랩','바디','사용자 보관함',name,desc,access='로그인 사용자·관리자',store='사용자별 그룹·스크랩 DB',api='GET /api/mydata · POST /api/groups · /api/scrap · /api/scrap/groups')
for name,desc in [
 ('재단동향 분기 본문','분기 기간의 저장 기사에서 재단 활동·동향·주요 이슈를 정리한 리포트를 표시한다.'),
 ('보안 월간 본문','전월 보안 기사와 저장 분석을 근거로 주요 위협·기관·대응·시사점을 표시한다.'),
 ('생성 메타','리포트 기준 기간·작성 시각·사용 모델 등 확보한 생성 정보를 표시한다.'),
 ('분석 진행·실패','관리자 실행 중 버튼을 잠그고 상태를 폴링한다. 완료 시 저장 스냅샷 목록과 본문을 갱신한다. AI 잔액 부족은 기부 안내를 제공한다.'),
 ('참고 기사 원문','보고서의 근거 기사 링크를 실제 원문으로 연결한다. 링크와 내용을 AI가 새 사실로 대체하지 않도록 원문 근거를 유지한다.'),
]:feature('AI 리포트','바디','리포트 내용',name,desc,access='관리자' if name=='분석 진행·실패' else '방문자·로그인 사용자·관리자(표시 설정 적용)',store='DB 스냅샷',api='GET /api/report/get · /api/report/status')
for name,desc in [
 ('기본 계정 안내','일반 사용자 기본 테스트 계정과 표시 이름을 안내한다. 명세서에는 실제 비밀번호를 기록하지 않는다.'),
 ('아이디 입력','다른 계정 모드에서 사용자 아이디를 입력한다. 관리자 모드는 비밀번호만 사용한다.'),
 ('비밀번호 입력','관리자 또는 다른 일반 계정의 인증 비밀번호를 입력한다. 성공/닫기 후 필드를 비운다.'),
 ('인증 오류','로그인 실패 이유·연결 실패 안내를 팝업 안에 표시하며 실패 상태에서 로그인 세션을 만들지 않는다.'),
]:feature('로그인','팝업','인증',name,desc,store='입력 필드는 화면; 성공 세션은 서버',api='POST /api/login')
for name,desc in [
 ('수집 로그 목록','실행 그룹·시각·결과·처리 상태 등을 조회한다. 서버 실행 기록과 브라우저 로딩 상태를 구분한다.'),
 ('접속 로그 목록','접속 시각·관련 요청 메타를 관리자 조회 영역에 표시한다. 일반 사용자에게 공개하지 않는다.'),
 ('패치 날짜·버전 접기','날짜 아래 버전을 최신순으로 표시하고 버전별 상세를 펼친다. 당시 교체/삭제된 기능도 이력으로 보존한다.'),
 ('표시 설정 저장 결과','체크를 바꾸면 즉시 서버에 저장하고 일반/방문자 노출을 갱신한다. 냥정보는 잠긴 기본 기능이며 관리자는 모두 표시한다.'),
]:feature('관리자 도구','팝업','로그·패치·표시',name,desc,access='관리자',store='표시 설정·로그 DB; 패치내역은 저장된 Markdown 읽기')
for name,desc in [
 ('경제지표 카드','ECOS 기준 금리·환율 등 구성된 지표의 값·단위·기준일·출처·변화 추이를 표시한다. 실데이터/예시/미설정/일시중단 상태를 명시한다.'),
 ('경제지표 차트','확보한 지표 시계열을 미니 차트로 표시한다. 데이터가 없으면 차트나 값이 미확보임을 표시한다.'),
 ('엔씨 주가','별도 주가 조회로 가격·변화·기준일·시계열을 표시한다. 경제지표 조회 성공과 주가 성공을 분리한다.'),
 ('지표 갱신 시각','자료를 받은 시각과 실제 지표 기준일을 구분해 표시한다.'),
 ('세무 캘린더','코드로 구성한 신고·납부 일정을 표시하고 휴일 조정 등 계산된 날짜를 안내한다. 개인별 의무나 법정 최신 일정 확정 서비스를 제공하지 않는다.'),
 ('공시 표 원문','기업명·공시명·접수일 표에서 공시 원문 링크를 연다. 결과가 없거나 키가 없으면 상태를 표시한다.'),
 ('브리핑 카드','분류·제목·요약·출처·일자를 표시하고 본문 읽기/공유/스크랩을 공통 기능으로 제공한다.'),
 ('PC 원문 전용 안내','모바일에서 원문이 메인으로 이동하는 출처는 앱 본문 버튼 대신 PC 원문 열람 안내를 표시한다.'),
 ('출처별 연결 상태','수집 출처 목록을 펼쳐 예시/실데이터/연결 준비/일시중단 상태를 확인한다.'),
 ('급여 결과','월 세전·보험/세금 공제·월 실수령액 근사 결과를 표시한다. 2025년 보험 요율·간이 추정이며 개인별 공식 세액 확정은 아니다.'),
 ('저축 결과','원금·세전 이자·일반 과세 15.4% 세금·세후 이자와 수령액을 표시한다. 우대·비과세 상품은 제외한다.'),
 ('대출 결과','원리금균등 또는 원금균등 계산의 월 납입액·총 이자·총 상환액을 표시한다. 중도상환 수수료·거치기간 제외.'),
]:feature('재무세무','바디','지표·계산·세무·브리핑',name,desc,store='API 조회는 서버 캐시; 계산은 브라우저·서버 입력 저장 없음',ref='static/js/finance.js',api='/api/finance/dashboard · /stock · /disclosures')
for name,desc in [
 ('추천 작품 히어로','탐색 첫 영역에 선택한 추천 작품·이미지·기본 정보를 표시한다. 작품 추천은 AI LLM 호출이 아니다.'),
 ('작품 카드 열기','작품 이미지·제목으로 상세 화면을 열고 카탈로그의 시리즈·회차를 조회한다.'),
 ('이어보기 레일','현재 브라우저에서 멈췄던 작품과 회차를 표시하고 이어보기 상세로 진입한다.'),
 ('내 목록 레일','저장한 작품을 가로 목록으로 표시한다. 다른 기기 계정 동기화 기능은 없다.'),
 ('추천 작품 레일','카탈로그 기반 추천 작품 목록을 가로로 표시한다.'),
 ('작품 목록 추가 로드','작품이 많으면 다음 목록을 추가 표시하고 결과 건수·끝 상태를 표시한다.'),
 ('회차 버튼','시리즈/구간 안의 회차별 버튼을 선택한다. 재생 검사 성공·실패·미확인 상태를 아이콘으로 구분한다.'),
 ('회차 검사 진행률','회차 재생 경로 확인 진행률·현재 상태와 중지/전체 검사 동작을 표시한다. 검사 실패와 작품 자체 미존재는 별개다.'),
 ('재생 원본·스트림','서버에서 허용된 원본 주소의 재생 경로를 확보하고 지원 방식으로 플레이어를 구성한다. 외부 소스 변경·접근 제한 시 재생이 실패할 수 있다.'),
 ('네이티브 플레이어','브라우저가 지원하는 video 플레이어 또는 HLS 재생을 사용한다. 기본 재생/음량/전체화면 UI는 기기의 네이티브 기능 범위다.'),
 ('시간 표시·저장','현재/전체 재생 시간을 표시하고 진행 위치를 브라우저에 저장한다. 다른 브라우저·기기와 자동 동기화하지 않는다.'),
 ('작품·회차 딥링크','URL의 video/series/episode로 작품·회차를 재개한다. 앱 프레임과 기존 루트 영상 링크의 쿼리를 유지한다.'),
 ('자막 지연 표시','현재 작품의 자막 지연 초를 표시하고 0.1초 빠르게/늦게 변경한다. AirPlay는 재선택해야 적용될 수 있다.'),
 ('재생 실패 안내','실패·차단·미지원이면 다시 불러오거나 다른 회차 선택을 안내한다. 항상 외부 영상 재생을 보장하지 않는다.'),
]:feature('영상','바디','탐색·재생',name,desc,store='내 목록·진행·검사·자막은 현재 브라우저',ref='static/js/videos.js',api='/api/videos/library · /catalog · /playback')
for name,desc in [
 ('공유 대상 제목','공유창 상단에 선택 자료의 제목을 표시하고 HTTP/HTTPS URL만 받아들인다. 자격정보가 포함된 URL은 받지 않는다.'),
 ('URL 복사','공유 URL을 클립보드에 복사한다. 실패하면 URL 필드를 선택하고 직접 복사하도록 안내한다.'),
 ('카카오톡','별도 Kakao 공유 SDK가 아니라 navigator.share의 기기 공유 목록에서 카카오톡을 사용자가 선택한다.'),
 ('다른 앱','기본 공유 시트를 열어 기기에서 사용할 수 있는 앱을 고르게 한다.'),
 ('공유 취소·중복 클릭','공유 중 버튼을 잠그고 취소는 전송 실패와 구분한다. 공유창 닫힘 후 원래 버튼으로 포커스를 돌린다.'),
 ('구 주소 정규화','과거 서비스 도메인 공유 URL을 hscope 도메인으로 바꾸고 루트 주소는 /hscope로 연결한다.'),
]:feature('공유하기','팝업','기기 공유',name,desc,inputs='HTTP/HTTPS URL·최대 200자 제목·기기 지원',error='기본 공유 미지원·권한 실패면 URL 복사 안내',store='서버 저장 없음; 복사는 기기 클립보드',ref='static/js/share.js')
for name,desc in [
 ('설치 앱 셸','설치한 앱을 모바일 폭의 세로형 화면 프레임으로 실행한다. 운영체제의 화면 회전을 모든 기기에서 강제로 막는 기능과는 다르다.'),
 ('설치 아이콘','웹 앱 manifest와 아이콘은 휴스코프 이름·아이콘과 공식 시작 주소를 사용한다. 런처 아이콘과 구분한다.'),
 ('iOS 그림 도움말','Safari 열기→공유→홈 화면에 추가→웹 앱으로 열기/추가→아이콘 실행의 4단계를 그림과 설명으로 제공한다.'),
 ('앱내 브라우저 안내','카카오톡/ChatGPT 등 앱 안에서는 Safari로 열기 또는 공식 주소 복사 후 붙여넣기를 안내한다.'),
 ('설치 상태 반영','설치 완료 또는 standalone 상태면 설치 카드/버튼 상태를 설치 완료로 바꾸고 중복 설치 요청을 막는다.'),
 ('서비스워커 범위','공식 도메인에서 서비스워커를 등록한다. 모든 뉴스·AI·외부 영상 기능의 완전 오프라인 실행을 약속하지 않는다.'),
]:feature('설치·앱 실행','바디','PWA·모바일 도움말',name,desc,store='OS 설치·브라우저 서비스워커 상태',ref='static/js/pwa-install.js')
for name,desc in [
 ('휴스코프 서비스 카드','런처에서 /hscope로 이동해 뉴스·맛집·영상·재무세무·리포트·스크랩 공통 화면을 연다.'),
 ('마음기록 서비스 카드','런처에서 /maeum-record로 이동한다. 현재 제공물은 유서/일기 서비스의 40페이지 기획서이며 실제 작성·전송 앱은 구현된 기능으로 표기하지 않는다.'),
 ('개발자 노트 원문','GitHub 운영 브랜치의 DEVNOTE.md 원문을 새 창으로 연다. 관리자 로그인 이후 팝업에서 중복 제공하지 않는다.'),
 ('기능명세서·IA','화면·영역·버튼·기능을 5단계 표로 보는 이 문서를 연다. 검색·영역·화면·권한 필터, 원문 Markdown, 인쇄를 지원한다.'),
]:feature('런처','바디','서비스·문서',name,desc,store='이동만',ref='templates/launcher.html')
for name,desc in [
 ('40페이지 순서 열람','마음기록 기획서 이미지 40페이지를 순서대로 스크롤해 읽는다. 첫 장을 우선 표시하고 나머지는 지연 로딩한다.'),
 ('페이지 크게 보기','각 기획서 페이지 이미지를 새 창으로 크게 연다. 일기 작성 폼은 아니다.'),
 ('PDF 열기','기획서 PDF 원본을 새 창으로 연다. 브라우저 PDF 뷰어 기능을 사용한다.'),
 ('PPT 다운로드','원본 기획서 PPTX를 기기에 다운로드한다.'),
 ('서비스 홈 돌아가기','기획서 하단 링크로 런처에 돌아간다.'),
]:feature('마음기록 기획서','바디','기획서 열람',name,desc,access='마음기록 비밀번호 확인 후',store='파일 조회·기기 다운로드',ref='templates/maeum_record_plan.html')
for name,desc in [
 ('소개 섹션 이동','만든 이유·주요 기능·AI 활용·실제 화면·시작하기 앵커로 이동한다.'),
 ('실제 화면 캡처','서비스 소개의 뉴스·리더·행사·캘린더·큐레이션·재단/보안 리포트·스크랩·맛집·추천·재무세무 캡처를 열람한다. 촬영 당시 버전으로 현재 기능과 차이가 있을 수 있다.'),
 ('캡처 크게 보기','각 캡처 이미지의 새 창 또는 전체 화면 링크로 크게 확인한다.'),
 ('FAQ 펼치기','행사 출처·본문과 요약 가능 여부·열람/저장/분석 차이를 접고 펼쳐 읽는다.'),
 ('휴스코프 열기','소개 시작/끝 버튼으로 운영 휴스코프 화면에 들어간다.'),
]:feature('서비스 소개','바디','소개·캡처·FAQ',name,desc,store='이동·접기 상태',ref='templates/intro.html')
feature('이용 전 안내','팝업','서비스 범위','안내 확인','개인용·비공식 서비스이며 공개 자료와 AI 결과의 오류 가능성·원문 확인·외부 인용 제한 안내를 읽고 확인 버튼으로 닫는다. 세션당 1회 표시하고 Escape 취소를 막는다.',result='안내창 닫기·기존 포커스 복귀',store='브라우저 sessionStorage: svc-notice-shown',ref='static/js/service-notice.js')
feature('행사일정','팝업','관심사 설정','추천 키워드 칩','AI 거버넌스/정보보안/생성형 AI/접근성/클라우드/개발자 칩을 눌러 관심 키워드에 추가한다. 중복·8개 제한을 검증한다.',store='브라우저 event-interests',ref='static/js/events-ui.js')
feature('행사일정','바디','캘린더','달력 펼치기·목록 크게 보기','달력 영역을 접거나 펼쳐 선택일 목록의 표시 공간을 바꾼다. 일정 데이터를 삭제하거나 다시 AI 분석하지 않는다.',ref='static/js/events-ui.js')
# The password template exists in the repository but is not used by the current route.
EXTRA=[(*x[:4], [*x[4][:4], '방문자·로그인 사용자·관리자', *x[4][5:]], x[5]) if x[0]=='마음기록 기획서' else x for x in EXTRA]
PANELS={'cat':'냥정보','game':'게임정보','news':'NC뉴스','biz':'비영리재단 동향','security':'보안뉴스','event':'행사일정'}
VIEWS={'view-collector':'뉴스 공통','view-food':'맛집 목록','view-lunch-reviews':'식당 평점·후기','view-lunch-ai':'점심 추천','view-report':'AI 리포트','view-scrap':'스크랩'}
MODALS={'login-modal':'로그인','status-modal':'수집 상태','runlog-modal':'관리자 로그','notes-modal':'관리자 패치내역','features-modal':'관리자 표시 설정','share-dialog':'공유하기','reader-view':'기사 본문 리더','lunch-address-dialog':'주소 검색','lunch-download-dialog':'맛집 다운로드 확인'}
FILES={'index':'휴스코프','launcher':'런처','videos':'영상','finance':'재무세무','intro':'서비스 소개','mobile_install':'설치 도움말','maeum_record_plan':'마음기록 기획서','service_notice':'이용 전 안내'}
SECTIONS=[
 ('런처','/','공통','서비스 선택·설치·소개·개발노트·기능명세 문서 진입'),
 ('휴스코프 공통','/hscope','탑·푸터','브랜드·인증·관리자 도구·대메뉴·버전·DB 상태'),
 ('냥정보·게임정보·NC뉴스·동향·보안','/hscope → 뉴스','바디','6개 뉴스/행사 탭 중 뉴스 5종의 분류·검색·카드·리스트'),
 ('행사일정','/hscope → 뉴스 → 행사일정','바디·팝업','일반 일정·AI 큐레이션·관심사·캘린더·앨범'),
 ('맛집 목록','/hscope → 맛집','바디·팝업','기본/GPS/주소/최근 위치·저장 식당·다운로드·필터'),
 ('후기·점심 추천','맛집 → 후기 또는 AI 추천','바디','후기/방문 쓰기·성향/기분·규칙 추천·대안'),
 ('영상','/hscope → 영상','바디·팝업','카탈로그·내 목록·이어보기·회차·검사·재생·AirPlay·자막'),
 ('재무세무','/hscope → 재무세무 beta','바디','경제지표·주가·3종 계산기·국세청 상태·DART·브리핑'),
 ('AI 리포트','/hscope → AI리포트','바디','분기 재단/월간 보안·스냅샷·원문·PDF·관리자 생성/삭제'),
 ('스크랩','/hscope → 스크랩','바디','개인 저장 자료·그룹·검색·분류·저장 해제'),
 ('공통 팝업','휴스코프 내 행동으로 진입','팝업','로그인·공유·리더·이용 전 안내·관리자 상태/로그/설정/패치'),
 ('서비스 소개','/intro','탑·바디·푸터','소개·캡처·FAQ·운영 서비스 이동'),
 ('설치 도움말','/hscope/install','탑·바디·푸터','iOS 설치 4단계 그림·공식 주소·복사'),
 ('마음기록 기획서','/maeum-record','탑·바디','현재 비밀번호 없이 기획서 40페이지·PDF·PPT·페이지 확대'),
 ('설치 앱 셸','/hscope?app=1','공통','모바일 폭 세로 프레임·쿼리 보존·휴스코프 아이콘'),
 ('기능명세서·IA','/static/docs/function-spec.html','탑·바디·푸터','5단계 표·검색/필터·원문 Markdown·인쇄'),
]
def context(t,file):
 if file=='index':
  for p in [t,*t.parents]:
   id=p.get('id','') if hasattr(p,'get') else ''
   if id in MODALS:return MODALS[id],'팝업',id
   if id.startswith('panel-'):return PANELS.get(id[6:],'뉴스 공통'),'바디',id
   if id in VIEWS:return VIEWS[id], '탑' if t.has_attr('data-tab') else '바디',id
   if id in ['footnav','bottombar']:return '공통','푸터','하단 내비게이션'
   if p.name=='header':return '공통','탑','브랜드·인증·관리자'
  return '공통','팝업' if t.find_parent('dialog') else '푸터' if 'credit-intro' in t.get('class',[]) else '공통','공통 도구'
 if file=='videos':
  return '영상','팝업' if t.find_parent('dialog') else '바디','회차 선택' if t.find_parent('dialog') else '작품 탐색·상세·재생'
 if file=='finance':
  p=t.find_parent(attrs={'data-panel':True});return '재무세무','바디',p.get('data-panel') if p else '분류 탭'
 zone='탑' if t.find_parent('header') else '푸터' if t.find_parent('footer') else '팝업' if t.find_parent('dialog') else '바디'
 return FILES[file],zone,{'intro':'소개·캡처·FAQ','launcher':'서비스·문서','mobile_install':'iOS 설치','maeum_record_plan':'기획서 열람','service_notice':'이용 전 안내'}.get(file,'화면')
def details(t,file):
 key=t.get('id','')
 form=t.find_parent('form')
 if t.name=='button' and not key and form:
  key={'finance-business-form':'finance-business-submit','finance-dart-form':'finance-dart-submit','videos-jump-form':'videos-jump-submit'}.get(form.get('id'),key)
 if key in D:return D[key].copy()
 if t.name=='button' and (key.endswith('-close') or key=='reader-close'):
  return ['현재 대화상자를 닫고 원래 화면으로 돌아간다. 닫기만으로 데이터 삭제·수집·AI 요청을 하지 않는다.','팝업이 열린 상태','팝업 닫힘','외부 닫기/기본 포커스는 각 대화상자 구현에 따름','방문자·로그인 사용자·관리자','화면 상태','']
 attr=next(((k,v) for k,v in t.attrs.items() if k.startswith('data-')),None)
 if attr:
  k,v=attr
  desc={
   'data-tab':'선택한 뉴스/행사 탭으로 전환하고 탭에 맞는 분류·자료·검색 상태를 표시한다.',
   'data-nav':'하단 대메뉴를 선택해 해당 화면으로 전환한다. 뉴스·맛집·영상·재무세무·리포트·스크랩은 같은 서비스 안의 화면이며 링크형 원문과 구분한다.',
   'data-view':'리스트/카드 보기로 바꾸고 브라우저 nvView에 저장한다. 같은 데이터의 표현만 변경한다.',
   'data-cat':'현재 탭에서 이 분류를 포함/제외한다. 전체 체크는 탭의 분류 선택을 일괄 변경한다. 검색 조건과 함께 자료를 필터링한다.',
   'data-sort':'보안뉴스를 게시일 최신순 또는 저장된 중요도순으로 정렬한다.',
   'data-emode':'일반 일정/AI 큐레이션 화면으로 전환한다. 전환 자체로 AI API를 호출하지 않는다.',
   'data-eview':'행사 일반 일정을 리스트/앨범/캘린더로 바꾼다. eventScheduleView로 뉴스 보기와 독립 저장한다.',
   'data-kind':'재단 분기/보안 월간 리포트 유형을 선택해 해당 스냅샷 목록을 읽는다.',
   'data-role':'일반 사용자/관리자 로그인 유형을 전환하고 해당 입력 필드·기본 계정 안내를 표시한다.',
   'data-log':'관리자 수집 로그/접속 로그 목록을 선택해 읽는다.',
   'data-feat':'방문자·일반 사용자에게 해당 탭/기능의 표시 여부를 즉시 저장한다. 냥정보는 기본 잠금이며 관리자는 모든 항목을 볼 수 있다.',
   'data-share-close':'공유창을 닫고 원래 공유 버튼으로 포커스를 돌린다.',
   'data-share-action':{'copy':'현재 공유 URL을 복사한다. 실패 시 주소 선택·직접 복사를 안내한다.','kakao':'기기 기본 공유창을 열어 카카오톡을 사용자가 선택하게 한다. Kakao SDK 직접 전송이 아니다.','other':'기본 공유창에서 사용 가능한 앱을 선택하도록 요청한다.'}.get(v,'기기 메시지/공유 기능을 요청한다.'),
   'data-reader-size':'기사 본문의 글자 크기를 선택 증감값으로 조절한다. 기사 내용·요약을 재생성하지 않는다.',
   'data-fintab':'지표/계산기/세무·공시/브리핑 중 재무세무 하위 화면으로 전환한다.',
   'data-category':'재무세무 브리핑을 전체/세법·보도자료/가이드/입법예고로 거른다. 검색어 조건과 함께 적용한다.',
  }.get(k)
  if desc:
   perm='관리자' if k in ['data-feat','data-log'] else '방문자·로그인 사용자·관리자'
   store='DB 설정' if k=='data-feat' else '브라우저 보기 설정' if k in ['data-view','data-eview'] else '화면 상태'
   return [desc,f'{k}={v}'+('; 잠긴 항목은 변경 불가' if t.has_attr('disabled') else ''),'선택 상태·자료/설정 표시 갱신','자료 없음·미지원 기능은 해당 영역에서 안내',perm,store,'POST /api/features' if k=='data-feat' else '']
 if t.name=='a':
  href=t.get('href','')
  if 'service.href' in href:desc='레지스트리에 등록한 서비스 카드를 연다. 휴스코프는 /hscope, 마음기록은 /maeum-record로 이동한다.'
  elif 'DEVNOTE' in href:desc='GitHub 개발자 노트 원문을 새 창으로 연다. 관리자가 아니어도 런처의 링크를 이용할 수 있다.'
  elif 'function-spec' in href:desc='5단계 IA 기능명세 표 문서를 연다. 화면·영역·권한 필터와 검색·원문/인쇄 기능을 제공한다.'
  elif '.pptx' in href:desc='기획서 원본 PPTX 파일을 다운로드한다.'
  elif '.pdf' in href:desc='기획서 PDF를 새 창의 브라우저 PDF 뷰어로 연다.'
  elif 'intro/shot' in href:desc='촬영 당시 서비스 화면 캡처 이미지를 새 창으로 크게 연다.'
  elif 'image_url' in href:desc='선택한 기획서 페이지 이미지 원본을 새 창으로 크게 연다. 40페이지 반복 링크다.'
  elif href.startswith('#'):desc='현재 페이지의 해당 섹션/서비스 영역으로 스크롤 이동한다.'
  elif 'ecos.bok' in href:desc='공식 ECOS 사이트로 이동해 경제지표 출처를 확인한다.'
  elif 'opendart' in href:desc='Open DART 사이트로 이동해 공시 출처를 확인한다.'
  elif 'filer.fss' in href:desc='전자공시 고유번호 조회 안내 링크로 이동한다. 앱 내부에서 번호 발급을 수행하지 않는다.'
  elif 'nts.go' in href:desc='화면에 지정한 국세청 공식 사이트를 새 창으로 연다. 화면의 홈택스라는 안내와 실제 nts.go.kr 링크를 구분한다.'
  elif 'intro' in href:desc='서비스 소개 페이지 /intro로 이동한다.'
  elif 'launcher' in href or href=='/':desc='서비스 런처 /로 돌아가 사용할 서비스나 문서를 선택한다.'
  elif 'index' in href or '/hscope' in href:desc='운영 휴스코프 /hscope 화면을 연다.'
  else:raise ValueError('Unreviewed link '+file+' '+href)
  return [desc,href,'목적지 페이지·원본·파일·섹션 열기','외부 사이트/기기 뷰어 지원에 따름; 실패 시 현재 자료 유지','방문자·로그인 사용자·관리자','이동/다운로드 외 서버 입력 저장 없음','']
 if t.name=='summary':return ['안내 또는 출처/FAQ 상세 내용을 접고 펼쳐 읽는다. 펼치기만으로 AI 분석을 요청하지 않는다.','해당 상세 항목','상세 본문 노출/접기','관련 자료가 없으면 안내 표시','방문자·로그인 사용자·관리자','화면 접기 상태','']
 if file=='service_notice' and t.name=='button':return ['개인용 서비스·AI 참고 정보·원문 확인 안내를 확인하고 dialog를 닫는다. Escape로 취소할 수 없고 세션당 1회 표시한다.','이용 전 안내창','안내 닫힘','세션 저장 실패 시 메모리 상태 사용','방문자·로그인 사용자·관리자','브라우저 세션 표시 기록','']
 raise ValueError('Unreviewed control '+file+' '+str(t)[:160])

def add(service,screen,zone,group,name,kind,detail,source):
 rows.append({'id':f'IA-{len(rows)+1:04d}','d1':service,'d2':screen,'d3':zone,'d4':group,'d5':name,'type':kind,'description':detail[0],'input':detail[1],'result':detail[2],'exception':detail[3],'permission':detail[4],'storage':detail[5],'source':source+(' · '+detail[6] if detail[6] else '')})
coverage=[]
for file in FILES:
 soup=BeautifulSoup((ROOT/'templates'/f'{file}.html').read_text(),'html.parser')
 for i,t in enumerate(soup.select('button,input:not([type=hidden]),select,textarea,a,summary'),1):
  screen,zone,group=context(t,file)
  label=t.get('aria-label') or (' '.join(t.stripped_strings) if t.name not in ['input','select'] else '')
  if not label and t.find_parent('label'):label=' '.join(t.find_parent('label').stripped_strings)
  if not label and t.get('id'):
   lab=soup.find('label',attrs={'for':t['id']});label=' '.join(lab.stripped_strings) if lab else ''
  label=label or t.get('placeholder') or t.get('title') or t.get('id') or t.get('data-cat') or t.get('data-feat') or '선택 옵션'
  if '{{ c }}' in label:label='서버 제공 분류 옵션 (각 분류별 반복)'
  if 'service.name' in label:label='서비스 카드 (휴스코프·마음기록 반복)'
  if '{{ page }}' in label:label='기획서 페이지 크게 보기 (1~40페이지 반복)'
  label=re.sub(r'\s+',' ',label)
  group={'indicators':'경제지표','calc':'계산기','tax':'세무·공시','news':'브리핑','하단 내비게이션':'하단 대메뉴'}.get(group,group)
  if group.startswith('panel-'):group='분류·목록·수집'
  if group.startswith('view-'):group='화면 탐색'
  if group in MODALS:group='대화상자 조작'
  detail=details(t,file)
  if any('admin-only' in p.get('class',[]) for p in [t,*t.parents] if hasattr(p,'get')) or screen.startswith('관리자') or screen=='수집 상태':detail[4]='관리자'
  if 'loggedout-only' in t.get('class',[]):detail[4]='비로그인 방문자'
  if 'loggedin-only' in t.get('class',[]):detail[4]='로그인 사용자·관리자'
  selector='#'+t['id'] if t.get('id') else ' '.join(f'[{k}="{v}"]' for k,v in t.attrs.items() if k.startswith('data-')) or f'{t.name}({i})'
  kind={'a':'링크','button':'버튼','select':'선택목록','textarea':'텍스트 입력','summary':'펼치기'}.get(t.name,'입력: '+t.get('type','text'))
  add('마음기록' if file=='maeum_record_plan' else '런처' if file=='launcher' else '휴스코프',screen,zone,group,label,kind,detail,f'templates/{file}.html · {selector}')
  coverage.append({'file':file,'selector':selector,'id':rows[-1]['id']})
  if t.name=='select':
   for opt in t.find_all('option'):
    d=detail.copy();d[0]='선택값 '+opt.get_text(' ',strip=True)+'을 해당 선택목록에 적용한다. '+detail[0];d[1]='value='+opt.get('value','')
    add(rows[-1]['d1'],screen,zone,group,'옵션: '+opt.get_text(' ',strip=True),'선택 옵션',d,f'templates/{file}.html · {selector}')

for name,desc in [
 ('주가 새로고침 버튼','엔씨 주가 카드의 새로고침 버튼으로 별도 /api/finance/stock 조회를 다시 요청한다. 경제지표·브리핑 전체를 다시 분석하지 않는다.'),
 ('지표 설명 버튼','지표의 ? 버튼을 눌러 제공된 설명을 펼치고 aria-expanded 상태를 갱신한다. 설명 데이터가 있을 때만 버튼을 표시한다.'),
]:feature('재무세무','바디','지표 카드',name,desc,store='조회/펼치기 상태',ref='static/js/finance.js')
for screen in ['냥정보','게임정보','NC뉴스','보안뉴스']:
 feature(screen,'바디','기사 묶음','같은 기사 매체별 보기','유사 제목의 같은 기사 묶음을 대표 카드로 표시하고 버튼을 눌러 매체별 기사·출처·날짜·본문/공유를 펼친다. 목록 전체와 개별 묶음 접기 상태를 구분한다.')
for name,desc in [
 ('다시 불러오기','자료 조회 실패 상태의 버튼으로 해당 탭 자료를 다시 요청한다. 수집 실행이나 AI 분석을 자동 시작하는 버튼은 아니다.'),
 ('검색 지우기','검색 결과가 없을 때 검색 지우기 버튼으로 검색어를 비우고 현재 분류 조건의 자료로 돌아간다.'),
 ('NEW 표시','구성된 기준일에 해당하는 새 자료에 새 소식 배지를 표시한다. 실제 신규 수집 시각·읽음 여부와 동일 개념은 아니다.'),
]:feature('뉴스 공통','바디','결과 상태',name,desc)
feature('AI 리포트','바디','리포트 내용','근거 펼치기','보고서의 근거 N건 요약을 눌러 연결된 참고 기사와 원문을 펼쳐 읽는다. 자료를 새로 수집하거나 AI를 재호출하지 않는다.',store='화면 접기 상태')
feature('스크랩','바디','그룹 관리','새 그룹 만들어 넣기','한 스크랩 카드에서 그룹이 없거나 새 그룹을 만들 때 이름을 입력받아 그룹 생성 후 해당 자료의 그룹 배정에 사용한다.',access='로그인 사용자·관리자',store='사용자 그룹 DB',api='POST /api/groups · /api/scrap/groups')
for key,name,desc in [
 ('safe','안전빵','신뢰 가중치 ×3, 탐색 ×0.4, 무작위 ×0.6으로 검증 선호를 반영한다.'),
 ('adventure','모험','탐색 ×2.4, 신뢰 ×0.5, 전체 방문 ×0.6으로 미방문 선호를 반영한다.'),
 ('cheap','월급루팡','분식·면요리·한식에 +18을 준다. 실제 가격을 수집하거나 보장하지 않는다.'),
 ('premium','오늘은 제대로','신뢰 ×1.7, 거리 ×0.4, 무작위 ×0.6을 적용한다. 가격/프리미엄 인증이 아니다.'),
 ('fast','빨리 먹자','거리 ×2.2와 분식·면요리·돈까스·한식 +15를 반영한다.'),
 ('world','세계여행','중식·일식·아시아음식·양식·해산물에 최근 7일 분류 여부에 따라 +25/+10, 그 외 -12를 준다.'),
 ('hidden','숨은 맛집','신뢰 ×0.6, 평점 있을 때 45×평점/5÷(1+리뷰수)를 더한다.'),
 ('comeback','오랜만이야','개인 과거 방문이지만 최근 3일 방문이 아닌 식당에 +22를 준다.'),
]:feature('점심 추천','바디','성향 선택',name+' 버튼',desc,inputs='data-persona='+key+'; 한 성향 선택',result='선택 칩 강조·추천 점수 조건 변경',store='현재 선택 상태')
# Trace literal runtime control IDs back to their reviewed functional rows.
TRACES={'관심 분야 선택':'.ed-topics input','키워드 입력':'#ed-keyword-input · #ed-keyword-form','키워드 제거':'[data-remove]','설정하고 추천받기':'#ed-recommend','설정창 닫기':'#ed-close','추천 키워드 칩':'[data-keyword]','월 이전·다음':'[data-cal=prev] · [data-cal=next]','오늘 이동':'[data-cal=today]','날짜 선택':'[data-date]','달력 펼치기·목록 크게 보기':'[data-cal=expand]','주가 새로고침 버튼':'.finance-stock-refresh','지표 설명 버튼':'.finance-help','그룹 추가':'.scrap-chip-add','그룹 이름 변경':'.grp-rename','그룹 삭제':'.grp-del','기사 그룹 배정':'.grp-assign · .grp-check','새 그룹 만들어 넣기':'.grp-new','스크랩 검색':'#scrap-search · #scrap-search-btn','추천받기':'#lunch-ai-go','랜덤 조건 주사위':'#lunch-ai-dice','조건 바꾸기':'#lunch-ai-edit','다시 추천':'#lunch-ai-retry','추천 방식 안내':'#lunch-recipe-toggle · .recipe-modal-x','별점 선택 1~5':'.lw-star','후기 내용':'#lw-comment','오늘 방문 체크':'#lw-visit','평점 등록':'.lw-submit','대안 선택':'[data-rev]','최근 위치 재사용':'[data-recent-key]','최근 위치 X 삭제':'[data-delete-recent]','주소 결과 선택':'[data-address-index]','숨기기·숨김해제':'[data-ex]','같은 기사 매체별 보기':'.accordion-toggle','근거 펼치기':'.rp-ev summary','다시 불러오기':'[data-reload]','검색 지우기':'[data-clear-search]','식당 카드':'.lunch-card','회피 음식 종류':'[data-mood=avoid:카테고리]','기분·상황':'[data-mood]','검증된 곳 우선':'[data-mood=trusted]'}
EXTRA=[(*x[:5],x[5]+(' · '+TRACES[x[3]] if x[3] in TRACES else '')) for x in EXTRA]

for screen,zone,group,name,detail,ref in EXTRA:add('런처' if screen=='런처' else '마음기록' if screen=='마음기록 기획서' else '휴스코프',screen,zone,group,name,'동적 기능·정보',detail,ref)
# Current DART and Kakao providers are traceable; no secret values are included.
COLS=[('id','IA ID'),('d1','Depth 1 · 서비스'),('d2','Depth 2 · 화면'),('d3','Depth 3 · 영역'),('d4','Depth 4 · 기능 묶음'),('d5','Depth 5 · 요소'),('type','유형'),('description','상세 기능 명세'),('input','입력·노출·실행 조건'),('result','결과·상태 변화'),('exception','예외·제한'),('permission','이용 권한'),('storage','저장·연동 범위'),('source','근거 파일·선택자·API')]
intro=f'''# 휴스코프 기능명세서 · IA 정보구조 표

기준: v{VERSION} · 2026-10-08 (KST) · 구현 근거 소스 {SOURCE[:7]}. UI 문서 추가와 버전 갱신 외 기존 동작 변경 없음.

총 {len(rows)}개 명세 행. 실제 템플릿의 버튼·입력·선택·링크·펼치기 {len(coverage)}개와 동적으로 생성되는 기능·표시 항목을 정리했다. 반복되는 기사·행사·회차·페이지는 개별 데이터 건수가 아닌 반복 UI의 기능을 기술한다.

Depth 1 서비스 → Depth 2 화면 → Depth 3 탑/바디/푸터/팝업/공통 → Depth 4 기능 묶음 → Depth 5 개별 요소. 한 행은 한 UI 요소 또는 상태/기능이다. 동일 기능의 설정창·실행 버튼·결과는 서로 다른 행으로 구분한다.

범위는 현재 런처와 연결된 운영 화면이다. 비활성 탭은 관리자 표시 설정에 따라 조건부 노출된다. 저장소에만 있고 현재 라우트에서 사용하지 않는 마음기록 비밀번호 템플릿은 운영 기능으로 포함하지 않았다. 마음기록의 일기 작성·수신인·전송 등은 기획서 내용이며 실제 구현 기능이 아니다. 재무 계산의 수치·요율은 현재 코드의 가정이고 최신 제도 확정 정보가 아니다. 기기 공유·설치·AirPlay·네이티브 플레이어는 지원 환경에서 동작한다.

문서의 화면은 비로그인/일반 로그인/관리자/설치 앱의 조건을 함께 설명한다. 표의 링크·API·권한 설명에 실제 비밀번호·키·토큰을 기록하지 않는다. 관리자 표시 숨김과 서버 권한 검사는 다른 개념이다.

## 화면 목록·진입 경로

| 화면 | 진입 경로 | 영역 | 기능 범위 |
| --- | --- | --- | --- |
'''
intro+=''.join('| '+' | '.join(item)+' |\n' for item in SECTIONS)
intro+='\n## 전체 기능명세 표\n\n'
def mdcell(v):return str(v).replace('|','\\|').replace('\n','<br>')
md=intro+'| '+' | '.join(label for _,label in COLS)+' |\n'+'| '+' | '.join('---' for _ in COLS)+' |\n'
md+=''.join('| '+' | '.join(mdcell(row[k]) for k,_ in COLS)+' |\n' for row in rows)
md+='\n## 갱신·확인 기준\n\n운영 화면 요소를 변경하면 `scripts/build_function_spec.py`의 설명·매핑을 수정하고 같은 버전으로 재생성한다. `tests/test_function_spec.py`는 실제 템플릿 조작 요소의 누락, 명세 행 ID, 생성 결과, 런처 링크, 화면별 범위를 확인한다. 실제 외부 API 연결 성공 여부와 OS 공유 대상 목록은 이 명세의 정적 목록과 별도로 확인한다.\n'
(ROOT/'static/docs/function-spec.md').write_text(md)
e=html.escape
heads=''.join(f'<th scope="col">{e(label)}</th>' for _,label in COLS)
trs=''.join('<tr data-screen="'+e(row['d2'])+'" data-zone="'+e(row['d3'])+'" data-permission="'+e(row['permission'])+'">'+''.join('<td'+(' class="spec-detail"' if k in ['description','input','result','exception'] else '')+'>'+e(row[k])+'</td>' for k,_ in COLS)+'</tr>' for row in rows)
screenrows=''.join('<tr>'+''.join('<td>'+e(v)+'</td>' for v in item)+'</tr>' for item in SECTIONS)
options=lambda values:''.join(f'<option value="{e(v)}">{e(v)}</option>' for v in sorted(set(values)))
page='''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>휴스코프 기능명세서 · IA</title><meta name="description" content="화면·영역·버튼·기능별 상세 정보구조와 기능명세 표"><style>
*{box-sizing:border-box}body{margin:0;background:#f5f7fc;color:#1b2841;font:14px/1.65 system-ui,-apple-system,sans-serif}header,main,footer{width:min(100% - 40px,1520px);margin:auto}header{padding:24px 0;display:flex;gap:10px;justify-content:space-between;align-items:center;flex-wrap:wrap}a{color:#225cd7;text-underline-offset:3px}header a,.actions a,.actions button{padding:10px 14px;border:1px solid #ccd5e6;background:white;border-radius:10px;color:#254a91;font:inherit;text-decoration:none;cursor:pointer}h1{font-size:clamp(25px,4vw,38px);letter-spacing:-1px;line-height:1.3;margin:4px 0 16px}h2{font-size:21px}.eyebrow{color:#6748c5;font-weight:750;letter-spacing:1px}p{max-width:1100px}.lead{font-size:16px;color:#475977}.meta{display:flex;gap:8px;flex-wrap:wrap}.meta span{padding:5px 12px;background:#e8edfa;border-radius:30px;font-weight:650}.box{background:#fff;border:1px solid #dce3f0;border-radius:16px;padding:22px;margin:22px 0}.actions{display:flex;gap:8px;flex-wrap:wrap}.filters{display:grid;grid-template-columns:2fr 1fr 1fr 1fr;gap:12px;margin-bottom:16px}label{display:block;font-size:12px;font-weight:700}input,select{display:block;width:100%;min-height:44px;margin-top:5px;padding:9px 12px;border:1px solid #bac7dd;border-radius:8px;font:inherit;background:white;color:inherit}.table-wrap{overflow:auto;border:1px solid #d6dfef;border-radius:10px;max-height:72vh;scrollbar-gutter:stable}table{border-collapse:separate;border-spacing:0;width:100%;font-size:12px}#spec-table{min-width:2800px}th,td{padding:12px;vertical-align:top;text-align:left;border-bottom:1px solid #e1e7f0;border-right:1px solid #e8edf5;min-width:120px}thead th{position:sticky;top:0;background:#eaf0fc;color:#1c3770;z-index:2;font-size:12px}td.spec-detail{min-width:230px;max-width:420px}td:nth-child(8){min-width:380px}#spec-table th:first-child,#spec-table td:first-child{position:sticky;left:0;min-width:85px;background:#f5f8ff;z-index:1;font-weight:700}#spec-table th:first-child{z-index:3}tbody tr:nth-child(even){background:#f9fbff}tr[hidden]{display:none}.screen-table{min-width:800px}footer{padding:28px 0;color:#65758e;font-size:12px}:focus-visible{outline:3px solid #4c87f6;outline-offset:3px}.empty{padding:20px;color:#87472a}.hint{font-size:12px;color:#5e708b}@media(max-width:760px){header,main,footer{width:calc(100% - 24px)}.box{padding:15px}.filters{grid-template-columns:1fr 1fr}.filters label:first-child{grid-column:1/-1}.table-wrap{max-height:70vh}header{padding:16px 0}}@media print{@page{size:A3 landscape;margin:12mm}body{background:white;font-size:10px}header,main,footer{width:100%}.filters,.actions,header nav,.hint{display:none}.box{padding:8px;margin:10px 0;break-inside:auto}.table-wrap{overflow:visible;max-height:none;border:0}#spec-table{min-width:0;width:100%;font-size:7px}th,td,td.spec-detail,td:nth-child(8){min-width:0!important;padding:4px}thead th,#spec-table th:first-child,#spec-table td:first-child{position:static}thead{display:table-header-group}tr{break-inside:avoid}}
</style></head><body><header><a href="https://hscope.onrender.com/">← 서비스 런처</a><nav><a href="https://hscope.onrender.com/hscope">휴스코프 열기</a></nav></header><main><p class="eyebrow">FUNCTION SPECIFICATION · INFORMATION ARCHITECTURE</p><h1>휴스코프 기능명세서 · IA</h1><p class="lead">화면에서 보이는 요소와 기능을 5단계 정보구조로 정리한 상세 표입니다.</p>'''
page+=f'<div class="meta"><span>v{VERSION} · 2026-10-08</span><span>{len(rows)}개 명세 행</span><span>{len(coverage)}개 템플릿 조작 요소</span><span>Depth 1–5</span></div>'
page+='''<section class="box"><h2>표 읽는 방법과 범위</h2><p><b>서비스 → 화면 → 영역 → 기능 묶음 → 개별 요소</b> 순서로 읽습니다. 탑·바디·푸터·팝업과 화면 상태, 동적 버튼·반복 카드·기기 기능을 함께 정리했습니다. 한 행은 하나의 조작 요소 또는 표시/상태 기능입니다.</p><p>방문자·로그인 사용자·관리자·설치 앱의 조건부 기능을 포함합니다. 반복 기사·행사·회차·40페이지 이미지는 데이터 건수 대신 반복 UI의 기능으로 기술합니다. 마음기록은 현재 기획서 열람이며 일기 작성·수신인·전송 기능이 구현된 앱은 아닙니다. 저장소의 미사용 비밀번호 템플릿은 운영 기능에 포함하지 않습니다.</p><p>재무 계산은 코드에 명시된 요율·근사 가정을 사용합니다. 외부 연결·공유·설치·AirPlay는 기기와 브라우저 지원에 따릅니다. 관리자 화면 숨김과 서버 API 권한 검사는 구분합니다.</p><div class="actions"><a href="function-spec.md" download="hscope-function-spec-IA.md">표 원문 다운로드 (.md)</a><a href="'''+REPO+'''claude/quirky-euler-agfmp/static/docs/function-spec.md" target="_blank" rel="noopener noreferrer">GitHub 원문 ↗</a><button type="button" id="spec-print">현재 표 인쇄 / PDF 저장</button></div></section>'''
page+='<section class="box"><h2>화면 목록·진입 경로</h2><div class="table-wrap"><table class="screen-table"><caption class="hint">현재 운영 화면과 문서의 진입 위치</caption><thead><tr>'+''.join('<th scope="col">'+e(v)+'</th>' for v in ['화면','진입 경로','영역','기능 범위'])+'</tr></thead><tbody>'+screenrows+'</tbody></table></div></section>'
page+='<section class="box"><h2>전체 기능명세 표</h2><div class="filters"><label>내용 검색<input id="spec-search" type="search" placeholder="화면, 버튼명, 기능, 예외, API…"></label><label>화면<select id="spec-screen"><option value="">전체 화면</option>'+options(r['d2'] for r in rows)+'</select></label><label>영역<select id="spec-zone"><option value="">전체 영역</option>'+options(r['d3'] for r in rows)+'</select></label><label>권한<select id="spec-permission"><option value="">전체 권한</option><option value="관리자">관리자 포함</option><option value="로그인 사용자">로그인 사용자 포함</option><option value="방문자">방문자 포함</option></select></label></div><p id="spec-count" role="status" aria-live="polite">전체 '+str(len(rows))+'개 항목</p><p class="hint">표를 가로로 스크롤하면 상세 동작·조건·예외·권한·저장 범위·근거를 읽을 수 있습니다. IA ID와 열 제목은 스크롤 중에도 유지됩니다. 인쇄는 현재 필터로 보이는 행을 A3 가로 형식으로 저장합니다.</p><div class="table-wrap" tabindex="0" aria-label="전체 기능명세 표, 가로로 스크롤 가능"><table id="spec-table"><caption class="hint">5단계 IA와 상세 기능 명세</caption><thead><tr>'+heads+'</tr></thead><tbody>'+trs+'</tbody></table></div><p class="empty" id="spec-empty" hidden>조건에 맞는 항목이 없습니다. 검색어나 필터를 줄여 주세요.</p></section>'
page+='<section class="box"><h2>명세 갱신 기준</h2><p>실제 화면과 코드에서 확인한 기능을 기준으로 작성했습니다. 구현 근거 스냅샷은 <a href="'+REPO+SOURCE+'/app.py" target="_blank" rel="noopener noreferrer">'+SOURCE[:7]+'</a>입니다. 이 문서·런처 링크와 버전 갱신 외 기존 기능은 변경하지 않았습니다.</p><p>화면 또는 동작 변경 시 생성 스크립트의 설명과 표를 함께 갱신합니다. 문서에는 실제 비밀번호·API 키·Cron 인증 토큰을 넣지 않습니다. 외부 자료의 접속 성공과 OS 지원 여부는 실행 환경에서 별도 확인합니다.</p></section></main><footer>© 2026 김상화 · 휴스코프 기능명세서 / IA · v'+VERSION+'</footer><script>"use strict";(()=>{const controls=["spec-search","spec-screen","spec-zone","spec-permission"].map(id=>document.getElementById(id));const rows=[...document.querySelectorAll("#spec-table tbody tr")].map(el=>({el,text:el.textContent.toLocaleLowerCase()}));function filter(){const [q,s,z,p]=controls.map(c=>c.value.trim());const words=q.toLocaleLowerCase().split(/\\s+/).filter(Boolean);let n=0;for(const r of rows){const show=(!s||r.el.dataset.screen===s)&&(!z||r.el.dataset.zone===z)&&(!p||r.el.dataset.permission.includes(p))&&words.every(w=>r.text.includes(w));r.el.hidden=!show;if(show)n++;}document.getElementById("spec-count").textContent=`${rows.length}개 중 ${n}개 표시`;document.getElementById("spec-empty").hidden=n>0;}controls.forEach(c=>c.addEventListener(c.type==="search"?"input":"change",filter));document.getElementById("spec-print").addEventListener("click",()=>window.print());filter();})();</script></body></html>'
(ROOT/'static/docs/function-spec.html').write_text(page)
(ROOT/'static/docs/function-spec-coverage.json').write_text(json.dumps({'version':VERSION,'source':SOURCE,'row_count':len(rows),'template_controls':coverage,'rows':rows},ensure_ascii=False,indent=2))
print(f'{len(rows)} rows; {len(coverage)} template controls; {len(EXTRA)} runtime/display features')
