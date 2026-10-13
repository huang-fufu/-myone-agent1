"""s15 技能系统（薄目录 + 按需加载）。"""
from pathlib import Path

from langchain_core.tools import tool

from tools import WORKDIR  # tools 是底座层，无循环依赖

SKILLS_DIR = WORKDIR / "skills"


def _parse_skill(path: Path) -> tuple[str, str]:
    """解析一个 SKILL.md：返回 (name, description)。

    Skill 的 frontmatter 格式为 --- 开头，里面有 name: 和 description: 字段。
    description 可能是一行，也可能是 | 多行块；多行块只取第一行作为目录摘要。
    """
    name = path.parent.name
    desc = ""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return name, desc

    # 定位 frontmatter（首行是 --- 时，找第二个 --- 作为结束行）。
    if lines and lines[0].strip() == "---":
        end = 1
        while end < len(lines) and lines[end].strip() != "---":
            end += 1
        fm, after = lines[1:end], lines[end + 1:]
    else:
        fm, after = [], lines

    in_multiline_desc = False
    for ln in fm:
        s = ln.strip()
        if s.startswith("name") and len(s) > 5:
            name = s[5:].strip()
        elif s.startswith("description:"):
            rest = s[len("description:"):].strip()
            if rest == "|":
                # 多行块：后续缩进的正文行由下面统一兜底。
                in_multiline_desc = True
            elif rest:
                desc = rest
        elif in_multiline_desc and s and not s.startswith("name:") and not desc:
            desc = s

    if not desc:
        # description 缺失时，取正文里第一个非标题行作为摘要。
        for ln in after:
            s = ln.strip()
            if s and not s.startswith("#"):
                desc = s
                break
    return name, desc


@tool
def skills_catalog() -> str:
    """扫描 skills/*/SKILL.md，只把目录（名称 + 摘要）放进目录，内容按需再加载。"""
    entries = []
    for p in sorted(SKILLS_DIR.glob("*/SKILL.md")):
        name, desc = _parse_skill(p)
        entries.append(f"- {name}:" + (f" {desc[:90]}" if desc else ""))
    if not entries:
        return "可用技能：（无）"
    return "可用技能（使用 load_skill 加载完整内容）：\n" + "\n".join(entries)


@tool
def load_skill(name: str) -> str:
    """通过目录名加载已安装技能的完整内容。"""
    # 防路径逃逸：resolve 后必须仍在技能目录内（挡住 ../../ 之类）。
    skill = (SKILLS_DIR / name / "SKILL.md").resolve()
    if not skill.is_relative_to(SKILLS_DIR.resolve()):
        return f"Error: 非法技能名:{name}"
    if not skill.exists():
        return f"Error: 没有技能:{name}；可用技能：" + skills_catalog.invoke({})
    try:
        return skill.read_text(encoding="utf-8")
    except Exception as e:
        return f"Error: {e}"