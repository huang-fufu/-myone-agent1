"""skill.py 技能系统测试：防路径逃逸、缺失技能报错、目录枚举。"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from skill import load_skill, skills_catalog


class TestLoadSkill(unittest.TestCase):
    def test_illegal_name_blocked(self):
        """../ 等越界技能名必须被拦，返回非法技能名错误。"""
        result = load_skill.invoke({"name": "../walk"})
        self.assertIn("非法技能名", result)

    def test_missing_skill_returns_error(self):
        """不存在的技能返回错误并附带可用技能列表。"""
        result = load_skill.invoke({"name": "no_such_skill_xyz"})
        self.assertIn("没有技能", result)


class TestSkillsCatalog(unittest.TestCase):
    def test_catalog_never_raises(self):
        """目录枚举绝不能抛异常（skills 目录可能不存在）。"""
        result = skills_catalog.invoke({})
        self.assertIsInstance(result, str)


if __name__ == "__main__":
    unittest.main(verbosity=2)