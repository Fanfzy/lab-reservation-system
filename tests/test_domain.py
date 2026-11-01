# 业务测试：先定义外部可观察结果，再实现业务服务。
from datetime import date, timedelta, time  # 生成日期极值、时间边界和开放时间样本。
from unittest.mock import patch  # 在保存操作记录时注入故障以验证回滚。
from uuid import uuid4  # 生成重复请求和独立请求的标识。
from django.test import TestCase, override_settings  # 使用独立数据库及测试专用快速密码散列。
from django.utils import timezone  # 检查取消截止和统计日期。
from labapp.models import Lab, Reservation, ReviewRecord, AuditEvent  # 检查真实数据库中的最终结果。
from labapp.services.common import DomainError  # 检查稳定的业务错误标识。
from labapp.services.reservations import review_reservation, cancel_reservation  # 测试审核和取消，提交由FixtureMixin统一调用。
from labapp.services.labs import save_lab  # 测试实验室维护入口。
from labapp.services.accounts import save_account  # 测试账号维护入口。
from labapp.services.reports import summarize  # 测试统计查询入口。
from tests.support import FixtureMixin  # 复用数据准备过程。

@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])  # 仅测试时加快密码准备。
class ReservationTests(FixtureMixin, TestCase):  # 覆盖FR-004到FR-008及NFR-002。
    def setUp(self):  # 每个测试重新建立隔离数据。
        self.prepare()  # 创建角色、实验室和未来时间。

    def test_valid_request_is_pending_and_audited(self):  # TC-001：合法申请应持久化并进入待审核。
        booking = self.booking()  # 提交一条实际预约。
        self.assertEqual(booking.status, Reservation.Status.PENDING)  # 核对初始状态。
        self.assertEqual(Reservation.objects.count(), 1)  # 核对记录已经保存。
        self.assertEqual(AuditEvent.objects.filter(action='SUBMIT').count(), 1)  # 核对业务记录同时保存。

    def test_all_overlap_shapes_are_rejected(self):  # TC-002：相等、部分重叠、包含及被包含都必须拒绝。
        self.booking()  # 建立九点到十点的占用。
        cases = [(0, 60), (-30, 30), (30, 90), (-30, 90), (15, 45)]  # 明确列出外部预期，不调用实际冲突函数计算答案。
        for begin, finish in cases:  # 遍历不同重叠形状。
            with self.subTest(begin=begin, finish=finish):  # 分别报告边界样本。
                with self.assertRaisesMessage(DomainError, '时间冲突'):  # 每种重叠都应返回冲突。
                    self.booking(actor=self.other, start_at=self.start + timedelta(minutes=begin), end_at=self.start + timedelta(minutes=finish))  # 提交冲突申请。
        self.assertEqual(Reservation.objects.count(), 1)  # 失败不能产生额外记录。

    def test_adjacent_both_sides_and_other_lab_are_allowed(self):  # TC-003：相邻与不同实验室预约应成功。
        self.booking()  # 建立中间时段占用。
        self.booking(start_at=self.start - timedelta(hours=1), end_at=self.start)  # 允许前一时段紧邻结束。
        self.booking(start_at=self.end, end_at=self.end + timedelta(hours=1))  # 允许后一时段紧邻开始。
        lab2 = Lab.objects.create(code='L002', name='电子实验室', location='302', capacity=20)  # 建立独立资源。
        self.booking(lab_id=lab2.pk)  # 同一时间使用不同实验室。
        self.assertEqual(Reservation.objects.count(), 4)  # 核对四条预约都有效。

    def test_invalid_times_and_capacity_are_rejected(self):  # TC-004：校验时间、开放区间、精度和人数。
        cases = [dict(end_at=self.start), dict(start_at=self.end, end_at=self.start), dict(start_at=timezone.now() - timedelta(hours=2), end_at=timezone.now() - timedelta(hours=1)), dict(start_at=self.start.replace(hour=7)), dict(end_at=self.end.replace(hour=23)), dict(end_at=self.end + timedelta(days=1)), dict(attendees=0), dict(attendees=21), dict(start_at=self.start.replace(second=1))]  # 列出独立无效输入。
        for values in cases:  # 对每个非法输入运行同一业务入口。
            with self.subTest(values=values):  # 标明具体失败输入。
                with self.assertRaises(DomainError):  # 业务必须明确拒绝。
                    self.booking(**values)  # 提交错误参数。
        self.assertEqual(Reservation.objects.count(), 0)  # 非法输入不得保存。

    def test_disabled_lab_rejects_submission(self):  # TC-005：停用实验室不能预约。
        self.lab.is_active = False  # 将实验室标为停用。
        self.lab.save()  # 保存夹具状态。
        with self.assertRaises(DomainError):  # 期待业务拒绝。
            self.booking()  # 尝试提交预约。

    def test_repeated_key_is_idempotent(self):  # TC-006：同一请求重试不能重复写入。
        key = uuid4()  # 准备浏览器一次提交的唯一标识。
        first = self.booking(request_key=key)  # 首次写入。
        second = self.booking(request_key=key)  # 模拟同一请求重试。
        self.assertEqual(first.pk, second.pk)  # 应返回原预约。
        self.assertEqual(AuditEvent.objects.filter(action='SUBMIT').count(), 1)  # 不能重复记录提交。
        with self.assertRaises(DomainError):  # 其他用户不能借标识读取原申请。
            self.booking(actor=self.other, request_key=key)  # 使用他人请求标识。

    def test_review_permissions_reason_and_repeat(self):  # TC-007：审批受角色、理由和状态限制。
        booking = self.booking()  # 建立待审核记录。
        with self.assertRaises(DomainError):  # 普通用户无权审核。
            review_reservation(self.user, booking.pk, True, '')  # 尝试越权批准。
        with self.assertRaises(DomainError):  # 拒绝理由不能省略。
            review_reservation(self.manager, booking.pk, False, ' ')  # 提交空白拒绝理由。
        review_reservation(self.manager, booking.pk, True, '安排通过')  # 合法批准。
        booking.refresh_from_db()  # 读取最终数据库状态。
        self.assertEqual(booking.status, Reservation.Status.APPROVED)  # 核对批准状态。
        self.assertEqual(ReviewRecord.objects.count(), 1)  # 保存一条审核记录。
        with self.assertRaises(DomainError):  # 同一记录不能重复审核。
            review_reservation(self.manager, booking.pk, True, '')  # 重复点击批准。

    def test_rejection_and_cancellation_release_time(self):  # TC-008：拒绝和取消允许后续申请占用原时段。
        first = self.booking()  # 提交初始申请。
        review_reservation(self.manager, first.pk, False, '实验室安排调整')  # 管理员拒绝。
        second = self.booking(actor=self.other)  # 原时段应重新可申请。
        cancel_reservation(self.other, second.pk)  # 本人开始前取消。
        third = self.booking()  # 再次复用同一时段。
        self.assertEqual(third.status, Reservation.Status.PENDING)  # 新申请保持合法。

    def test_cancellation_ownership_deadline_and_terminal_state(self):  # TC-009：取消遵守归属、截止和终态。
        booking = self.booking()  # 创建本人记录。
        with self.assertRaises(DomainError):  # 其他申请人不能取消。
            cancel_reservation(self.other, booking.pk)  # 尝试操作他人数据。
        with self.assertRaises(DomainError):  # 到开始时刻即禁止取消。
            cancel_reservation(self.user, booking.pk, now=booking.start_at)  # 使用明确截止边界。
        cancel_reservation(self.user, booking.pk)  # 开始前本人取消。
        with self.assertRaises(DomainError):  # 已取消不能再次取消。
            cancel_reservation(self.user, booking.pk)  # 重复取消。

    def test_expired_pending_cannot_be_approved(self):  # TC-010：管理员不能批准已经开始的待审预约。
        booking = self.booking()  # 保存未来预约。
        with self.assertRaises(DomainError):  # 到开始时间后应拒绝审批。
            review_reservation(self.manager, booking.pk, True, '', now=booking.start_at)  # 检查边界。

    def test_submit_and_review_rollback_with_audit_failure(self):  # TC-011：操作记录保存失败时主业务也必须回滚。
        with patch('labapp.services.reservations.audit', side_effect=RuntimeError('injected failure')):  # 在真实事务中注入保存失败。
            with self.assertRaises(RuntimeError):  # 故障应传给调用者而非假装成功。
                self.booking()  # 提交失败事务。
        self.assertEqual(Reservation.objects.count(), 0)  # 主表写入也应撤销。
        booking = self.booking()  # 建立下一次合法申请。
        with patch('labapp.services.reservations.audit', side_effect=RuntimeError('injected failure')):  # 注入审核末尾故障。
            with self.assertRaises(RuntimeError):  # 记录实际异常。
                review_reservation(self.manager, booking.pk, True, '')  # 批准事务失败。
        booking.refresh_from_db()  # 重新查询主记录。
        self.assertEqual(booking.status, Reservation.Status.PENDING)  # 状态应恢复待审。
        self.assertEqual(ReviewRecord.objects.count(), 0)  # 审核记录不应残留。

    def test_future_bookings_protect_lab_edits(self):  # TC-012：资源修改不得使未来预约失效。
        self.booking()  # 建立未来资源占用。
        values = dict(code='L001', name=self.lab.name, location='301', capacity=20, equipment='', description='', open_time=time(8), close_time=time(22), is_active=True)  # 准备完整维护输入。
        for changes in [dict(is_active=False), dict(capacity=2), dict(open_time=time(10))]:  # 检查三类破坏性修改。
            with self.subTest(changes=changes):  # 分别展示修改原因。
                with self.assertRaises(DomainError):  # 存在预约时必须拒绝不兼容修改。
                    save_lab(self.manager, self.lab.pk, {**values, **changes})  # 调用真实维护服务。
        saved = save_lab(self.manager, self.lab.pk, {**values, 'location': '实验楼新301'})  # 不影响预约的修改可以执行。
        self.assertEqual(saved.location, '实验楼新301')  # 核对新位置。

    def test_statistics_fixed_sample_and_scope(self):  # TC-013：用固定数据核对统计和本人数据范围。
        first = self.booking()  # 创建一小时待审申请。
        review_reservation(self.manager, first.pk, True, '')  # 转为已批准。
        self.booking(actor=self.other, start_at=self.end, end_at=self.end + timedelta(hours=2))  # 创建第二个两小时待审申请。
        day = self.start.date()  # 统计明天的预约。
        admin = summarize(self.manager, day, day)  # 查询系统统计。
        own = summarize(self.user, day, day)  # 查询个人统计。
        self.assertEqual(admin['total'], 2)  # 系统范围有两笔申请。
        self.assertEqual(admin['approved_hours'], 1.0)  # 只有批准的一个小时计入时长。
        self.assertEqual(own['total'], 1)  # 普通用户只统计本人。
        self.assertEqual(summarize(self.manager, day + timedelta(days=1), day + timedelta(days=1))['total'], 0)  # 空日期返回零。

    def test_account_management_and_self_protection(self):  # TC-014：只有管理员维护账号，不能停用或降级自己。
        values = dict(username='newstudent', first_name='新同学', is_staff=False, is_active=True, password='StrongDemo!2026')  # 准备新账号输入。
        with self.assertRaises(DomainError):  # 普通用户无权新建账号。
            save_account(self.user, None, values)  # 越权请求。
        saved = save_account(self.manager, None, values)  # 管理员合法创建。
        self.assertTrue(saved.check_password(values['password']))  # 数据库保存的是可验证散列。
        with self.assertRaises(DomainError):  # 管理员不得停用本人。
            save_account(self.manager, self.manager.pk, {**values, 'username': 'manager', 'is_active': False, 'is_staff': True})  # 尝试锁死自身入口。

    def test_statistics_supports_last_calendar_day(self):  # TC-024：有效日期极值不能导致统计溢出。
        booking = self.booking()  # 创建一小时的正常预约。
        review_reservation(self.manager, booking.pk, True, '')  # 将固定样本批准。
        whole = summarize(self.manager, date.min, date.max)  # 查询完整合法日期范围。
        self.assertEqual((whole['total'], whole['approved_hours']), (1, 1.0))  # 核对日期边界不影响正常数据。
        last = summarize(self.manager, date.max, date.max)  # 查询日期上限当天。
        self.assertEqual((last['total'], last['approved_hours']), (0, 0.0))  # 空结果应为零，而不是日期加一天溢出。

    def test_lab_hours_use_minute_precision(self):  # TC-025：开放时间与预约使用相同的分钟精度。
        values = dict(code='L002', name='分钟实验室', location='302', capacity=20, equipment='', description='', open_time=time(8), close_time=time(22), is_active=True)  # 准备合法资源输入。
        for changes in [dict(open_time=time(8, 0, 30)), dict(close_time=time(22, 0, 0, 1))]:  # 覆盖秒和微秒边界。
            with self.subTest(changes=changes):  # 明确显示失败的候选配置。
                with self.assertRaises(DomainError) as caught:  # 秒精度配置不能保存。
                    save_lab(self.manager, None, {**values, **changes})  # 调用实际维护入口。
                self.assertEqual(caught.exception.code, 'INVALID_LAB')  # 返回资源校验提示。
        self.assertFalse(Lab.objects.filter(code='L002').exists())  # 失败输入不留下新资源。

    def test_cancellation_rolls_back_when_audit_fails(self):  # TC-026：取消和审计失败时整体回滚。
        booking = self.booking()  # 建立可取消的未来预约。
        with patch('labapp.services.reservations.audit', side_effect=RuntimeError('injected failure')):  # 在取消保存后的审计处注入异常。
            with self.assertRaises(RuntimeError):  # 保留异常供调用层处理。
                cancel_reservation(self.user, booking.pk)  # 执行真实取消服务。
        booking.refresh_from_db()  # 读取事务结束后的实际结果。
        self.assertEqual(booking.status, Reservation.Status.PENDING)  # 原占用不能被半途释放。
        self.assertIsNone(booking.cancelled_at)  # 取消时间不能残留。
        self.assertIsNone(booking.cancelled_by_id)  # 取消人不能残留。
