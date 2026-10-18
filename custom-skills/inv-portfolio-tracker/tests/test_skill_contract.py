from pathlib import Path
import unittest

SKILL = Path(__file__).resolve().parents[1]

class SkillContractTest(unittest.TestCase):
    def test_trade_workflow_has_no_duplicate_qarp_write(self):
        text = (SKILL / 'SKILL.md').read_text()
        trade = text.split('## 调仓更新流程', 1)[1].split('## 受控决策闭环', 1)[0]
        self.assertNotIn('QARP check', trade)
        self.assertIn('只记录异常待核', text)
        self.assertIn('render --details', text)

if __name__ == '__main__':
    unittest.main()
