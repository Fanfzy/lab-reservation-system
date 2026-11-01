# 数据分区：实验室信息及基本约束。
from datetime import time  # 设置每日开放时段默认值。
from django.conf import settings  # 使用项目注册的用户模型。
from django.db import models  # 使用框架数据模型与数据库约束。
from django.db.models import F, Q  # 构造数据库字段比较与条件。
from django.utils import timezone  # 推导预约展示状态。

class Lab(models.Model):  # 保存一间可整体预约的实验室。
    code = models.CharField('编码', max_length=32, unique=True)  # 用唯一编码识别资源。
    name = models.CharField('名称', max_length=100)  # 保存用户可读名称。
    location = models.CharField('位置', max_length=150)  # 保存楼栋与房间。
    capacity = models.PositiveIntegerField('容量')  # 限制单次预约人数。
    equipment = models.TextField('设备', blank=True)  # 保存设备说明。
    description = models.TextField('说明', blank=True)  # 保存其他使用说明。
    open_time = models.TimeField('开放时间', default=time(8))  # 默认早上八点开放。
    close_time = models.TimeField('关闭时间', default=time(22))  # 默认晚上十点关闭。
    is_active = models.BooleanField('可预约', default=True)  # 停用后保留历史资料。
    updated_at = models.DateTimeField(auto_now=True)  # 记录最后更新时间。
    class Meta:  # 定义排序和数据库基本约束。
        ordering = ['code']  # 稳定展示资源顺序。
        constraints = [models.CheckConstraint(condition=Q(capacity__gte=1), name='lab_positive_capacity'), models.CheckConstraint(condition=Q(close_time__gt=F('open_time')), name='lab_valid_hours')]  # 在数据库防止无效容量和开放时间。
    def __str__(self):  # 提供表单选择和日志中的可读名称。
        return f'{self.code} · {self.name}'  # 同时展示编码和名称。

# 数据分区：预约记录和展示属性。
class Reservation(models.Model):  # 保存申请与当前业务状态。
    class Status(models.TextChoices):  # 状态值使用稳定的内部标识。
        PENDING = 'PENDING', '待审核'  # 待审核也占用资源。
        APPROVED = 'APPROVED', '已批准'  # 已批准继续占用资源。
        REJECTED = 'REJECTED', '已拒绝'  # 拒绝释放时段。
        CANCELLED = 'CANCELLED', '已取消'  # 取消释放时段。
    applicant = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='reservations')  # 保留申请人的历史关联。
    lab = models.ForeignKey(Lab, on_delete=models.PROTECT, related_name='reservations')  # 保留实验室的历史关联。
    start_at = models.DateTimeField('开始时间')  # 保存含日期的开始时刻。
    end_at = models.DateTimeField('结束时间')  # 保存含日期的结束时刻。
    purpose = models.CharField('用途', max_length=500)  # 保存申请用途。
    attendees = models.PositiveIntegerField('人数')  # 保存计划参与人数。
    request_key = models.UUIDField(unique=True)  # 防止同一提交请求重复写入。
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)  # 保存可验证的状态。
    created_at = models.DateTimeField(auto_now_add=True)  # 保存申请提交时间。
    cancelled_at = models.DateTimeField(null=True, blank=True)  # 保存实际取消时刻。
    cancelled_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name='cancelled_reservations')  # 保存取消操作者。
    class Meta:  # 定义常用检索方式与基本约束。
        ordering = ['-created_at', '-pk']  # 默认展示最新申请。
        indexes = [models.Index(fields=['lab', 'status', 'start_at'], name='booking_occupancy_idx'), models.Index(fields=['applicant', 'start_at'], name='booking_owner_date_idx')]  # 支持资源占用和本人查询。
        constraints = [models.CheckConstraint(condition=Q(end_at__gt=F('start_at')), name='booking_valid_interval'), models.CheckConstraint(condition=Q(attendees__gte=1), name='booking_positive_attendees'), models.CheckConstraint(condition=Q(status__in=['PENDING', 'APPROVED', 'REJECTED', 'CANCELLED']), name='booking_valid_status')]  # 防止无效区间、人数和非法状态。
    @property  # 向页面暴露状态相关的只读属性。
    def can_cancel(self):  # 判断当前时间是否仍可显示取消入口。
        return self.status in [self.Status.PENDING, self.Status.APPROVED] and self.start_at > timezone.now()  # 写入时业务层仍会再次校验。
    @property  # 由时间推导展示备注，不伪造实际使用记录。
    def time_note(self):  # 给历史状态补充时间说明。
        now = timezone.now()  # 获取当前实际时间。
        if self.status == self.Status.APPROVED and self.end_at <= now:  # 已批准时段已经结束。
            return '预约时段已结束'  # 只表示计划时段结束。
        if self.status == self.Status.PENDING and self.start_at <= now:  # 待审申请已错过开始时刻。
            return '已过期，不能再批准'  # 保留原始待审状态。
        return ''  # 正常未来时段不添加备注。

# 数据分区：审核证据与关键操作记录。
class ReviewRecord(models.Model):  # 每条预约最多保留一次正式审核。
    reservation = models.OneToOneField(Reservation, on_delete=models.PROTECT, related_name='review')  # 避免重复审核记录。
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)  # 保存审核操作者。
    approved = models.BooleanField()  # 明确记录通过还是拒绝。
    reason = models.CharField(max_length=500, blank=True)  # 保存理由或审核备注。
    reviewed_at = models.DateTimeField(auto_now_add=True)  # 保存实际审核时间。

class AuditEvent(models.Model):  # 在业务事务中记录关键动作。
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)  # 保留操作者关联。
    action = models.CharField(max_length=32)  # 保存稳定操作标识。
    subject = models.CharField(max_length=120)  # 保存被操作对象的文字标识。
    detail = models.TextField(blank=True)  # 保存关键输入与状态变化说明。
    created_at = models.DateTimeField(auto_now_add=True)  # 保存真实操作时间。
    @property  # 页面显示中文操作名称，数据库仍保留稳定标识。
    def action_label(self):  # 将已定义的业务动作转换成易读名称。
        labels = {'SUBMIT': '提交申请', 'APPROVE': '批准预约', 'REJECT': '拒绝预约', 'CANCEL': '取消预约', 'LAB_CREATE': '新增实验室', 'LAB_UPDATE': '修改实验室', 'USER_CREATE': '新增账号', 'USER_UPDATE': '修改账号', 'DEMO_INIT': '初始化演示数据'}  # 集中维护名称对应关系。
        return labels.get(self.action, self.action)  # 未知历史标识仍可追踪。
    class Meta:  # 规定查看顺序。
        ordering = ['-created_at', '-pk']  # 最新操作优先显示。
