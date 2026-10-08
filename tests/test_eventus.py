import datetime as dt
import unittest
from unittest.mock import Mock, patch

from collector import eventus
from collector.event_identity import merge_events

TODAY = dt.date(2026, 10, 6)


def row(title='AI 산업 포럼', **kwargs):
    values = dict(title=title, description='산업 사례 발표와 패널 토론', event_type='강연/세미나',
                  id='12345', subdomain='host', start_date='2026-10-20T00:30:00Z',
                  close_date='2026-10-20T06:00:00Z', area_detail='서울 강남구',
                  full_address='서울 강남구 영동대로', place='코엑스', app_title='주최기관',
                  event_system_type='offline', cover_image_url='/Image/host/12345/cover.jpg', min_money=0)
    values.update(kwargs)
    return {key: {'raw': value} for key, value in values.items()}


class EventusTests(unittest.TestCase):
    def test_context_keeps_events_without_allowing_courses(self):
        for title in ['AI 산업 포럼 특별강연', '개발자 컨퍼런스', '반려동물 페어', '창업 네트워킹', '해커톤', '교육 박람회']:
            self.assertTrue(eventus.is_event(title), title)
        for title in ['AI 특강', '포럼 준비 교육과정', '개발자 부트캠프', '원데이클래스', '자격증 강의', '[상시진행] IT 세미나', 'AI 컨설팅', '2026 재도전 전시,교육 체험 프로그램', '2026 포럼 2기 모집']:
            self.assertFalse(eventus.is_event(title, '컨퍼런스 참가 방법 소개'), title)
        self.assertTrue(eventus.is_event('AI 정책 세미나', '정책 토론과 사례 발표'))
        self.assertFalse(eventus.is_event('AI 실습 세미나', '커리큘럼을 수강하세요'))
        self.assertFalse(eventus.is_event('투자 워크숍', '6주 과정 교육생 모집'))
        self.assertFalse(eventus.is_event('맛보기 강의', '', '학술회의'))
        self.assertFalse(eventus.is_event('아기유니콘 성장 프로그램 기업모집', '', '대회/공모전'))

    def test_observed_raw_schema_mapping_and_korean_midnight(self):
        result = eventus.parse(row(start_date='2026-10-19T15:30:00Z'), TODAY)
        self.assertEqual(result['start_date'], '2026-10-20')
        self.assertEqual(result['source_url'], 'https://event-us.kr/host/event/12345')
        self.assertEqual(result['image_url'], 'https://eventusstorage.blob.core.windows.net/evs/Image/host/12345/cover.jpg')
        self.assertIn('무료', result['content'])
        self.assertEqual(result['author'], '주최기관')

    def test_expired_missing_dates_foreign_permanent_and_invalid_urls(self):
        for changes in [dict(close_date='2000-01-01'), dict(start_date=None), dict(close_date='2030-01-01'),
                        dict(start_date='2026-02-30'), dict(subdomain='../x'), dict(id='abc'),
                        dict(area_detail='도쿄', full_address='Japan')]:
            self.assertIsNone(eventus.parse(row(**changes), TODAY), changes)
        self.assertIsNone(eventus.parse(row(title='CES 2027 스타트업전시관', place='라스베가스'), TODAY))
        self.assertIsNone(eventus.parse(row(title='싱가포르 핀테크 페스티벌', event_system_type='online'), TODAY))
        self.assertIsNotNone(eventus.parse(row(event_system_type='online', area_detail='', full_address=''), TODAY))

    def test_pagination_repeated_rows_and_exclusion_before_storage(self):
        response = Mock(); response.json.return_value = {'results':[row(), row('AI 특강', id='23456')], 'meta':{'page':{'total_pages':3}}}
        session = Mock(); session.post.return_value = response
        session.__enter__ = Mock(return_value=session); session.__exit__ = Mock(return_value=False)
        with patch.object(eventus.requests, 'Session', return_value=session), patch.object(eventus.time, 'sleep'):
            result = eventus.collect()
        self.assertEqual(len(result), 1)
        self.assertEqual(session.post.call_count, 2)
        self.assertEqual(eventus.diagnose()['excluded'], 1)

    def test_rate_limit_does_not_retry_or_fail_the_other_sources(self):
        response = Mock(); response.raise_for_status.side_effect = eventus.requests.HTTPError()
        session = Mock(); session.post.return_value = response
        session.__enter__ = Mock(return_value=session); session.__exit__ = Mock(return_value=False)
        with patch.object(eventus.requests, 'Session', return_value=session):
            self.assertEqual(eventus.collect(), [])
        self.assertEqual(session.post.call_count, 1)
        self.assertEqual(eventus.diagnose()['error'], 'HTTPError')

    def test_merge_url_title_date_and_venue_with_official_preference(self):
        official = eventus.parse(row(), TODAY)
        news = dict(official, source='뉴스', url='https://news.google.com/rss/123', source_url='https://news.example/a',
                    title='[사전등록] AI 산업 포럼', image_url='')
        second_city = dict(official, url='https://event-us.kr/host/event/67890', source_url='', venue='부산 벡스코')
        later_session = dict(official, url='https://event-us.kr/host/event/67891', source_url='', start_date='2026-10-21')
        merged = merge_events([news, official, second_city, later_session])
        self.assertEqual(len(merged), 3)
        self.assertEqual(merged[0]['source'], '이벤터스')
        self.assertEqual(len(merge_events([official, dict(official, url=official['url']+'?utm_source=test')])), 1)
        # Long common prefixes must not collapse differently named sessions.
        other = dict(official, title=official['title']+' 개발자 세션', url='https://other.example/', source_url='')
        self.assertEqual(len(merge_events([official, other])), 2)


if __name__ == '__main__':
    unittest.main()
