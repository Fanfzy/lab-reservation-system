# 结构导出分区：从已迁移演示数据库导出可检查的空结构。
from contextlib import closing  # 避免数据库文件句柄泄漏。
from pathlib import Path  # 确定交付源与目标。
import sqlite3  # 使用环境自带数据库接口。
ROOT = Path(__file__).resolve().parents[1]  # 项目根目录。
with closing(sqlite3.connect((ROOT / 'database' / 'demo.sqlite3').as_uri() + '?mode=ro', uri=True)) as connection:  # 只读初始演示快照。
    statements = connection.execute("SELECT sql FROM sqlite_master WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%' ORDER BY CASE type WHEN 'table' THEN 0 ELSE 1 END,name").fetchall()  # 表先于索引，排除SQLite内部对象。
lines = ['-- 本文件为数据库空结构参考；标准创建入口为manage.py migrate。', '-- 不包含演示数据或django_migrations中的版本记录。', 'PRAGMA foreign_keys=ON; -- 启用外键校验。']  # 说明重建边界。
for (sql,) in statements:  # 将每条真实DDL加入脚本。
    lines.extend(line + ' -- 由已迁移模型结构导出。' for line in (sql.rstrip(';') + ';').splitlines())  # 每行补充来源注释。
(ROOT / 'database' / 'schema.sql').write_text('\n'.join(lines) + '\n', encoding='utf-8')  # 保存可复查SQL。
print(f'已导出{len(statements)}条结构语句。')  # 报告真实导出规模。
