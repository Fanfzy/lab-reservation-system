# 访问分区：HTTP入口只解析输入并调用业务服务。
import calendar  # 生成当前月的统计默认窗口。
from datetime import timedelta  # 给新申请提供明天的默认时段。
from functools import wraps  # 保留装饰器包装函数信息。
from uuid import uuid4  # 初始化一次表单提交标识。
from django.contrib import messages  # 显示中文成功与错误提示。
from django.contrib.auth import update_session_auth_hash  # 修改本人密码后安全更新当前会话验证值。
from django.contrib.auth.decorators import login_required  # 对页面执行登录校验。
from django.contrib.auth.models import User  # 查询账号管理列表。
from django.core.paginator import Paginator  # 对长列表进行分页。
from django.db.models import Q  # 组合关键词条件。
from django.shortcuts import get_object_or_404, redirect, render  # 提供页面响应和受控对象查询。
from django.utils import timezone  # 使用项目时区。
from django.views.decorators.http import require_POST  # 写入操作只接受POST。
from labapp.forms import ReservationForm, LabForm, AccountForm, LabFilterForm, DateForm, BookingFilterForm, StatisticsForm  # 统一解析表单。
from labapp.models import Lab, Reservation, AuditEvent  # 读取页面展示数据。
from labapp.services.common import DomainError, require_manager  # 稳定处理权限与业务错误。
from labapp.services.reservations import submit_reservation, review_reservation, cancel_reservation, OCCUPYING  # 业务规则唯一入口。
from labapp.services.labs import save_lab  # 维护资源并保护预约。
from labapp.services.accounts import save_account  # 维护账号与角色。
from labapp.services.reports import summarize  # 读取统计结果。

def manager_required(view):  # 封装管理员HTTP访问控制。
    @wraps(view)  # 保留原视图名称。
    def wrapped(request, *args, **kwargs):  # 验证当前请求角色。
        try:  # 将业务授权失败转换为403页面。
            require_manager(request.user)  # 以数据库当前角色校验。
        except DomainError as error:  # 处理越权请求。
            return render(request, 'labapp/error.html', {'title': '没有操作权限', 'error': str(error)}, status=403)  # 不返回管理数据。
        return view(request, *args, **kwargs)  # 合法管理请求继续执行。
    return login_required(wrapped)  # 匿名请求先进入登录流程。

def visible_bookings(user):  # 为所有记录入口统一数据归属。
    query = Reservation.objects.select_related('lab', 'applicant', 'cancelled_by')  # 避免展示列表时重复查询外键。
    return query if user.is_staff else query.filter(applicant=user)  # 普通用户始终限定本人。

# 查询分区：实验室列表、详情和占用时段。
@login_required  # 实验室系统要求登录访问。
def labs(request):  # 查询可预约资源。
    form = LabFilterForm(request.GET or {'active': 'active'})  # 绑定经过验证的筛选条件。
    query = Lab.objects.all()  # 初始资源查询。
    if form.is_valid():  # 只使用成功解析的值。
        data = form.cleaned_data  # 获取规范化输入。
        if data['q']:  # 根据关键词筛选。
            query = query.filter(Q(code__icontains=data['q']) | Q(name__icontains=data['q']) | Q(location__icontains=data['q']))  # 查询编码、名称和位置。
        if data['min_capacity']:  # 容量条件可以省略。
            query = query.filter(capacity__gte=data['min_capacity'])  # 限制最低容量。
        state = data['active'] or 'active'  # 缺省仍只显示可用资源。
        if state != 'all':  # 全部状态无需额外过滤。
            query = query.filter(is_active=state == 'active')  # 区分可用与停用。
    return render(request, 'labapp/labs.html', {'title': '找到适合你的实验室', 'section': 'labs', 'form': form, 'labs': query, 'lab_count': query.count(), 'available_count': Lab.objects.filter(is_active=True).count()})  # 返回本地页面。

@login_required  # 占用详情只对有效会话开放。
def lab_detail(request, lab_id):  # 展示资源信息及选定日期占用。
    lab = get_object_or_404(Lab, pk=lab_id)  # 不存在资源返回404。
    day = timezone.localdate()  # 默认查看今天。
    form = DateForm(request.GET or {'date': day})  # 解析用户选择日期。
    if form.is_valid():  # 输入有效时才切换日期。
        day = form.cleaned_data['date']  # 使用实际日期值。
    occupied = Reservation.objects.filter(lab=lab, status__in=OCCUPYING, start_at__date=day).order_by('start_at')  # 只展示占用区间，不展示他人用途或身份。
    return render(request, 'labapp/lab_detail.html', {'title': lab.name, 'section': 'labs', 'lab': lab, 'form': form, 'day': day, 'occupied': occupied})  # 返回资源详情。

# 申请分区：表单错误保留输入，写入只调用服务。
@login_required  # 预约申请要求有效会话。
def book_lab(request, lab_id):  # 展示和提交单个实验室预约。
    lab = get_object_or_404(Lab, pk=lab_id)  # 检查资源编号。
    if request.user.is_staff:  # 管理员不直接提交申请。
        return render(request, 'labapp/error.html', {'title': '请选择申请人账号', 'error': '管理员负责资源维护与审核，请使用申请人账号预约。'}, status=403)  # 提供明确角色提示。
    tomorrow = (timezone.localtime() + timedelta(days=1)).replace(hour=lab.open_time.hour, minute=lab.open_time.minute, second=0, microsecond=0)  # 提供合法开放时刻作为初值。
    form = ReservationForm(request.POST if request.method == 'POST' else None, initial={'start_at': tomorrow, 'end_at': min(tomorrow + timedelta(hours=1), tomorrow.replace(hour=lab.close_time.hour, minute=lab.close_time.minute)), 'attendees': 1, 'request_key': uuid4()})  # 空POST也绑定并显示必填错误。
    if request.method == 'POST':  # 只有提交请求尝试写入。
        if form.is_valid():  # 先完成输入格式校验。
            try:  # 处理服务端业务拒绝。
                booking, created = submit_reservation(actor=request.user, lab_id=lab.pk, **form.cleaned_data)  # 调用唯一申请入口。
            except DomainError as error:  # 在当前表单展示原因。
                form.add_error(None, str(error))  # 保留已填写内容。
            else:  # 事务成功后才显示成功。
                messages.success(request, '申请已提交，等待管理员审核。' if created else '这次提交已处理，现展示原申请。')  # 区分新申请与重试。
                return redirect('booking_detail', booking_id=booking.pk)  # 防止刷新再次POST。
        messages.error(request, '请检查以下输入或预约条件。')  # 统一表单错误提示。
    return render(request, 'labapp/form.html', {'title': '提交预约申请', 'section': 'labs', 'form': form, 'lab': lab, 'booking_form': True, 'subtitle': f'{lab.name} · 容量{lab.capacity}人', 'submit_label': '提交申请'})  # 返回申请页面。

# 记录分区：列表、详情、审核与取消。
@login_required  # 预约记录需要登录。
def bookings(request):  # 查询与分页展示预约记录。
    form = BookingFilterForm(request.GET)  # 验证组合筛选条件。
    query = visible_bookings(request.user)  # 在筛选之前限定数据归属。
    if form.is_valid():  # 只处理合法条件。
        data = form.cleaned_data  # 获取字段值。
        for field in ['lab', 'status']:  # 实验室与状态采用精确筛选。
            if data[field]:  # 忽略空条件。
                query = query.filter(**{field: data[field]})  # 应用受控字段条件。
        if data['start_date']:  # 起始日期可选。
            query = query.filter(start_at__date__gte=data['start_date'])  # 包含首日。
        if data['end_date']:  # 结束日期可选。
            query = query.filter(start_at__date__lte=data['end_date'])  # 包含最后一日。
        if request.user.is_staff and data['applicant']:  # 申请人关键词仅管理员使用。
            query = query.filter(Q(applicant__username__icontains=data['applicant']) | Q(applicant__first_name__icontains=data['applicant']))  # 查询姓名或账号。
    params = request.GET.copy()  # 保留分页时的筛选条件。
    params.pop('page', None)  # 防止重复页码。
    page = Paginator(query, 20).get_page(request.GET.get('page'))  # 稳健处理空或非法页码。
    return render(request, 'labapp/bookings.html', {'title': '预约记录' if request.user.is_staff else '我的预约', 'section': 'bookings', 'form': form, 'page': page, 'query_string': params.urlencode()})  # 返回有归属限制的列表。

@login_required  # 详情访问需要登录。
def booking_detail(request, booking_id):  # 查看有权访问的单条记录。
    booking = get_object_or_404(visible_bookings(request.user), pk=booking_id)  # 他人编号统一返回404。
    return render(request, 'labapp/booking_detail.html', {'title': f'预约 #{booking.pk:04d}', 'section': 'bookings', 'booking': booking})  # 展示状态与审核证据。

@manager_required  # 审核只对管理员开放。
@require_POST  # GET不能改变业务状态。
def review_booking(request, booking_id):  # 接收通过或拒绝请求。
    get_object_or_404(Reservation, pk=booking_id)  # 无效编号返回404。
    decision = request.POST.get('decision', '')  # 读取受控审核结果。
    try:  # 处理非法结果和当前状态变化。
        if decision not in ['approve', 'reject']:  # 不接受任意字符串作为通过。
            raise DomainError('INVALID_REVIEW', '请选择通过或拒绝。')  # 返回明确输入错误。
        review_reservation(request.user, booking_id, decision == 'approve', request.POST.get('reason', ''))  # 调用真实审核事务。
        messages.success(request, '审核结果已保存。')  # 完整事务成功后反馈。
    except DomainError as error:  # 将业务拒绝显示在详情。
        messages.error(request, str(error))  # 保留具体原因。
    return redirect('booking_detail', booking_id=booking_id)  # 重新读取最终状态。

@login_required  # 取消至少需要有效会话。
@require_POST  # 限制修改请求方式。
def cancel_booking(request, booking_id):  # 执行开始前取消。
    get_object_or_404(visible_bookings(request.user), pk=booking_id)  # 在调用服务前限制记录归属。
    try:  # 处理截止时间与状态竞争。
        if request.POST.get('confirm_cancel') != 'yes':  # 服务端也要求明确确认取消意图。
            raise DomainError('INVALID_CONFIRMATION', '请先确认取消此预约，再提交。')  # 未确认时不调用写入服务。
        cancel_reservation(request.user, booking_id)  # 执行唯一取消事务。
        messages.success(request, '预约已取消，原时段已释放。')  # 只在保存成功后提示。
    except DomainError as error:  # 显示实际拒绝原因。
        messages.error(request, str(error))  # 不报告虚假成功。
    return redirect('booking_detail', booking_id=booking_id)  # 展示最终状态。

# 管理分区：维护页复用同一业务规则。
@manager_required  # 实验室维护列表需要管理员。
def manage_labs(request):  # 展示包括停用在内的所有资源。
    return render(request, 'labapp/manage_labs.html', {'title': '实验室管理', 'section': 'manage_labs', 'labs': Lab.objects.all()})  # 数据维护入口。

@manager_required  # 新建和修改同样检查管理角色。
def edit_lab(request, lab_id=None):  # 管理员维护资源。
    lab = get_object_or_404(Lab, pk=lab_id) if lab_id is not None else None  # 读取候选资源。
    form = LabForm(request.POST if request.method == 'POST' else None, instance=lab)  # 按请求方法绑定，保留空POST的必填提示。
    if request.method == 'POST' and form.is_valid():  # 仅合法POST执行保存。
        try:  # 维护服务仍需保护已有预约。
            save_lab(request.user, lab_id, form.cleaned_data)  # 校验并原子保存。
        except DomainError as error:  # 资源保护失败返回表单。
            form.add_error(None, str(error))  # 显示兼容性说明。
        else:  # 写入完成后跳转。
            messages.success(request, '实验室信息已保存。')  # 提示真实结果。
            return redirect('manage_labs')  # 返回资源列表。
    return render(request, 'labapp/form.html', {'title': '修改实验室' if lab else '新增实验室', 'section': 'manage_labs', 'form': form, 'submit_label': '保存实验室'})  # 返回统一编辑页。

@manager_required  # 账号管理列表需要管理角色。
def accounts(request):  # 展示账号状态。
    return render(request, 'labapp/accounts.html', {'title': '账号管理', 'section': 'accounts', 'accounts': User.objects.order_by('username')})  # 不向页面提供密码散列。

@manager_required  # 账号维护只能由管理员执行。
def edit_account(request, account_id=None):  # 创建、修改或停用用户。
    account = get_object_or_404(User, pk=account_id) if account_id is not None else None  # 读取已有账号。
    initial = {field: getattr(account, field) for field in ['username', 'first_name', 'is_staff', 'is_active']} if account else {'is_active': True}  # 密码不回填。
    form = AccountForm(request.POST if request.method == 'POST' else None, initial=initial)  # 空提交也执行字段校验。
    if request.method == 'POST' and form.is_valid():  # 格式正确时调用业务服务。
        try:  # 处理密码与自身保护规则。
            saved_account = save_account(request.user, account_id, form.cleaned_data)  # 原子保存账号和维护记录。
        except DomainError as error:  # 回显业务校验失败。
            form.add_error(None, str(error))  # 保留字段输入。
        else:  # 保存完成后跳转。
            if saved_account.pk == request.user.pk and form.cleaned_data['password']:  # 仅对本人实际修改密码更新会话。
                update_session_auth_hash(request, saved_account)  # 轮换会话标识并使用新密码验证值。
            messages.success(request, '账号信息已保存。')  # 返回真实结果。
            return redirect('accounts')  # 返回维护列表。
    return render(request, 'labapp/form.html', {'title': '修改账号' if account else '新增账号', 'section': 'accounts', 'form': form, 'submit_label': '保存账号'})  # 返回统一编辑页。

# 统计和审计分区：只读展示，业务与数据库实现细节不进入产品页面。
@login_required  # 统计需要有效身份。
def statistics(request):  # 展示当前角色对应范围的统计。
    today = timezone.localdate()  # 读取实际日期。
    start, end = today.replace(day=1), today.replace(day=calendar.monthrange(today.year, today.month)[1])  # 默认当前月。
    form = StatisticsForm(request.GET or {'start_date': start, 'end_date': end})  # 验证日期输入。
    summary = None  # 错误范围不展示误导性结果。
    if form.is_valid():  # 仅有效字段进行汇总。
        try:  # 处理日期顺序错误。
            summary = summarize(request.user, **form.cleaned_data)  # 服务强制本人或管理范围。
        except DomainError as error:  # 将业务错误绑定表单。
            form.add_error(None, str(error))  # 页面显示说明。
    return render(request, 'labapp/statistics.html', {'title': '预约统计', 'section': 'statistics', 'form': form, 'summary': summary})  # 返回只读统计页。

@manager_required  # 关键操作记录含管理信息，只对管理员开放。
def audit_events(request):  # 查询真实操作时间与操作者。
    page = Paginator(AuditEvent.objects.select_related('actor'), 25).get_page(request.GET.get('page'))  # 分页加载记录。
    return render(request, 'labapp/audit.html', {'title': '操作记录', 'section': 'audit', 'page': page})  # 返回只读记录列表。

# 异常展示分区：统一恢复入口，详细诊断进入本地日志。
def not_found(request, exception):  # 处理缺失页面或受保护对象。
    return render(request, 'labapp/error.html', {'title': '未找到页面', 'error': '页面不存在，或你无权查看这条记录。'}, status=404)  # 不透露他人的数据是否存在。

def server_error(request):  # 处理未预期的服务端异常。
    return render(request, 'labapp/error.html', {'title': '暂时无法完成操作', 'error': '请稍后重试；如问题持续，请联系管理员。'}, status=500)  # 保留正确的错误响应状态。
