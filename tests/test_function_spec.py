"""Actual template-control coverage and navigation for the detailed IA document."""
import json
import unittest
from pathlib import Path
from bs4 import BeautifulSoup
ROOT=Path(__file__).resolve().parents[1]
FILES=['index','launcher','videos','finance','intro','mobile_install','maeum_record_plan','service_notice']
class FunctionSpecTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.manifest=json.loads((ROOT/'static/docs/function-spec-coverage.json').read_text())
  cls.soup=BeautifulSoup((ROOT/'static/docs/function-spec.html').read_text(),'html.parser')
 def test_each_actual_template_control_has_a_specification(self):
  for file in FILES:
   controls=BeautifulSoup((ROOT/f'templates/{file}.html').read_text(),'html.parser').select('button,input:not([type=hidden]),select,textarea,a,summary')
   refs=[c for c in self.manifest['template_controls'] if c['file']==file]
   self.assertEqual(len(controls),len(refs),file)
   ids={c['id'] for c in refs}
   for el in controls:
    if el.get('id'):self.assertTrue(any(c['selector']=='#'+el['id'] for c in refs),el['id'])
   self.assertEqual(len(ids),len(refs),file)
 def test_rows_are_unique_complete_and_rendered_in_both_formats(self):
  rows=self.manifest['rows'];md=(ROOT/'static/docs/function-spec.md').read_text()
  rendered=self.soup.select('#spec-table tbody tr')
  self.assertEqual(len(rows),len(rendered))
  self.assertEqual(len(rows),len({r['id'] for r in rows}))
  self.assertGreater(len(rows),450)
  for row,el in zip(rows,rendered):
   self.assertEqual(len(el.find_all('td',recursive=False)),14)
   for key in ['d1','d2','d3','d4','d5','description','input','result','exception','permission','storage','source']:
    self.assertTrue(row[key].strip(),row['id']+' '+key)
   self.assertIn(row['id'],md)
   self.assertIn(row['description'],el.get_text())
 def test_all_principal_screens_and_regions_are_present(self):
  rows=self.manifest['rows'];screens={r['d2'] for r in rows};zones={r['d3'] for r in rows}
  self.assertTrue({'런처','냥정보','게임정보','NC뉴스','비영리재단 동향','보안뉴스','행사일정','맛집 목록','식당 평점·후기','점심 추천','영상','재무세무','스크랩','AI 리포트','로그인','기사 본문 리더','공유하기','서비스 소개','설치 도움말','마음기록 기획서'}<=screens)
  self.assertTrue({'탑','바디','푸터','팝업'}<=zones)
 def test_unused_password_template_is_not_a_live_screen(self):
  self.assertNotIn('maeum_password',[c['file'] for c in self.manifest['template_controls']])
  self.assertIn('현재 비밀번호 없이',(ROOT/'static/docs/function-spec.md').read_text())
 def test_launcher_and_document_download_links_exist(self):
  source=(ROOT/'templates/launcher.html').read_text()
  self.assertIn("filename='docs/function-spec.html'",source)
  self.assertIn('기능명세서 · IA',source)
  self.assertTrue(self.soup.select_one('a[href="function-spec.md"][download]'))
  for id in ['spec-search','spec-screen','spec-zone','spec-permission','spec-count','spec-print']:
   self.assertIsNotNone(self.soup.select_one('#'+id))
if __name__=='__main__':unittest.main()
