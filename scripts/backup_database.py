# 备份分区：SQLite备份接口产生一致快照，禁止覆盖既有备份。
import argparse  # 读取数据库源路径与目标路径。
from contextlib import closing  # 确保连接结束时实际关闭文件句柄。
import sqlite3  # 使用环境自带的数据库接口。
from pathlib import Path  # 规范文件位置。

def backup(source, target):  # 对实际数据库创建独立快照。
    source, target = Path(source).resolve(), Path(target).resolve()  # 使用确定的绝对路径。
    if not source.is_file() or source == target or target.exists():  # 禁止无效源、原地备份与覆盖文件。
        raise ValueError('源数据库必须存在；备份目标必须是新的独立文件。')  # 明确操作边界。
    target.parent.mkdir(parents=True, exist_ok=True)  # 准备目标目录。
    with closing(sqlite3.connect(source.as_uri() + '?mode=ro', uri=True)) as original:  # 只读连接不修改源数据并在退出时关闭。
        with closing(sqlite3.connect(target)) as snapshot:  # 创建新快照数据库并及时释放Windows文件句柄。
            original.backup(snapshot)  # SQLite保证一致的备份视图。
            result = snapshot.execute('PRAGMA integrity_check').fetchone()[0]  # 验证快照结构完整。
            if result != 'ok':  # 损坏快照不能报告成功。
                raise RuntimeError(result)  # 保留完整性诊断。
    return target  # 返回已核对目标位置。

if __name__ == '__main__':  # 直接运行时解析参数。
    parser = argparse.ArgumentParser(description='创建不覆盖既有文件的SQLite一致备份')  # 展示用途。
    parser.add_argument('source')  # 指定源数据库。
    parser.add_argument('target')  # 指定新备份位置。
    args = parser.parse_args()  # 获取用户输入。
    print(backup(args.source, args.target))  # 输出真实生成的快照位置。
