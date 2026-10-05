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
        'description': '일기처럼 쓰는 유서 서비스의 원본 PPT 기획서. ChatGPT 로그인 후 열 수 있어요.',
        'href': 'https://chatgpt.com/api/library/files/libfile_2c400f821cd08191b58d442523575be3/download',
        'icon': 'heart',
        'kind': 'document',
        'new_tab': True,
        'badge': '기획서',
        'note': 'ChatGPT 로그인 필요',
        'tags': (),
    },
)
