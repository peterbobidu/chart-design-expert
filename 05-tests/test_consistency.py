"""Regression tests for stale claims, with historical and partial-scope controls."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('consistency', ROOT / 'scripts/check_consistency.py')
consistency = importlib.util.module_from_spec(spec)
spec.loader.exec_module(consistency)


class ConsistencyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='chart-doc-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for path in consistency.AUTHORITY.values():
            self.write(path, '# Current authority\n')

    def write(self, path, text):
        p = self.root / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding='utf-8')

    def test_current_tree(self):
        self.assertEqual(consistency.check(ROOT), [])

    def test_obsolete_hd_parallel_entry(self):
        self.write('03-references/chart-spec/hd.md', '| 平行坐标 | 暂无专项文件；沿用方法05 |\n')
        self.assertTrue(any('obsolete HD parallel' in e for e in consistency.check(self.root)))

    def test_unscoped_parallel_focus_gap(self):
        self.write('03-references/methods/05/detail.md', '线宽、轴间距、目标标记及图形高亮等未定义处为建议。\n')
        self.assertTrue(any('parallel focus style gap' in e for e in consistency.check(self.root)))

    def test_parallel_partial_and_other_domain_gaps_are_allowed(self):
        self.write('03-references/methods/05/detail.md', 'HD初始态线条未定义；其他领域缺专项时按任务设计。\n')
        self.write('03-references/chart-spec/semiconductor/general.md', '半导体平行坐标专项暂无定义，不自动继承HD。\n')
        self.write('CHANGELOG.md', '历史HD平行坐标暂无专项文件。\n')
        self.assertEqual(consistency.check(self.root), [])

    def test_legacy_tooltip_gap_list(self):
        self.write('03-references/chart-spec/charts/line.md', '## 尚未覆盖\nTooltip视觉参数和Select/Highlight图形详细样式。\n')
        self.assertTrue(any('uncovered' in e for e in consistency.check(self.root)))

    def test_hover_blanket_gap(self):
        self.write('03-references/methods/05/detail.md', '线宽、目标标记和 Hover 等未定义处为本次建议。\n')
        self.assertTrue(any('whole-Tooltip' in e for e in consistency.check(self.root)))

    def test_partial_and_historical_claims_are_allowed(self):
        self.write('03-references/chart-spec/charts/line.md', '## 尚未覆盖\nTooltip字重未定义；桌面Hover视觉读取组件规范。\n')
        self.write('CHANGELOG.md', '## 旧版本\nTooltip视觉参数未定义。\n')
        self.write('05-tests/tooltip-cases.md', '输入：Tooltip视觉参数未定义吗？预期读取当前组件。\n')
        self.assertEqual(consistency.check(self.root), [])

    def test_missing_authority_is_rejected(self):
        (self.root / consistency.AUTHORITY['Tooltip']).unlink()
        self.assertTrue(any('missing authority' in e for e in consistency.check(self.root)))

    def test_old_next_run_instruction(self):
        self.write('05-tests/regression-0920.md', '下一次运行使用整理后的v0.6.4。\n')
        self.assertTrue(any('historical version' in e for e in consistency.check(self.root)))

    def test_mini_blanket_gap(self):
        self.write('03-references/prototype/generation-review.md', 'Mini专项规范未接入时自行设计。\n')
        self.assertTrue(any('unscoped Mini' in e for e in consistency.check(self.root)))

    def test_old_router_title(self):
        self.write('05-tests/router-cases.md', '# Router Cases｜v0.6.4\n')
        self.assertTrue(any('suite title' in e for e in consistency.check(self.root)))

    def test_historical_confirmation_cannot_depend_on_current_chat(self):
        self.write('05-tests/vue-echarts-cases.md', '前三项设计方案已由用户在当前对话确认；工程测试分别记录。\n')
        self.assertTrue(any('current conversation' in e for e in consistency.check(self.root)))

    def test_history_and_quoted_confirmation_remain_allowed(self):
        self.write('05-tests/vue-echarts-cases.md',
                   '沿用v0.6.4历史记录，当前版本需重新验证。\n'
                   '> 前三项设计方案已由用户在当前对话确认。\n'
                   '输入：用户在当前对话已确认方案，请继续。\n')
        self.assertEqual(consistency.check(self.root), [])

    def test_current_task_reference_is_not_a_historical_result(self):
        self.write('05-tests/treemap-cases.md', '本次任务请使用当前对话提供的数据，不读取预期。\n')
        self.assertEqual(consistency.check(self.root), [])

    def test_legitimate_domain_and_reference_differences(self):
        self.write('03-references/chart-spec/semiconductor/general.md', '图外图例10px；Y轴标题90°。\n')
        self.write('03-references/chart-spec/components/tooltip.md', '卡内圆点8px；字重未定义。\n')
        self.write('03-references/methods/03/reference.md', '参考HTML的分类标签-90°，不是Y轴标题。\n')
        self.assertEqual(consistency.check(self.root), [])

    def test_hosted_and_readme_scope(self):
        self.write('05-tests/chart-spec-cases.md', '| CS-Vue-01 | 默认原型 | 默认Vue及Vite |\n')
        self.write('05-tests/echarts-capability-cases.md', '| 工程有外部补充实现 | README可访问交接说明 |\n')
        errors = consistency.check(self.root)
        self.assertTrue(any('existing-host' in e for e in errors))
        self.assertTrue(any('README' in e for e in errors))

    def test_method_count_summary(self):
        self.write(consistency.AUTHORITY['method state'], '已编写6张、待实现7张\n| 01 | 趋势 | 已编写 | card |\n')
        self.assertTrue(any('count summary' in e for e in consistency.check(self.root)))

    def test_inventory_covers_all_markdown_and_classifies_history(self):
        self.write('CHANGELOG.md', '旧记录\n')
        self.write('05-tests/sample.md', '默认行为待核对\n')
        self.write('03-references/new.md', '未提供规范\n')
        rows = consistency.inventory(self.root)
        self.assertEqual(len(rows), len(list(self.root.rglob('*.md'))))
        self.assertEqual(next(x for x in rows if x['path'] == 'CHANGELOG.md')['kind'], 'history')
        self.assertEqual(len(next(x for x in rows if x['path'] == '03-references/new.md')['review_claims']), 1)


if __name__ == '__main__':
    unittest.main()
