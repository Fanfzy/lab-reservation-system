# 真并发测试：使用文件数据库与不同线程的独立数据库连接。
from threading import Barrier, Thread  # 同步两个真实竞争的操作。
from django.db import connections, close_old_connections  # 管理线程各自的数据库连接。
from django.test import TransactionTestCase, override_settings  # 允许真实事务提交而非单个测试外层回滚。
from labapp.models import Reservation  # 核对提交后的全局数据库状态。
from labapp.services.common import DomainError  # 记录正常业务竞争结果。
from tests.support import FixtureMixin  # 准备已提交的夹具。

@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])  # 测试专用快速密码散列。
class ConcurrencyTests(FixtureMixin, TransactionTestCase):  # 覆盖FR-008的并发占用要求。
    def setUp(self):  # 用真实提交准备两个申请人。
        self.prepare()  # 将夹具写入当前文件测试数据库。

    def test_simultaneous_overlapping_requests_only_one_succeeds(self):  # TC-019：两个同时提交的冲突申请只能成功一笔。
        self.assertNotIn(':memory:', str(connections['default'].settings_dict['NAME']))  # 禁止用内存数据库代替真实文件。
        barrier = Barrier(2)  # 两个线程等待同一起点。
        results = []  # 收集每个线程的实际结果。
        def compete(actor):  # 定义单个独立连接上的申请过程。
            close_old_connections()  # 避免复用其他线程的连接。
            try:  # 确保结束时关闭线程连接。
                barrier.wait(timeout=10)  # 在业务入口之前同时放行。
                self.booking(actor=actor)  # 各自提交相同实验室时段。
                results.append('OK')  # 记录真实提交成功。
            except DomainError as error:  # 收集业务冲突。
                results.append(error.code)  # 保留稳定错误标识。
            except Exception as error:  # 将意外错误也暴露为失败结果。
                results.append(type(error).__name__)  # 不吞掉线程异常。
            finally:  # 无论成功与否都释放连接。
                connections['default'].close()  # 关闭本线程数据库连接。
        workers = [Thread(target=compete, args=(actor,)) for actor in [self.user, self.other]]  # 使用不同申请人构造竞争。
        for worker in workers:  # 启动并发操作。
            worker.start()  # 让两个线程重叠执行。
        for worker in workers:  # 等待并检查工作线程。
            worker.join(timeout=15)  # 给数据库等待和业务操作明确截止。
            self.assertFalse(worker.is_alive())  # 禁止线程无期限悬挂。
        self.assertCountEqual(results, ['OK', 'CONFLICT'])  # 一笔成功，另一笔在锁内读取后发现冲突。
        self.assertEqual(Reservation.objects.count(), 1)  # 最终数据库只有一笔占用。
