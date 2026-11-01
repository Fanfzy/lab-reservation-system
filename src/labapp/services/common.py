# 公共分区：稳定业务错误、角色检查与短写事务。
from contextlib import contextmanager  # 包装统一事务边界。
from django.db import OperationalError, transaction  # 处理SQLite等待失败与原子提交。
from labapp.models import AuditEvent  # 在同一业务事务内保存操作记录。

class DomainError(Exception):  # 将业务拒绝与程序异常区分。
    def __init__(self, code, message):  # 同时提供机器标识和中文提示。
        self.code = code  # 供测试和请求层判断错误类别。
        super().__init__(message)  # 将中文消息提供给界面。

def require_user(actor):  # 检查身份和账号当前有效性。
    if not actor.is_authenticated:  # 匿名对象不能查询当前账号。
        raise DomainError('FORBIDDEN', '请使用有效账号登录。')  # 明确身份错误。
    actor.refresh_from_db(fields=['is_active', 'is_staff'])  # 重新读取当前账号状态与权限。
    if not actor.is_active:  # 禁止停用账号操作。
        raise DomainError('FORBIDDEN', '请使用有效账号登录。')  # 返回明确身份错误。

def require_manager(actor):  # 检查管理业务权限。
    require_user(actor)  # 先验证账号有效性。
    if not actor.is_staff:  # is_staff在本项目对应管理员角色。
        raise DomainError('FORBIDDEN', '只有管理员可以执行此操作。')  # 服务端阻止越权。

@contextmanager  # 将事务上下文复用于所有资源状态写入。
def write_transaction():  # 获得IMMEDIATE事务后再读取业务条件。
    try:  # 将数据库忙转换为稳定业务提示。
        with transaction.atomic():  # 由SQLite配置在事务开始时竞争写锁。
            yield  # 在短事务内执行校验、主记录和操作记录保存。
    except OperationalError as error:  # 检查数据库层运行异常。
        if 'locked' in str(error).lower() or 'busy' in str(error).lower():  # 仅转换锁等待失败。
            raise DomainError('DATABASE_BUSY', '系统正在处理其他提交，请稍后重试；本次未成功保存。') from error  # 不把失败报告为成功。
        raise  # 其他异常保留原始诊断信息。

def audit(actor, action, subject, detail=''):  # 统一记录实际业务动作。
    return AuditEvent.objects.create(actor=actor, action=action, subject=str(subject), detail=detail)  # 调用者事务保证与主记录一致。
