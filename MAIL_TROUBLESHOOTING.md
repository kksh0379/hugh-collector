# 관리자 메일 테스트 오류 확인

관리자 로그인 후 기존 메일 테스트 버튼을 한 번 누릅니다. 임의 수신자는 입력할 수 없으며,
Render에 등록된 MAIL_FROM / MAIL_RECIPIENTS를 그대로 사용합니다. 자동 재시도는 하지 않습니다.
HTTP 502 응답의 provider_status는 실제 Resend HTTP 상태이며, provider_code와 error에는
허용된 오류 코드와 한국어 요약만 표시됩니다. 원본 응답, 키, 계정 이메일은 기록하지 않습니다.
서버 로그의 `Admin mail test failed`에도 동일한 안전한 요약을 남깁니다.

## 403 validation_error

- “테스트 발신은 Resend 계정 이메일로만” 안내가 나오면 onboarding@resend.dev의 수신자 제한입니다.
  현재 수신자와 **해당 API 키가 속한 Resend 계정 이메일**이 같은지 확인합니다.
  Render/GitHub 계정 이메일만으로 Resend 계정 이메일을 추정하지 않습니다.
- 계정 이메일로 테스트하려면 사용자가 수신자 변경을 명시적으로 승인한 후에만 설정을 바꿉니다.
  원래 수신자를 기록하고, 한 번 발송하여 accepted/provider_id를 확인한 후 승인된 설정으로 복원합니다.
- 현재 수신자에게 보내려면 DNS를 관리할 수 있는 소유 도메인을 Resend에 추가하고 인증합니다.
  인증 완료 후 사용자가 승인한 해당 도메인의 발신 주소를 MAIL_FROM으로 지정합니다.
  onrender.com 서비스 주소만으로 발신 도메인 소유권이 생기지는 않습니다.

## 키 권한과 도메인

Resend API Keys에서 키가 활성 상태이며 이메일 발송 권한이 있는지 확인합니다.
Sending access로 발송할 수 있습니다. 도메인/API 키 목록 조회를 위해 Full access로 확대할 필요는 없습니다.
키에 도메인 제한이 있으면 MAIL_FROM의 도메인과 일치하는지 확인합니다.
Domains에서 발신 도메인이 verified인지 확인합니다.
키 값을 채팅, 화면 캡처, 로그에 붙여 넣지 않습니다.

설정 변경 시 Render에서 적용 배포가 완료된 후 한 번만 테스트합니다.
accepted는 공급자의 접수 완료를 뜻하며 실제 수신함 도착을 보장하지 않습니다.
Resend 이벤트의 delivered 또는 수신자의 실제 수신을 별도로 확인합니다.

## 확인 범위

이 변경은 오류 관찰을 개선하며 Resend의 수신자/도메인/키 제한을 우회하지 않습니다.
기존 오류 본문이 폐기된 과거 로그만으로 세부 원인을 확정할 수 없습니다.
알 수 없는 코드나 HTML, 손상된 JSON, 8 KiB 초과 본문은 일반 안내로 대체합니다.

공식 문서:
- https://resend.com/docs/api-reference/errors
- https://resend.com/docs/dashboard/api-keys/introduction
