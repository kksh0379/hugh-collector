# 휴스코프 Gmail 발신 연결

발신: kksh0378@gmail.com / 수신: kksh0378@ncfoundation.or.kr
도메인이나 수신자 인증 없이 Gmail API로 발송합니다. 기존 Resend 설정은 삭제하지 않아도 됩니다.

## 1. Google Cloud 설정 (계정 소유자가 진행)

1. https://console.cloud.google.com/ 에 발신 Gmail로 로그인하고 프로젝트를 만듭니다.
2. API 및 서비스 > 라이브러리에서 Gmail API를 사용 설정합니다.
3. Google Auth Platform에서 앱 이름(휴스코프 메일), 지원/연락 이메일을 설정합니다.
4. Audience는 External로 설정하고, Testing 단계에서는 발신 Gmail을 Test users에 추가합니다.
5. Data Access에는 https://www.googleapis.com/auth/gmail.send 만 추가합니다.
6. Clients에서 OAuth 클라이언트(Web application)를 만듭니다.
7. Authorized redirect URIs에 https://developers.google.com/oauthplayground 를 정확히 등록합니다.

## 2. Google 공식 Playground에서 승인

1. https://developers.google.com/oauthplayground/ 를 엽니다.
2. 톱니바퀴 설정에서 Use your own OAuth credentials를 켭니다.
3. 위 클라이언트의 Client ID / Client secret을 입력합니다. endpoints는 Google,
   Access type은 Offline, Force prompt는 Consent Screen을 사용합니다.
4. Step 1 범위에 https://www.googleapis.com/auth/gmail.send 를 입력하고 Authorize APIs를 누릅니다.
5. 반드시 kksh0378@gmail.com을 선택하고 발송 권한을 직접 승인합니다.
6. Step 2에서 Exchange authorization code for tokens를 눌러 Refresh token을 받습니다.
7. 토큰·client secret·자격증명 포함 링크를 채팅이나 저장소에 공유하지 않습니다.

Playground 기본 클라이언트 토큰은 24시간 후 취소되므로 반드시 본인 클라이언트를 사용합니다.
External + Testing 상태의 Gmail 권한 refresh token은 7일 후 만료됩니다.
계속 운영하려면 Google의 게시/검증 요구사항을 확인해 In production 상태로 전환하고,
그 상태에서 다시 승인하여 새 refresh token을 발급받습니다. 게시만으로 기존 토큰이 연장되지는 않습니다.
개인 사용 예외가 적용되더라도 Google 계정에 표시되는 경고와 요구사항을 확인합니다.

## 3. Render 환경변수

https://dashboard.render.com/web/srv-dauqmap7lnhs739ilqmg/env 에서 아래를 저장하고 배포합니다.

| 키 | 값 |
|---|---|
| MAIL_PROVIDER | gmail |
| MAIL_FROM | kksh0378@gmail.com |
| MAIL_RECIPIENTS | kksh0378@ncfoundation.or.kr |
| GMAIL_CLIENT_ID | 위 클라이언트 ID |
| GMAIL_CLIENT_SECRET | 위 클라이언트 secret |
| GMAIL_REFRESH_TOKEN | 위 Refresh token (Access token 아님) |

MAIL_DAILY_ENABLED는 이번 연결 테스트에서 변경하지 않습니다.
발신 주소만 바꾸고 MAIL_PROVIDER를 Resend로 남겨두면 Gmail 발송으로 전환되지 않습니다.

## 4. 검증

배포 live 이후 관리자 메일 테스트를 한 번 실행합니다.
accepted와 provider_id는 Gmail 접수 확인이며, 수신함 도착은 별도로 확인합니다.
인증 실패 시 원문·토큰 없이 gmail_oauth_error, 발송 거부 시 gmail_send_error를 표시합니다.
메일 요청을 자동 재시도하지 않습니다. 연결이 끊긴 경우 계정 승인을 다시 진행합니다.

공식 문서:
- https://developers.google.com/workspace/gmail/api/guides/sending
- https://developers.google.com/identity/protocols/oauth2#expiration
- https://developers.google.com/oauthplayground/
