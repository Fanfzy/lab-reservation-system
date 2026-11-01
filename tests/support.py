# 测试夹具：生成相互独立的用户、实验室和未来预约时间。
from datetime import timedelta  # 构造相对于运行日期的未来时间。
from uuid import uuid4  # 给不同提交生成独立请求标识。
from django.contrib.auth.models import User  # 使用框架提供的用户模型。
from django.utils import timezone  # 按项目时区生成可比较的时间。
from labapp.models import Lab  # 使用真实实验室模型作为测试数据。
from labapp.services.reservations import submit_reservation  # 通过公开业务入口创建预约。

class FixtureMixin:  # 为不同测试组提供共享的数据准备方法。
    def prepare(self):  # 为当前用例建立自己的测试数据。
        self.user = User.objects.create_user('student', password='LabDemo!2026')  # 建立普通申请人。
        self.other = User.objects.create_user('other', password='LabDemo!2026')  # 建立第二个申请人。
        self.manager = User.objects.create_user('manager', password='LabDemo!2026', is_staff=True)  # 建立管理员。
        self.lab = Lab.objects.create(code='L001', name='自动控制实验室', location='实验楼301', capacity=20)  # 建立默认可用实验室。
        self.start = (timezone.localtime() + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)  # 选择明天九点。
        self.end = self.start + timedelta(hours=1)  # 预约持续一小时。

    def booking(self, **changes):  # 只封装公共输入，不复用实现中的判定逻辑。
        values = dict(actor=self.user, lab_id=self.lab.pk, start_at=self.start, end_at=self.end, purpose='控制系统实验', attendees=3, request_key=uuid4())  # 提供标准合法请求。
        values.update(changes)  # 允许单个测试调整一个或多个输入。
        return submit_reservation(**values)[0]  # 返回业务入口实际保存的预约。
