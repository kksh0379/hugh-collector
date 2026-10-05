"""Launcher entries. Add a service here after registering its own page/blueprint."""
SERVICES = (
    {
        'id': 'hscope',
        'name': '휴스코프',
        'description': '관심 소식을 모으고, 일상에 필요한 콘텐츠를 골라보세요.',
        'href': '/hscope',
        'icon': 'scope',
        'tags': ('뉴스·동향', '맛집', '영상', '재무세무', 'AI 리포트'),
    },
    {
        'id': 'maeum-record',
        'name': '마음기록',
        'description': '일기처럼 쓰는 유서 서비스의 40페이지 기획서. 기획서 바로 보기와 원본 PPT 다운로드.',
        'href': '/maeum-record',
        'icon': 'heart',
        'kind': 'document',
        'new_tab': False,
        'badge': '기획서',
        'note': '기획서 보기 · PPT 다운로드',
        'tags': (),
    },
)
