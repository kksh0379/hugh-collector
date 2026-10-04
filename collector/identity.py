"""Account identifiers stay stable; public authorship uses display names."""
USER_ALIASES = {"tester1": "test1"}
DISPLAY_NAMES = {"admin": "관리자", "test1": "김테스터"}


def canonical_user(username):
    return USER_ALIASES.get(username, username)


def display_name(username):
    return DISPLAY_NAMES.get(canonical_user(username), username or "익명")


def public_author(row):
    return dict(row, display_name=display_name(row.get("username")))
