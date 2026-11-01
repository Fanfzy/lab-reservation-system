# 页面与权限测试：通过HTTP入口验证服务是否实际被正确调用。
from uuid import uuid4  # 生成表单提交标识。
from django.test import TestCase, Client, override_settings  # 提供浏览器请求替身及CSRF严格检查客户端。
from django.urls import reverse  # 依据命名路由构造实际请求地址。
from labapp.models import Reservation  # 查询页面请求产生的数据。
from tests.support import FixtureMixin  # 准备独立数据。

@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])  # 测试专用快速散列。
class WebTests(FixtureMixin, TestCase):  # 覆盖登录、页面、筛选、归属和请求安全。
    def setUp(self):  # 每次准备全新数据。
        self.prepare()  # 创建两个角色与实验室。

    def test_login_and_manager_guard(self):  # TC-015：未登录跳转，普通用户不能进入管理员界面。
        self.assertEqual(self.client.get(reverse('labs')).status_code, 302)  # 未登录跳转登录页。
        self.assertFalse(self.client.login(username='student', password='wrong'))  # 错误密码不能登录。
        self.assertTrue(self.client.login(username='student', password='LabDemo!2026'))  # 正确密码可登录。
        self.assertEqual(self.client.get(reverse('manage_labs')).status_code, 403)  # 服务端阻止越权。
        self.user.is_active = False  # 停用账号。
        self.user.save()  # 保存停用状态。
        self.client.logout()  # 清除已有测试会话。
        self.assertFalse(self.client.login(username='student', password='LabDemo!2026'))  # 停用用户不能登录。

    def test_complete_browser_request_flow(self):  # TC-016：通过真实页面入口完成申请、审核和取消。
        self.client.force_login(self.user)  # 以申请人身份访问。
        data = dict(start_at=self.start.strftime('%Y-%m-%dT%H:%M'), end_at=self.end.strftime('%Y-%m-%dT%H:%M'), purpose='网页完整流程实验', attendees=3, request_key=str(uuid4()))  # 准备浏览器表单格式。
        response = self.client.post(reverse('book_lab', args=[self.lab.pk]), data, follow=True)  # 提交预约并跟随页面跳转。
        self.assertContains(response, '待审核')  # 页面显示正确状态。
        booking = Reservation.objects.get()  # 核对数据库实际保存。
        self.client.force_login(self.manager)  # 切换管理员身份。
        response = self.client.post(reverse('review_booking', args=[booking.pk]), {'decision': 'approve', 'reason': ''}, follow=True)  # 通过审批页面批准。
        self.assertContains(response, '已批准')  # 页面显示审批结果。
        self.client.force_login(self.user)  # 切换回申请人。
        self.assertContains(self.client.get(reverse('booking_detail', args=[booking.pk])), '确认取消此预约并释放时段')  # 页面采用明确的取消确认控件。
        response = self.client.post(reverse('cancel_booking', args=[booking.pk]), {'confirm_cancel': 'yes'}, follow=True)  # 明确确认后发起取消。
        self.assertContains(response, '已取消')  # 页面与最终状态一致。

    def test_ownership_and_csrf_are_enforced(self):  # TC-017：直接猜地址和省略CSRF均不能绕过控制。
        booking = self.booking()  # 建立第一个申请人的记录。
        self.client.force_login(self.other)  # 使用其他申请人。
        self.assertEqual(self.client.get(reverse('booking_detail', args=[booking.pk])).status_code, 404)  # 不暴露他人记录。
        self.assertEqual(self.client.post(reverse('cancel_booking', args=[booking.pk])).status_code, 404)  # 不能取消他人记录。
        strict = Client(enforce_csrf_checks=True)  # 开启浏览器实际使用的CSRF限制。
        strict.force_login(self.manager)  # 准备已登录管理员会话。
        self.assertEqual(strict.post(reverse('review_booking', args=[booking.pk]), {'decision': 'approve'}).status_code, 403)  # 缺令牌的写请求被拒绝。
        self.assertEqual(self.client.get(reverse('cancel_booking', args=[booking.pk])).status_code, 405)  # GET不能触发取消。

    def test_filters_and_invalid_input(self):  # TC-018：筛选与错误输入在页面层也生效。
        self.booking()  # 准备可筛选记录。
        self.client.force_login(self.user)  # 登录申请人。
        self.assertContains(self.client.get(reverse('labs'), {'q': '自动控制'}), self.lab.name)  # 中文关键词找到实验室。
        self.assertNotContains(self.client.get(reverse('labs'), {'q': '不存在的实验室'}), 'L001')  # 无匹配结果不展示原实验室。
        self.assertEqual(self.client.get(reverse('lab_detail', args=[self.lab.pk]), {'date': 'bad-date'}).status_code, 200)  # 无效日期显示校验提示而不崩溃。
        response = self.client.post(reverse('book_lab', args=[self.lab.pk]), {'start_at': 'bad-date', 'end_at': '', 'purpose': '', 'attendees': 0, 'request_key': str(uuid4())})  # 提交错误表单。
        self.assertContains(response, '请检查')  # 显示中文错误提示。
        self.assertEqual(Reservation.objects.count(), 1)  # 无效输入不能写入。

    def test_empty_post_displays_required_field_errors(self):  # TC-027：空POST必须绑定表单并显示必填错误。
        self.client.force_login(self.user)  # 准备申请人身份。
        response = self.client.post(reverse('book_lab', args=[self.lab.pk]), {})  # 提交没有任何字段的表单。
        self.assertTrue(response.context['form'].is_bound)  # 空POST仍是已经提交的表单。
        self.assertIn('start_at', response.context['form'].errors)  # 展示开始时间必填错误。
        self.assertEqual(Reservation.objects.count(), 0)  # 不能写入不完整预约。
        self.client.force_login(self.manager)  # 准备资源和账号维护身份。
        for name in ['new_lab', 'new_account']:  # 检查所有编辑入口。
            with self.subTest(name=name):  # 定位具体表单。
                response = self.client.post(reverse(name), {})  # 发送空维护请求。
                self.assertTrue(response.context['form'].is_bound)  # 保留提交状态。
                self.assertTrue(response.context['form'].errors)  # 不应无提示地返回未绑定表单。

    def test_self_password_change_preserves_current_session(self):  # TC-028：管理员修改本人密码后继续使用当前会话。
        self.client.force_login(self.manager)  # 登录将修改自身密码的管理员。
        data = dict(username=self.manager.username, first_name='管理员', password='ChangedDemo!2026', is_staff='on', is_active='on')  # 保持角色与启用状态。
        response = self.client.post(reverse('edit_account', args=[self.manager.pk]), data, follow=True)  # 从实际账号页面改密码。
        self.assertEqual(response.request['PATH_INFO'], reverse('accounts'))  # 成功后留在管理列表，而非意外跳回登录页。
        self.assertTrue(response.context['user'].is_authenticated)  # 当前会话继续有效。
        self.manager.refresh_from_db()  # 核对保存的密码。
        self.assertTrue(self.manager.check_password(data['password']))  # 新密码可验证。
        self.assertFalse(self.manager.check_password('LabDemo!2026'))  # 原密码失效。

    def test_cancellation_requires_explicit_confirmation(self):  # TC-029：服务端也核对取消确认字段。
        booking = self.booking()  # 建立未来待审核预约。
        self.client.force_login(self.user)  # 使用记录本人。
        for data in [{}, {'confirm_cancel': 'no'}]:  # 覆盖缺失和不合法确认值。
            with self.subTest(data=data):  # 精确标识请求输入。
                response = self.client.post(reverse('cancel_booking', args=[booking.pk]), data, follow=True)  # 提交未确认取消。
                self.assertContains(response, '请先确认取消此预约')  # 页面提供可修正提示。
                booking.refresh_from_db()  # 重新读取实际状态。
                self.assertEqual(booking.status, Reservation.Status.PENDING)  # 未确认不能释放时段。
        self.client.post(reverse('cancel_booking', args=[booking.pk]), {'confirm_cancel': 'yes'})  # 提交明确确认。
        booking.refresh_from_db()  # 核对保存结果。
        self.assertEqual(booking.status, Reservation.Status.CANCELLED)  # 正常确认流程仍能完成。

    def test_statistics_page_accepts_calendar_upper_bound(self):  # TC-030：网页的合法最大日期不会返回500。
        self.client.force_login(self.user)  # 以申请人打开统计。
        response = self.client.get(reverse('statistics'), {'start_date': '9999-12-31', 'end_date': '9999-12-31'})  # 使用日期控件允许的合法上限。
        self.assertEqual(response.status_code, 200)  # 显示页面而不是异常。
        self.assertEqual(response.context['summary']['total'], 0)  # 正确展示空统计。
