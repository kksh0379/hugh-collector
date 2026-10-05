"""수집 결과의 완전성. 빈/부분 응답으로 기존 자료를 지우지 않도록 전달한다."""
class CollectionItems(list):
    def __init__(self, items=(), *, complete=True, warnings=(), sources=()):
        super().__init__(items)
        self.complete = complete
        self.warnings = list(warnings)
        self.sources = list(sources)


class CollectionFailure(RuntimeError):
    """사용자에게 공개 가능한 오류만 보관. 요청 URL·인증키는 결과에 넣지 않는다."""
    def __init__(self, reason, *, stop_search=False):
        super().__init__(reason)
        self.stop_search = stop_search


def failure_reason(error):
    if isinstance(error, CollectionFailure):
        return str(error)
    response = getattr(error, "response", None)
    status = getattr(response, "status_code", None)
    if status:
        return {403: "접근 거부 (HTTP 403)", 429: "요청 한도 초과 (HTTP 429)"}.get(status, f"출처 응답 오류 (HTTP {status})")
    kind = type(error).__name__
    if "Timeout" in kind:
        return "출처 응답 시간 초과"
    if "SSL" in kind:
        return "출처 인증서 연결 오류"
    if "Connection" in kind:
        return "출처 연결 실패"
    return "출처 응답을 해석하지 못했어요"


def summarize_failures(sources):
    failed = [s for s in sources if s["status"] in ("failed", "deferred")]
    if not failed:
        return []
    reasons = list(dict.fromkeys(s["reason"] for s in failed))
    return [f"{len(failed)}개 출처 미완료 · " + " · ".join(reasons)]
