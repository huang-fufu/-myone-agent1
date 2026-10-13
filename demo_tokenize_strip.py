"""演示学习：用 tokenize 精确删除代码注释、保留 docstring。"""

import io
import re
import tokenize

SOURCE = '''\
"""
这是一个 docstring，会被保留。
因为它在 token 层面属于 STRING，不是 COMMENT。
"""
import os  # 这行尾部注释会被删除

def greet(name):
    # 这行整行注释会被删除
    msg = "# 这不是注释，是字符串，会被保留"
    print(f"hello {name}")
'''

def strip_comments(source: str) -> str:
    """保留 docstring 与字符串，只删 COMMENT token，并压平多余空行。"""
    tokens = [
        token
        for token in tokenize.generate_tokens(io.StringIO(source).readline)
        if token.type != tokenize.COMMENT
    ]
    text = tokenize.untokenize(tokens)
    text = "\n".join(line.rstrip() for line in text.splitlines())
    return re.sub(r"\n{3,}", "\n\n", text).strip() + "\n"


if __name__ == "__main__":
    print("========== 原始代码 ==========")
    print(SOURCE)

    print("========== 删除注释后 ==========")
    cleaned = strip_comments(SOURCE)
    print(cleaned)