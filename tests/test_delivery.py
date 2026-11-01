# 交付质量分区：验证新环境初始化、错误恢复和管理员页面。
from io import StringIO  # 收集命令结果而不污染测试输出。
from contextlib import closing  # 在临时目录回收前关闭测试连接。
from tempfile import TemporaryDirectory  # 将备份测试文件放在可自动回收的位置。
from pathlib import Path  # 构造独立快照路径。
import sqlite3  # 核对备份内容和完整性。
import socket  # 使用真实本机端口验证启动前检查。
import os  # 指定独立的启动验证进程变量。
import re  # 仅替换验证副本中的管理命令。
import subprocess  # 使用真实Windows命令解释器验证入口。
import sys  # 使用当前专用Conda解释器。
from django.core.management import call_command  # 执行与用户相同的演示初始化入口。
from django.contrib.auth.models import User  # 核对账号与密码。
from django.test import TestCase, SimpleTestCase, override_settings  # 提供数据库及无数据库测试。
from django.urls import reverse  # 使用实际路由名称。
from labapp.models import Lab, Reservation, AuditEvent  # 核对初始化和管理结果。
from scripts.backup_database import backup  # 验证交付备份工具。
from tests.support import FixtureMixin  # 准备角色与资源。

class SeedTests(TestCase):  # 验证演示初始化可重复且不覆盖已有资料。
    def test_seed_is_repeatable_without_resetting_passwords(self):  # TC-020：重复初始化不能重设账号或制造重复样本。
        call_command('seed_demo', stdout=StringIO())  # 从空数据库创建演示数据。
        manager = User.objects.get(username='admin01')  # 获取演示管理员。
        self.assertTrue(manager.check_password('LabDemo!2026'))  # 新建账号的演示密码正确。
        manager.set_password('ChangedDemo!2026')  # 模拟用户已经修改密码。
        manager.save()  # 保存真实变更。
        counts = (User.objects.count(), Lab.objects.count(), Reservation.objects.count(), AuditEvent.objects.count())  # 记录第一次初始化结果。
        self.assertEqual(counts[:3], (3, 4, 4))  # 验证规定的演示规模。
        self.assertEqual(set(Reservation.objects.values_list('status', flat=True)), set(Reservation.Status.values))  # 四种状态都有展示样本。
        output = StringIO()  # 收集重复运行的准确提示。
        call_command('seed_demo', stdout=output)  # 再次运行用户入口。
        self.assertIn('新增账号：无', output.getvalue())  # 不能把既有账号误报为本次新增。
        manager.refresh_from_db()  # 重新读取当前密码。
        self.assertTrue(manager.check_password('ChangedDemo!2026'))  # 初始化不覆盖用户设置。
        self.assertEqual(counts, (User.objects.count(), Lab.objects.count(), Reservation.objects.count(), AuditEvent.objects.count()))  # 不追加虚假业务与操作记录。

class DeliveryWebTests(FixtureMixin, TestCase):  # 管理员维护、统计和异常页必须实际可访问。
    def setUp(self):  # 准备独立数据。
        self.prepare()  # 建立申请人与管理员。
    def test_management_pages_and_saved_resource(self):  # TC-021：通过表单新增资源并访问所有管理页面。
        self.client.force_login(self.manager)  # 使用管理员身份。
        data = {'code': 'L002', 'name': '新实验室', 'location': '402', 'capacity': 30, 'equipment': 'PLC', 'description': '', 'open_time': '08:00', 'close_time': '22:00', 'is_active': 'on'}  # 构造真实页面字段。
        self.assertContains(self.client.post(reverse('new_lab'), data, follow=True), '新实验室')  # 页面保存入口成功。
        self.assertTrue(Lab.objects.filter(code='L002').exists())  # 新资源实际入库。
        for name in ['manage_labs', 'accounts', 'audit', 'statistics']:  # 覆盖管理工作区主要页面。
            with self.subTest(name=name):  # 精确标识失败页面。
                self.assertEqual(self.client.get(reverse(name)).status_code, 200)  # 所有页面正常渲染。
        self.assertContains(self.client.get(reverse('audit')), '新增实验室')  # 操作动作使用中文显示。
    @override_settings(DEBUG=False)  # 模拟交付默认配置。
    def test_missing_page_has_friendly_recovery(self):  # TC-022：不存在地址提供恢复入口而不展示堆栈。
        self.client.force_login(self.user)  # 登录普通申请人。
        response = self.client.get('/missing-course-page/')  # 请求一个不存在的页面。
        self.assertContains(response, '未找到页面', status_code=404)  # 正确返回友好404。
        self.assertNotContains(response, 'Traceback', status_code=404)  # 不泄露调试堆栈。

class BackupTests(SimpleTestCase):  # 无需项目数据库也能验证快照工具。
    def test_backup_integrity_and_no_overwrite(self):  # TC-023：快照保持数据并拒绝覆盖与原地备份。
        with TemporaryDirectory() as folder:  # 创建独立测试目录。
            source, target = Path(folder) / 'source.sqlite3', Path(folder) / 'snapshot.sqlite3'  # 区分源和快照。
            with closing(sqlite3.connect(source)) as connection:  # 建立原始样本数据库并保证连接关闭。
                connection.execute('CREATE TABLE sample (value TEXT)')  # 建立简单数据表。
                connection.execute('INSERT INTO sample VALUES (?)', ('备份验证',))  # 写入中文样本。
                connection.commit()  # 在关闭连接前持久保存测试数据。
            backup(source, target)  # 使用交付工具备份。
            with closing(sqlite3.connect(target)) as connection:  # 独立打开快照并保证连接关闭。
                self.assertEqual(connection.execute('SELECT value FROM sample').fetchone()[0], '备份验证')  # 内容保持一致。
                self.assertEqual(connection.execute('PRAGMA integrity_check').fetchone()[0], 'ok')  # 快照结构完整。
            for destination in [source, target]:  # 检查同路径与已存在路径。
                with self.assertRaises(ValueError):  # 两类覆盖风险均被拒绝。
                    backup(source, destination)  # 尝试不被允许的备份。

# 启动检查分区：不创建数据库，验证端口输入和占用保护。
class LauncherTests(SimpleTestCase):  # 独立核对启动工具的外部行为。
    def test_port_validation_and_exclusive_binding(self):  # TC-031：有效、非法和占用端口均有确定结果。
        from scripts.check_local_port import ensure_local_port_available  # 使用实际交付检查函数。
        for value in ['0', '65536', '-1', 'abc', '8000.5']:  # 覆盖范围与格式错误。
            with self.subTest(value=value):  # 明确具体输入。
                with self.assertRaises(ValueError):  # 非法输入不能进入服务启动。
                    ensure_local_port_available(value)  # 调用真实检查入口。
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as reserved:  # 系统分配一个临时端口。
            reserved.bind(('127.0.0.1', 0))  # 不触碰用户正在使用的固定端口。
            reserved.listen()  # 模拟已经运行的本机服务。
            port = reserved.getsockname()[1]  # 读取实际分配值。
            with self.assertRaises(OSError):  # 端口占用时必须拒绝。
                ensure_local_port_available(str(port))  # Windows下不能采用地址复用探测。
        self.assertEqual(ensure_local_port_available(str(port)), port)  # 原监听关闭后端口可以使用。
        self.assertEqual(ensure_local_port_available(str(port)), port)  # 检查函数自身不永久占用端口。
        if os.name == 'nt':  # 批处理解析检查仅在Windows执行。
            root = Path(__file__).resolve().parents[1]  # 定位维护项目或解压后的交付项目。
            with TemporaryDirectory(prefix='lab_launcher_test_') as folder:  # 使用可回收目录，不接触业务数据库。
                directory = Path(folder)  # 本次入口验证副本。
                (directory / 'scripts').mkdir()  # 只准备端口工具所在位置。
                (directory / 'scripts' / 'check_local_port.py').write_bytes((root / 'scripts' / 'check_local_port.py').read_bytes())  # 使用真实交付工具。
                for name in ['启动系统.cmd', '初始化演示数据.cmd', '测试系统.cmd']:  # 验证三种用户双击入口。
                    with self.subTest(launcher=name):  # 指明失败入口。
                        data = (root / name).read_bytes()  # 检查实际文件而非自动转换后的文本。
                        self.assertTrue(data.isascii(), 'CMD控制文本应为ASCII；中文结果由Python输出。')  # 防止中文批处理的解析兼容问题。
                        self.assertNotIn(b'\n', data.replace(b'\r\n', b''), 'CMD文件必须采用完整的Windows换行。')  # 防止编辑器保存为单LF。
                        source = data.decode('ascii').replace('\r\n', '\n')  # 在副本中进行明确的文本替换。
                        pattern = r'^"%LAB_BOOKING_PYTHON%" -B manage\.py .+$'  # 仅识别实际管理命令行。
                        steps = len(re.findall(pattern, source, flags=re.MULTILINE))  # 记录应到达的命令数量。
                        self.assertGreater(steps, 0)  # 不允许空入口伪装为成功。
                        source = re.sub(pattern, '"%LAB_BOOKING_PYTHON%" -c "print(\'MANAGEMENT_STEP_OK\')"', source, flags=re.MULTILINE)  # 用无副作用输出代替建库、初始化、服务和测试。
                        source = source.replace('\npause\n', '\nrem Test skips interactive pause.\n')  # 验证不等待人工按键。
                        launcher = directory / 'entry.cmd'  # 临时入口始终在可回收目录。
                        launcher.write_bytes(source.replace('\n', '\r\n').encode('ascii'))  # 保持正式入口的字符集和换行。
                        environment = {**os.environ, 'LAB_BOOKING_PYTHON': sys.executable, 'LAB_BOOKING_PORT': str(port), 'LAB_BOOKING_DB': str(directory / 'unused.sqlite3')}  # 独立变量不影响已有系统。
                        result = subprocess.run([os.environ.get('COMSPEC', 'cmd.exe'), '/d', '/c', str(launcher)], env=environment, capture_output=True, timeout=15)  # 真实解析整个入口，但不执行业务写命令。
                        output = result.stdout.decode('utf-8', errors='replace')  # 读取Python的中文提示。
                        errors = result.stderr.decode('utf-8', errors='replace')  # 保留命令解释器错误。
                        self.assertEqual(result.returncode, 0, output + errors)  # 入口必须完整成功结束。
                        self.assertEqual(errors.strip(), '', errors)  # 不能把说明误解析为命令后仍报成功。
                        self.assertEqual(output.count('MANAGEMENT_STEP_OK'), steps)  # 每个预定阶段确实到达。
                        if name == '启动系统.cmd':  # 用户启动入口应提供能看懂的访问说明。
                            self.assertIn(f'http://127.0.0.1:{port}/', output)  # 地址来自实际传入端口。
                            self.assertIn('Ctrl+C', output)  # 明确说明停止方式。
                        self.assertFalse((directory / 'unused.sqlite3').exists())  # 解析测试不创建业务数据。
