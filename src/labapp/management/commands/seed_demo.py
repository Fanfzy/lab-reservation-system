# 演示初始化：创建缺失样本，已有账号密码和业务数据保持原样。
from datetime import timedelta, time  # 生成明天的时段及每日开放时间。
from uuid import uuid5, NAMESPACE_URL  # 为固定样本生成稳定标识。
from django.contrib.auth.models import User  # 引导创建首个管理员。
from django.core.management.base import BaseCommand, CommandError  # 接入框架管理命令。
from django.utils import timezone  # 使用当前日期和北京时间。
from labapp.models import Lab, Reservation  # 检查现有业务数据。
from labapp.services.common import audit, write_transaction, DomainError  # 统一初始化事务与记录。
from labapp.services.accounts import save_account  # 创建其他演示账号。
from labapp.services.labs import save_lab  # 创建示例资源。
from labapp.services.reservations import submit_reservation, review_reservation, cancel_reservation  # 样本通过实际业务入口创建。
PASSWORD = 'LabDemo!2026'  # 仅供明确标注的课程演示账号使用。

class Command(BaseCommand):  # 提供可重复运行的演示初始化命令。
    help = '创建演示账号、资源和样本；不清空或覆盖已有业务数据。'  # 说明命令边界。
    def handle(self, *args, **options):  # 执行受控初始化。
        new_users = []  # 只记录本次真正创建的账号。
        try:  # 业务错误转换为管理命令错误。
            with write_transaction():  # 在一个原子事务内创建首次演示数据。
                manager, created = User.objects.get_or_create(username='admin01', defaults={'first_name': '实验室管理员', 'is_staff': True, 'is_active': True})  # 仅引导创建缺失管理员。
                if created:  # 首次创建时才设置演示密码。
                    manager.set_password(PASSWORD)  # 数据库保存密码散列。
                    manager.save()  # 保存有效登录信息。
                    new_users.append(manager.username)  # 记录实际新增管理员。
                if not manager.is_staff or not manager.is_active:  # 不擅自升级或启用已有同名账号。
                    raise CommandError('已有admin01不是启用管理员，请先由现有管理员处理账号。')  # 返回可操作说明。
                people = []  # 收集样本申请人。
                for username, name in [('user01', '张同学'), ('user02', '李同学')]:  # 创建两个独立申请人。
                    user = User.objects.filter(username=username).first()  # 优先使用已有同名账号。
                    if user is None:  # 只创建缺失账号。
                        user = save_account(manager, None, dict(username=username, first_name=name, password=PASSWORD, is_staff=False, is_active=True))  # 通过正常管理业务创建。
                        new_users.append(username)  # 记录实际新增申请人。
                    people.append(user)  # 为预约样本提供操作者。
                resources = [('AUTO-301', '自动控制实验室', '实验楼 A · 301', 24, 'PLC实验台、直流电机、过程控制装置', True), ('ELEC-302', '电路与电子实验室', '实验楼 A · 302', 32, '示波器、信号发生器、模拟电路实验箱', True), ('COMP-401', '计算机与仿真实验室', '实验楼 B · 401', 40, '工作站、MATLAB仿真平台、网络实验设备', True), ('SENS-303', '传感器实验室', '实验楼 A · 303', 16, '传感器实验台、数据采集装置', False)]  # 定义三间可用及一间停用资源。
                labs = []  # 收集按编码定位的资源。
                for code, name, location, capacity, equipment, active in resources:  # 创建缺失资源。
                    lab = Lab.objects.filter(code=code).first()  # 保留已有维护信息。
                    if lab is None:  # 不覆盖用户已修改的资源。
                        lab = save_lab(manager, None, dict(code=code, name=name, location=location, capacity=capacity, equipment=equipment, description='请按预约时段使用设备，实验结束后恢复现场。', open_time=time(8), close_time=time(22), is_active=active))  # 通过维护服务保存。
                    labs.append(lab)  # 为样本选定资源。
                if not Reservation.objects.exists():  # 仅首次空业务库创建预约样本。
                    base = (timezone.localtime() + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)  # 样本位于明天。
                    samples = [(people[0], labs[0], 0, 1, 'PID控制实验', 'pending'), (people[1], labs[0], 1, 2, 'PLC顺序控制实验', 'approved'), (people[0], labs[1], 4, 6, '运算放大器实验', 'rejected'), (people[1], labs[2], 5, 7, '控制系统仿真实验', 'cancelled')]  # 用四笔数据展示全部状态。
                    for index, (user, lab, begin, finish, purpose, state) in enumerate(samples):  # 逐笔经过真实业务入口。
                        booking, _ = submit_reservation(user, lab.pk, base + timedelta(hours=begin), base + timedelta(hours=finish), purpose, 4, uuid5(NAMESPACE_URL, f'lab-demo/{base.date()}/{index}'))  # 统一申请与冲突规则。
                        if state in ['approved', 'rejected']:  # 两种样本需要实际审核。
                            review_reservation(manager, booking.pk, state == 'approved', '教学安排确认' if state == 'approved' else '请补充实验准备后重新申请')  # 保存审核证据。
                        if state == 'cancelled':  # 取消样本通过同一取消服务。
                            cancel_reservation(user, booking.pk)  # 保存释放资源记录。
                    audit(manager, 'DEMO_INIT', '演示数据', '首次创建四种预约状态样本；样本日期=' + str(base.date()))  # 标注样本来源。
        except DomainError as error:  # 发生不兼容已有数据时保持原子回滚。
            raise CommandError(str(error)) from error  # 不部分覆盖业务数据。
        names = ' / '.join(new_users) if new_users else '无（已有账号保持原样）'  # 区分首次和重复运行。
        self.stdout.write(self.style.SUCCESS(f'演示初始化完成。新增账号：{names}；仅新账号初始密码为{PASSWORD}。'))  # 提供准确的实际结果。
