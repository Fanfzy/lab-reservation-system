# 统计查询：仅读取数据，固定数量和计划时长口径。
from datetime import date, datetime, timedelta, time  # 构造包含首尾日期并兼容日期极值的统计窗口。
from django.db.models import Count  # 在数据库中汇总数量。
from django.utils import timezone  # 保持统计日期与界面时区一致。
from labapp.models import Reservation  # 查询预约记录。
from labapp.services.common import DomainError, require_user  # 验证统计访问权限。

def summarize(actor, start_date, end_date):  # 返回数量、状态分布和获批计划时长。
    require_user(actor)  # 复查当前身份与角色。
    if start_date > end_date:  # 统计日期不能颠倒。
        raise DomainError('INVALID_DATE', '统计开始日期不能晚于结束日期。')  # 返回可修正提示。
    query = Reservation.objects.filter(start_at__date__gte=start_date, start_at__date__lte=end_date)  # 申请数按预约开始日期筛选。
    if not actor.is_staff:  # 申请人只统计本人。
        query = query.filter(applicant=actor)  # 强制数据归属。
    grouped = dict(query.values_list('status').annotate(total=Count('pk')))  # 汇总当前状态。
    total = sum(grouped.values())  # 计算窗口内申请总数。
    lower = timezone.make_aware(datetime.combine(start_date, time.min))  # 包含开始日零点。
    upper_value = datetime.combine(end_date + timedelta(days=1), time.min) if end_date < date.max else datetime.max  # 日期上限使用当天最后微秒，避免加一天溢出。
    upper = timezone.make_aware(upper_value)  # 普通日期采用次日零点；分钟预约不触及最大日期的微秒边界。
    seconds = 0.0  # 初始化获批计划时长。
    for booking in query.filter(status=Reservation.Status.APPROVED):  # 取消和拒绝不计入时长。
        seconds += max(0, (min(booking.end_at, upper) - max(booking.start_at, lower)).total_seconds())  # 累计与窗口相交的区间。
    states = [{'key': key, 'label': label, 'count': grouped.get(key, 0), 'percent': round(grouped.get(key, 0) * 100 / total, 1) if total else 0} for key, label in Reservation.Status.choices]  # 零数据也展示完整状态。
    by_lab = list(query.values('lab__code', 'lab__name').annotate(total=Count('pk')).order_by('-total', 'lab__code'))  # 汇总各实验室申请数量。
    return {'total': total, 'approved_hours': round(seconds / 3600, 2), 'states': states, 'by_lab': by_lab, 'start_date': start_date, 'end_date': end_date}  # 返回只读结果。
