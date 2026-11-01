# 源码检查分区：检查项目自有代码的语法和逐行注释约定。
from pathlib import Path  # 遍历规范目录中的源文件。
import io  # 将Python源码交给标记器。
import tokenize  # 使用真实注释标记而非字符串中井号判断。
import json  # 输出可归档检查证据。
ROOT = Path(__file__).resolve().parents[1]  # 定位根目录。
paths = [ROOT / 'manage.py', *sorted((ROOT / 'src').rglob('*')), *sorted((ROOT / 'tests').rglob('*')), *sorted((ROOT / 'scripts').rglob('*')), ROOT / 'database' / 'schema.sql', ROOT / 'environment.yml']  # 只检查维护源，不扫描第三方或验证副本。
failures, checked = [], 0  # 保存失败位置和核对规模。
for path in paths:  # 逐一检查实际文件。
    if not path.is_file() or path.suffix not in {'.py', '.html', '.css', '.js', '.sql', '.yml'}:  # 跳过目录和非代码数据。
        continue  # 避免把数据库或缓存当作文本。
    content = path.read_text(encoding='utf-8-sig')  # 兼容UTF-8源码。
    checked += 1  # 记录检查数量。
    if path.suffix == '.py':  # Python采用语法和词法双检查。
        compile(content, str(path), 'exec')  # 语法失败立即停止，且不生成pyc。
        comments = {token.start[0] for token in tokenize.generate_tokens(io.StringIO(content).readline) if token.type == tokenize.COMMENT}  # 找出真实注释所在行。
        bad = [number for number, line in enumerate(content.splitlines(), 1) if line.strip() and number not in comments]  # 每个非空物理行都应有注释。
    else:  # 文本代码使用各自注释符号。
        signs = {'.html': ('<!--', '{#'), '.css': ('/*',), '.js': ('//',), '.sql': ('--',), '.yml': ('#',)}[path.suffix]  # 明确各类允许符号。
        bad = [number for number, line in enumerate(content.splitlines(), 1) if line.strip() and not any(sign in line for sign in signs)]  # 找出无注释的非空行。
    failures.extend(f'{path.relative_to(ROOT)}:{number}' for number in bad)  # 保留精确位置。
result = {'checked_files': checked, 'python_syntax': 'PASS', 'line_comments': 'PASS' if not failures else 'FAIL', 'missing': failures}  # 不把启发式文本检查称为完整静态分析。
print(json.dumps(result, ensure_ascii=False, indent=2))  # 输出实际结果。
if failures:  # 注释规范未满足则失败。
    raise SystemExit(1)  # 交付前阻止遗漏。
