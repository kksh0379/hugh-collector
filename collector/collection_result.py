"""수집 결과의 완전성. 빈/부분 응답으로 기존 자료를 지우지 않도록 전달한다."""
class CollectionItems(list):
    def __init__(self, items=(), *, complete=True, warnings=()):
        super().__init__(items)
        self.complete = complete
        self.warnings = list(warnings)
