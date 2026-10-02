"""User-provided 2026 lunch history; synthetic ratings are explicitly labelled."""
import hashlib
import re
from collections import defaultdict

AUTHOR = '방문기록 · 예시 리뷰'
KEY = 'lunch_history_20261002_v1'
ALIASES = {'어고집밥':'이물비 어고집밥', '청년밥상':'청년밥상문간 슬로우점',
           '서브웨이':'써브웨이 대학로점', '도도야':'도도야 혜화본점',
           '그리너':'그리너 서울혜화점', '국수가':'국수가 대학로본점',
           '순대실록':'순대실록 대학로본점', '소바의 온도':'소바의온도 본점'}
# Ambiguous March dates remain week labels, never invented visit dates.
RAW = '''
01-02|이화김치찌개|GDa23E8M
01-05|어고집밥|5bVsYOf2
01-06|제로밥상|
01-07|성북동집|FvEg5xbE
01-08|버거파크|FG7xn2E5
01-09|순대실록|5tJtlayi
01-12|하이콴|5eZtkRRw
01-13|아비꼬|5r95rVya
01-14|콩나물장수|5WOkVWrU
01-15|메종 아카이|GV2t5tSR
01-16|엄마손돼지불백|5xnueN7H
01-19|코야코|IDB1o7IR
01-20|한촌설렁탕|x0UEDBC4
01-27|청년밥상|xa52DUZv
01-28|서래향|FdCxyTgr
01-29|서브웨이|
01-30|국수가|5WOQeGyP
02-03|혜화칼국수|GvcQXu09
02-04|또보겠지떡볶이|xKtnSaqh
02-05|파파이스|GwSU6LdU
02-06|서브웨이|xxY2SWkP
02-09|혜화도담|FY3yD5E3
02-10|아비꼬|5r95rVya
02-11|콩나물장수|5WOkVWrU
02-12|풍성뚝배기|xOxXxaAt
02-19|돈텐동식당|xhzCEykg
02-20|가마솥순대국밥 대학로점|FMTckUra
02-23|버거파크|FG7xn2E5
02-24|이화김치찌개|GDa23E8M
02-27|청화원 대학로점|FsRsuBSq
03-03|미락분식|
03-04|포카치아 샌드위치 날에|FUhCxq8S
03-05|충무칼국수|G0DXhvJy
03-06|혜화동 베이커리|
3월 2주|롤링 파스타|
3월 2주|삼삼뼈국|
3월 2주|도도야|
3월 2주|프레퍼스|
3월 3주|엄마손돼지불백|
3월 3주|겐로쿠우동|
3월 3주|카산도|
3월 3주|그리너|
03-23|슬램버거|5M5N5UNE
03-24|긴자료코|Fn6AoVWh
03-25|순대실록|5tJtlayi
03-26|국수가|5WOQeGyP
03-27|서래향|FdCxyTgr
03-30|제순식당|IGJIE6fg
03-31|콩나물장수|
04-01|삼청동수제비|
04-02|프레퍼스|
04-03|성북동누룽지백숙|
04-06|침스버거|FxFtbQy8
04-07|스모키트레인|
04-08|신선식탁|
04-09|콩나물장수|5WOkVWrU
04-10|바오쯔|
04-13|혜화 골목냉면|55rw4oPt
04-14|시올돈 성북직영점|GQ1E4Y5n
04-15|백소정|5D8Iniu5
04-16|지미존스|
04-17|신선식탁|
04-20|커피내리는분식|FHl0WyBl
04-21|미스사이공|Grma0zgO
04-22|청년밥상|xa52DUZv
04-23|순대실록|5tJtlayi
04-27|도도야|
04-28|혜화동버거|
04-29|진아춘|
04-30|육전국밥|
05-04|어고집밥|
05-06|소바의 온도|
05-07|이화동 개성만두|GctJazk1
05-08|에그 놀 씨어터 대학로|
05-11|바오쯔|
05-12|낙산어전|
05-13|육전국밥|
05-14|재즈스파이스|
05-15|죽이야기|
05-18|버거파크|FG7xn2E5
05-19|서래향|FdCxyTgr
05-20|국수가|5WOQeGyP
05-21|이화김치찌개|GDa23E8M
05-22|광산포차|xAA4CAhM
06-15|순대실록|5tJtlayi
06-17|국수가|5WOQeGyP
06-18|이화동 개성만두|GctJazk1
06-19|서래향|FdCxyTgr
07-13|순대실록|5tJtlayi
07-14|이화김치찌개|GDa23E8M
07-15|마당너른집|G8s9IPDP
07-16|엄마손돼지불백|5xnueN7H
'''

def normalized(name):
    return re.sub(r'[\s·()]+', '', name).lower()

def grouped():
    out = defaultdict(list)
    for line in RAW.strip().splitlines():
        date, name, link = line.split('|')
        out[name].append((date, 'https://naver.me/' + link if link else ''))
    return out

def import_history(conn, q, now):
    locations = [dict(r) for r in conn.execute('SELECT * FROM lunch_location').fetchall()]
    locations = [r for r in locations if '이화장길100' in normalized(r.get('address') or '')]
    if len(locations) != 1:
        raise ValueError('점심 기록 대상 위치를 단일하게 확인할 수 없음')
    loc_id = locations[0]['id']
    # The unique marker is acquired in the same transaction as all inserts.
    claimed = conn.execute(q('INSERT INTO meta (key,value) VALUES (?,?) ON CONFLICT (key) DO NOTHING RETURNING key'), (KEY, now)).fetchone()
    if not claimed:
        return 0
    rows = [dict(r) for r in conn.execute(q('SELECT * FROM lunch_restaurant WHERE loc_id=?'), (loc_id,)).fetchall()]
    for name, records in grouped().items():
        target = normalized(ALIASES.get(name, name))
        targets = {normalized(name), target}
        matches = [r for r in rows if normalized(r['name']) in targets]
        if not matches:
            # Only a unique branch-qualified name is accepted; no arbitrary fuzzy match.
            branches = {t+s for t in targets for s in ('대학로점','혜화점','대학로','혜화','대학로본점','혜화본점','본점')}
            matches = [r for r in rows if normalized(r['name']) in branches]
        if len(matches) > 1:
            raise ValueError('중복 식당 확인 필요: ' + name)
        if matches:
            rid = matches[0]['id']
        else:
            link = next((url for _, url in records if url), '')
            row = conn.execute(q('INSERT INTO lunch_restaurant (loc_id,source,place_id,name,cat_norm,place_url,excluded,first_seen,last_checked) VALUES (?,?,?,?,?,?,0,?,?) RETURNING id'),
                               (loc_id,'history','history:'+target,name,'기타',link,now,now)).fetchone()
            rid = row['id']
        # Modest synthetic distribution; frequency is factual, score is not.
        choice = int(hashlib.sha256(name.encode()).hexdigest()[:8], 16) % 10
        rating = 3 if choice < 2 else (5 if choice == 9 else 4)
        count = len(records)
        intro = f'점심 기록에 {count}회 등장.'
        observation = ' 여러 번 찾았던 곳이라 점심 후보로 다시 살펴볼 만해요.' if count > 1 else ' 한 번 방문한 기록이 있어요. 다음 선택 때 메뉴를 다시 확인해 보세요.'
        extra = ' 4월 기록은 배달 이용이에요.' if name == '침스버거' else (' 기록에 점심 한식뷔페 운영으로 메모되어 있어요.' if name == '광산포차' else '')
        comment = '[예시 리뷰 · 임의 평점] '+intro+observation+extra+' 맛·가격·응대에 대한 실제 평가가 아닙니다.'
        conn.execute(q('INSERT INTO lunch_review (restaurant_id,username,rating,comment,created_at) VALUES (?,?,?,?,?)'), (rid,AUTHOR,rating,comment,now))
        for date, _ in records:
            if re.fullmatch(r'\d{2}-\d{2}', date):
                conn.execute(q('INSERT INTO lunch_visit (restaurant_id,username,visited_at) VALUES (?,?,?)'), (rid,'방문기록 가져오기','2026-'+date))
    return len(grouped())


def rewrite_history(conn, q, now):
    """Rewrite only imported placeholder reviews; leave actual user reviews intact."""
    marker = KEY + '_personal_notes'
    claimed = conn.execute(q('INSERT INTO meta (key,value) VALUES (?,?) ON CONFLICT (key) DO NOTHING RETURNING key'),
                           (marker, '방문기록 기반 개인 메모; 평점은 사용자 요청으로 임의 부여')).fetchone()
    if not claimed:
        return 0
    rows = conn.execute(q('SELECT v.id,v.comment,r.name FROM lunch_review v JOIN lunch_restaurant r ON r.id=v.restaurant_id WHERE v.username=?'), (AUTHOR,)).fetchall()
    for row in rows:
        old = row['comment'] or ''
        match = re.search(r'점심 기록에 (\d+)회 등장', old)
        if not match:
            raise ValueError('가져온 리뷰의 방문 횟수를 확인할 수 없음')
        count = int(match.group(1))
        tone = int(hashlib.sha256((row['name'] or '').encode()).hexdigest()[:8], 16) % 3
        if '배달 이용' in old:
            comment = '4월에 배달로 한 번 먹었음. 점심 배달 후보로 기록해 둔다.'
        elif '한식뷔페' in old:
            comment = '5월 점심에 한 번 갔음. 당시 기록에는 점심 한식뷔페로 적어 뒀다.'
        elif count >= 4:
            comment = [f'올해 점심으로 {count}번 찾았다. 여러 번 갔던 곳이라 다음 점심 후보에도 남겨 둔다.',
                       f'기록을 보니 점심에 {count}번 갔음. 한동안 자주 찾았던 곳 중 하나.',
                       f'점심으로 {count}번 방문. 메뉴 고민할 때 다시 떠올릴 만한 곳으로 적어 둠.'][tone]
        elif count >= 2:
            comment = [f'점심으로 {count}번 방문. 한 번으로 끝나지 않고 다시 갔던 곳이다.',
                       f'올해 점심 기록에 {count}번 남아 있다. 재방문했던 곳이라 따로 적어 둠.',
                       f'점심에 {count}번 다녀옴. 다음에 근처에서 식사할 때 참고할 곳.'][tone]
        else:
            comment = ['점심으로 한 번 방문. 다녀온 곳을 잊지 않으려고 기록해 둔다.',
                       '한 번 점심 먹으러 갔던 곳. 다음 식사 고를 때 참고하려고 남겨 둠.',
                       '점심 방문 기록이 한 번 있다. 아직 자주 간 곳은 아니라 방문 목록에만 적어 둔다.'][tone]
        conn.execute(q('UPDATE lunch_review SET username=?,comment=? WHERE id=? AND username=?'),
                     ('휴', comment, row['id'], AUTHOR))
    return len(rows)
