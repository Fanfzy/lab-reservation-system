# 管理入口：显式定位源码与项目测试，不依赖当前工作目录。
import os  # 设置框架配置入口。
import sys  # 配置模块查找路径和读取命令参数。
from pathlib import Path  # 可靠处理中文和带空格的目录。

ROOT = Path(__file__).resolve().parent  # 获取真实项目根目录。
sys.path.insert(0, str(ROOT / 'src'))  # 让Python能够找到应用源码。
sys.path.insert(0, str(ROOT))  # 让测试包可以被框架发现。
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')  # 默认使用本项目配置。
if __name__ == '__main__':  # 仅直接运行时执行管理命令。
    from django.core.management import execute_from_command_line  # 延迟导入环境中已安装的框架。
    execute_from_command_line(sys.argv)  # 执行启动、迁移、测试等命令。
