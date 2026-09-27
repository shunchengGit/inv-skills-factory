import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'weekly_guard.py'
spec = importlib.util.spec_from_file_location('weekly_guard', SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class WeeklyGuardTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root/'USER.md').write_text('组合约束: 单只股票仓位上限：`<= 40%`\n组合约束: 单一行业集中度：`<= 55%`\n现金只记账，不作否决。\n', encoding='utf8')
        (self.root/'PORTFOLIO.md').write_text('## 当前持仓\n| 标的 | 代码 |\n|---|---|\n| 腾讯 | 00700 |\n| 现金 | — |\n', encoding='utf8')
        (self.root/'audit.json').write_text(json.dumps({'integrity':'ok','coverage':1,'rows':[{'symbol':'00700','status':'needs_review','gaps':[{'id':'issue'}]}]}), encoding='utf8')
        (self.root/'review.md').write_text('本周新增：00700 需复核；现金只记账，不作买卖门槛。旧价线仅提醒。', encoding='utf8')
    def tearDown(self):
        self.tmp.cleanup()
    def test_current_rules_and_unresolved_research_reported(self):
        d=module.check(self.root/'USER.md', self.root/'PORTFOLIO.md', self.root/'audit.json', self.root/'review.md')
        self.assertTrue(d['checks']['rules_current'])
        self.assertFalse(d['checks']['research_ready'])
        self.assertEqual(d['unresolved'], ['00700'])
    def test_obsolete_rule_cannot_pass(self):
        (self.root/'review.md').write_text('下周现金 <5% 停止新建仓，腾讯触价立即加仓。', encoding='utf8')
        d=module.check(self.root/'USER.md', self.root/'PORTFOLIO.md', self.root/'audit.json', self.root/'review.md')
        self.assertFalse(d['checks']['rules_current'])
        self.assertIn('obsolete_action_rule', d['blockers'])
    def test_missing_review_or_invalid_audit_fails_closed(self):
        (self.root/'review.md').unlink()
        d=module.check(self.root/'USER.md', self.root/'PORTFOLIO.md', self.root/'audit.json', self.root/'review.md')
        self.assertFalse(d['checks']['weekly_artifact'])
        (self.root/'audit.json').write_text('{', encoding='utf8')
        d=module.check(self.root/'USER.md', self.root/'PORTFOLIO.md', self.root/'audit.json', self.root/'review.md')
        self.assertFalse(d['checks']['ledger_integrity'])
    def test_missing_holding_in_ledger_blocks_authorization(self):
        (self.root/'PORTFOLIO.md').write_text('## 当前持仓\n| 标的 | 代码 |\n|---|---|\n| 腾讯 | 00700 |\n| 微软 | MSFT |\n| 现金 | — |\n', encoding='utf8')
        d=module.check(self.root/'USER.md', self.root/'PORTFOLIO.md', self.root/'audit.json', self.root/'review.md')
        self.assertFalse(d['checks']['holding_coverage'])
        self.assertIn('MSFT', d['missing_holdings'])
        self.assertFalse(d['research_authorized'])
    def test_review_must_name_all_holdings_or_list_unresolved(self):
        (self.root/'audit.json').write_text(json.dumps({'integrity':'ok','coverage':1,'rows':[{'symbol':'00700','status':'decision_ready','gaps':[]}]}), encoding='utf8')
        (self.root/'review.md').write_text('本周无任何增量；继续观察。', encoding='utf8')
        d=module.check(self.root/'USER.md', self.root/'PORTFOLIO.md', self.root/'audit.json', self.root/'review.md')
        self.assertFalse(d['checks']['weekly_artifact'])
        self.assertIn('review_missing_holdings', d['blockers'])
    def test_constraint_change_requires_review_update(self):
        (self.root/'USER.md').write_text('单只股票仓位上限：`<= 35%`\n单一行业集中度：`<= 55%`\n现金只记账，不作否决。', encoding='utf8')
        (self.root/'review.md').write_text('下周单只上限 <=40%，现金只记账。', encoding='utf8')
        d=module.check(self.root/'USER.md', self.root/'PORTFOLIO.md', self.root/'audit.json', self.root/'review.md')
        self.assertFalse(d['checks']['rules_current'])
if __name__=='__main__': unittest.main()
