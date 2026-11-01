# 校验分区：时间、容量与半开区间冲突。
from datetime import datetime  # 检查时间对象的类型。
from uuid import UUID  # 规范化提交唯一标识。
from django.utils import timezone  # 转换用户所在时区。
from labapp.models import Lab, Reservation, ReviewRecord  # 访问实际预约数据。
from labapp.services.common import DomainError, require_user, require_manager, write_transaction, audit  # 统一授权和写事务。
OCCUPYING = [Reservation.Status.PENDING, Reservation.Status.APPROVED]  # 两种有效占用状态。

def validate_interval(lab, start_at, end_at, attendees, now):  # 核对完整资源使用条件。
    if not isinstance(start_at, datetime) or not isinstance(end_at, datetime) or timezone.is_naive(start_at) or timezone.is_naive(end_at):  # 禁止模糊输入或缺失时区。
        raise DomainError('INVALID_TIME', '请填写有效的开始和结束时间。')  # 返回格式提示。
    if start_at >= end_at or start_at <= now:  # 开始必须在未来且区间长度为正。
        raise DomainError('INVALID_TIME', '开始时间必须在未来，且早于结束时间。')  # 描述时间限制。
    if start_at.second or start_at.microsecond or end_at.second or end_at.microsecond:  # 首版采用分钟精度。
        raise DomainError('INVALID_TIME', '预约时间精度为分钟，请不要填写秒。')  # 避免界面与业务精度不一致。
    start, end = timezone.localtime(start_at), timezone.localtime(end_at)  # 转为实验室所在时区。
    if start.date() != end.date() or start.time() < lab.open_time or end.time() > lab.close_time:  # 区间必须同日且位于开放时间内。
        raise DomainError('INVALID_TIME', '预约必须在同一天，并位于实验室开放时间内。')  # 给出实际条件。
    if not isinstance(attendees, int) or isinstance(attendees, bool) or attendees < 1 or attendees > lab.capacity:  # 检查整数人数与容量。
        raise DomainError('INVALID_CAPACITY', f'人数必须为1至{lab.capacity}的整数。')  # 展示当前容量。
    if not lab.is_active:  # 使用写事务读取的资源状态。
        raise DomainError('LAB_DISABLED', '该实验室已停用，暂时不能预约。')  # 阻止停用资源预约。

def has_conflict(lab_id, start_at, end_at, exclude_id=None):  # 查询半开区间重叠。
    query = Reservation.objects.filter(lab_id=lab_id, status__in=OCCUPYING, start_at__lt=end_at, end_at__gt=start_at)  # 严格不等号允许首尾相邻。
    if exclude_id is not None:  # 审批不能把本记录作为冲突。
        query = query.exclude(pk=exclude_id)  # 排除自身。
    return query.exists()  # 仅查询是否存在占用。

# 提交分区：幂等重试与占用检查处于同一写事务。
def submit_reservation(actor, lab_id, start_at, end_at, purpose, attendees, request_key, now=None):  # 返回预约和是否新建。
    try:  # 将表单标识统一为UUID。
        key = UUID(str(request_key))  # 解析一次提交标识。
    except (ValueError, TypeError, AttributeError) as error:  # 捕获非法标识。
        raise DomainError('INVALID_REQUEST', '提交标识无效，请重新打开预约页面。') from error  # 给出恢复方法。
    purpose = str(purpose).strip()  # 去掉用途首尾空白。
    if not purpose or len(purpose) > 500:  # 业务入口也校验用途。
        raise DomainError('INVALID_PURPOSE', '请填写不超过500字的预约用途。')  # 拒绝无效文本。
    with write_transaction():  # 获得写锁后才读取占用条件。
        require_user(actor)  # 复查当前身份。
        if actor.is_staff:  # 首版管理员使用申请人账号演示申请。
            raise DomainError('FORBIDDEN', '请使用申请人账号提交预约。')  # 保持角色职责明确。
        existing = Reservation.objects.filter(request_key=key).first()  # 查询同一提交是否已经成功。
        if existing is not None:  # 避免重试重复写入。
            same = existing.applicant_id == actor.pk and existing.lab_id == lab_id and existing.start_at == start_at and existing.end_at == end_at and existing.purpose == purpose and existing.attendees == attendees  # 仅接受相同身份和内容重试。
            if not same:  # 防止他人借标识读取或变更请求。
                raise DomainError('REQUEST_REUSED', '请求标识已被使用，请重新打开申请页面。')  # 不暴露原预约内容。
            return existing, False  # 返回原结果且不重复记录动作。
        try:  # 读取当前资源配置。
            lab = Lab.objects.get(pk=lab_id)  # 使用事务中的最新资源。
        except (Lab.DoesNotExist, ValueError, TypeError) as error:  # 处理非法编号。
            raise DomainError('NOT_FOUND', '实验室不存在。') from error  # 返回明确错误。
        validate_interval(lab, start_at, end_at, attendees, now or timezone.now())  # 验证时间、容量与可用性。
        if has_conflict(lab.pk, start_at, end_at):  # 在写事务中检查占用。
            raise DomainError('CONFLICT', '预约时间冲突，请选择其他时段。')  # 拒绝任何重叠形状。
        booking = Reservation.objects.create(applicant=actor, lab=lab, start_at=start_at, end_at=end_at, purpose=purpose, attendees=attendees, request_key=key)  # 保存待审申请。
        audit(actor, 'SUBMIT', f'预约#{booking.pk}', f'{lab.code}；待审核；{start_at.isoformat()}至{end_at.isoformat()}')  # 操作记录一起保存。
        return booking, True  # 完整事务成功才报告新建。

# 审核分区：重新检查资源、状态和过期条件。
def review_reservation(actor, booking_id, approved, reason, now=None):  # 审核一条待审申请。
    reason = str(reason).strip()  # 规范化审核说明。
    if not isinstance(approved, bool) or len(reason) > 500 or (not approved and not reason):  # 验证结果与拒绝理由。
        raise DomainError('INVALID_REVIEW', '请选择审核结果，拒绝时须填写不超过500字的理由。')  # 返回具体限制。
    with write_transaction():  # 审核与其他占用操作共同竞争写事务。
        require_manager(actor)  # 复查管理权限。
        try:  # 从数据库读取最新记录。
            booking = Reservation.objects.select_related('lab').get(pk=booking_id)  # 同时读取实验室配置。
        except Reservation.DoesNotExist as error:  # 处理无效编号。
            raise DomainError('NOT_FOUND', '预约不存在。') from error  # 返回明确错误。
        if booking.status != Reservation.Status.PENDING:  # 终态和已批准不能再次审批。
            raise DomainError('INVALID_STATE', '只有待审核预约可以审批，请刷新查看最新状态。')  # 引导刷新状态。
        if approved:  # 批准前检查资源仍然有效。
            validate_interval(booking.lab, booking.start_at, booking.end_at, booking.attendees, now or timezone.now())  # 排除过期与不可用资源。
            if has_conflict(booking.lab_id, booking.start_at, booking.end_at, booking.pk):  # 排除本预约后复查冲突。
                raise DomainError('CONFLICT', '预约时间冲突，不能批准。')  # 拒绝异常占用。
        booking.status = Reservation.Status.APPROVED if approved else Reservation.Status.REJECTED  # 应用合法状态转换。
        booking.save(update_fields=['status'])  # 更新当前状态。
        ReviewRecord.objects.create(reservation=booking, reviewer=actor, approved=approved, reason=reason)  # 保存唯一审核证据。
        audit(actor, 'APPROVE' if approved else 'REJECT', f'预约#{booking.pk}', f'待审核→{booking.get_status_display()}；{reason}')  # 主状态和证据原子提交。
        return booking  # 返回审核后的对象。

# 取消分区：归属与时间边界必须在写入前复查。
def cancel_reservation(actor, booking_id, now=None):  # 释放待审或批准的未来时段。
    with write_transaction():  # 与同时审核共享事务策略。
        require_user(actor)  # 检查当前身份。
        try:  # 读取当前预约状态。
            booking = Reservation.objects.get(pk=booking_id)  # 获取实际记录。
        except Reservation.DoesNotExist as error:  # 处理无效编号。
            raise DomainError('NOT_FOUND', '预约不存在。') from error  # 提供稳定错误。
        if booking.applicant_id != actor.pk and not actor.is_staff:  # 仅本人或管理员能取消。
            raise DomainError('FORBIDDEN', '只能取消本人的预约。')  # 阻止跨用户操作。
        if booking.status not in OCCUPYING or booking.start_at <= (now or timezone.now()):  # 开始时刻即截止。
            raise DomainError('INVALID_STATE', '仅能在开始前取消待审核或已批准的预约。')  # 明确当前限制。
        before = booking.get_status_display()  # 保留原始状态说明。
        booking.status, booking.cancelled_at, booking.cancelled_by = Reservation.Status.CANCELLED, now or timezone.now(), actor  # 设置取消结果。
        booking.save(update_fields=['status', 'cancelled_at', 'cancelled_by'])  # 一并更新取消证据。
        audit(actor, 'CANCEL', f'预约#{booking.pk}', f'{before}→已取消')  # 与释放资源动作同时提交。
        return booking  # 返回已取消对象。
