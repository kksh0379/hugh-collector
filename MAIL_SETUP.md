# 휴스코프 일일 메일 발송 설정 (v3.188)

## 구성
- `collector/mailer.py`: Resend HTTPS API 메일 전송 및 반응형 HTML 테스트 메일
- `/api/admin/mail/status`: 관리자 세션에서만 메일 설정 여부 조회 (주소·API 키 미노출)
- `/api/admin/mail/test`: 관리자 세션에서만 설정된 수신자에게 테스트 발송
- 관리자 도구 → **메일 발송 테스트**: 발송 전 확인 후 상태 안내
- `scripts/daily_mail.py`: 추후 Render Cron Job 실행 진입점. **현재 자동발송 금지**, 본문 기획 완료 후 활성화 및 콘텐츠 생성기 연결 필요

## Render hscope 환경변수 (비밀 값은 저장소에 커밋하지 말 것)
- `RESEND_API_KEY`: Resend API 토큰
- `MAIL_FROM`: 인증된 발신 도메인의 주소 (예: `digest@your-verified-domain.example`)
- `MAIL_RECIPIENTS`: 쉼표로 구분한 테스트 수신 주소(최대 5개)
- `MAIL_DAILY_ENABLED=false`: 이메일 콘텐츠 확정 전에는 유지

## 연결 테스트
1. Resend에서 발신 도메인 DNS(SPF/DKIM 등) 인증을 완료한다.
2. Render hscope 웹 서비스 환경변수에 발신·수신 정보를 저장하고 재배포한다.
3. 관리자 계정 로그인 → 관리자 도구 → **메일 발송 테스트** 클릭 후 확인한다.
4. Resend의 접수 성공은 수신함 도착을 보장하지 않는다. 수신함·스팸함과 발송 공급자 로그를 함께 점검한다.

## 일일 자동 발송 활성화 전 선행 작업
- 요약 자료와 제목·본문 템플릿 기획 및 승인
- 수신자와 발송 시각(KST), 수신 거부 등 필요 정책 확정
- 중복 발송 방지·발송 결과 기록·실패 시 재시도 및 모니터링
- Render Cron Job 생성, 스케줄 설정, 환경변수 연결
- 기존 `scripts/daily_mail.py`에 실제 콘텐츠 생성 및 발송 로직 연계

의도적으로 현재 Cron Job은 생성하지 않았으며 예약 발송도 비활성화되어 있습니다.
