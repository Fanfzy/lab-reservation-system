# 实验室维护：所有候选配置先校验，再保护现有占用。
from django.core.exceptions import ValidationError  # 转换模型校验错误。
from django.utils import timezone  # 统一每日时间比较。
from labapp.models import Lab, Reservation  # 获取资源和关联预约。
from labapp.services.common import DomainError, require_manager, write_transaction, audit  # 复用统一写入机制。
from labapp.services.reservations import OCCUPYING  # 共享占用状态定义。
FIELDS = ['code', 'name', 'location', 'capacity', 'equipment', 'description', 'open_time', 'close_time', 'is_active']  # 限定可维护字段。

def save_lab(actor, lab_id, values):  # 创建或修改实验室。
    with write_transaction():  # 维护与预约提交共同竞争写锁。
        require_manager(actor)  # 验证当前管理权限。
        try:  # 准备更新或创建对象。
            lab = Lab.objects.get(pk=lab_id) if lab_id is not None else Lab()  # 保留原资源主键。
        except Lab.DoesNotExist as error:  # 处理无效编号。
            raise DomainError('NOT_FOUND', '实验室不存在。') from error  # 返回稳定错误。
        for field in FIELDS:  # 避免外部输入写入未知字段。
            if field in values:  # 只应用明确提供的值。
                setattr(lab, field, values[field])  # 设置候选配置。
        lab.code, lab.name, lab.location = lab.code.strip().upper(), lab.name.strip(), lab.location.strip()  # 规范编码和必要文本。
        try:  # 检查字段、唯一性和基本约束。
            lab.full_clean()  # 使用与数据库一致的模型校验。
        except ValidationError as error:  # 聚合字段错误。
            raise DomainError('INVALID_LAB', '；'.join(error.messages)) from error  # 返回页面可读提示。
        if any(value.second or value.microsecond for value in [lab.open_time, lab.close_time]):  # 维护输入与预约保持同一时间精度。
            raise DomainError('INVALID_LAB', '开放和关闭时间精度为分钟，请不要填写秒。')  # 避免保存界面无法完整表达的资源时段。
        if lab_id is not None:  # 更新时检查仍有效的占用。
            bookings = Reservation.objects.filter(lab_id=lab_id, status__in=OCCUPYING, end_at__gt=timezone.now())  # 保护未来和正在进行的预约。
            for booking in bookings:  # 逐条检查新配置兼容性。
                start, end = timezone.localtime(booking.start_at), timezone.localtime(booking.end_at)  # 转为本地时间。
                if not lab.is_active or booking.attendees > lab.capacity or start.time() < lab.open_time or end.time() > lab.close_time:  # 不允许破坏已有预约。
                    raise DomainError('LAB_HAS_BOOKINGS', '存在未来或进行中的有效预约，请先处理预约，再调整停用、容量或开放时间。')  # 提示正确处理顺序。
        lab.save()  # 兼容条件满足后写入。
        audit(actor, 'LAB_UPDATE' if lab_id is not None else 'LAB_CREATE', f'实验室#{lab.pk}', f'{lab.code}；容量{lab.capacity}；可预约={lab.is_active}')  # 保存维护证据。
        return lab  # 返回实际保存结果。
