# 账号维护：角色控制、密码散列和自身保护。
from django.contrib.auth.models import User  # 使用框架账号模型。
from django.contrib.auth.password_validation import validate_password  # 检查密码基本强度。
from django.core.exceptions import ValidationError  # 统一转换校验错误。
from labapp.services.common import DomainError, require_manager, write_transaction, audit  # 复用权限和事务。

def save_account(actor, account_id, values):  # 创建或更新有效账号。
    with write_transaction():  # 账号与操作记录同时提交。
        require_manager(actor)  # 检查当前管理员权限。
        try:  # 加载旧账号或准备新账号。
            account = User.objects.get(pk=account_id) if account_id is not None else User()  # 保留历史外键关联。
        except User.DoesNotExist as error:  # 处理不存在账号。
            raise DomainError('NOT_FOUND', '账号不存在。') from error  # 返回稳定错误。
        if account_id == actor.pk and (not values.get('is_active', True) or not values.get('is_staff', True)):  # 禁止停用或降级当前管理员。
            raise DomainError('SELF_PROTECTION', '不能停用或降级当前管理员账号，请由其他管理员处理。')  # 保留管理入口。
        for field in ['username', 'first_name', 'is_staff', 'is_active']:  # 只更新已批准字段。
            if field in values:  # 应用明确提供的值。
                setattr(account, field, values[field])  # 设置候选账号属性。
        password = values.get('password', '')  # 空密码表示保持旧密码。
        if account_id is None and not password:  # 新账号必须有可用密码。
            raise DomainError('INVALID_PASSWORD', '新建账号必须设置密码。')  # 提示必填内容。
        try:  # 同时验证密码与账号字段。
            if password:  # 设置新密码时调用强度检查。
                validate_password(password, account)  # 检查长度、常见和纯数字密码。
                account.set_password(password)  # 保存密码散列。
            account.full_clean()  # 检查用户名格式和唯一性。
        except ValidationError as error:  # 聚合校验错误。
            raise DomainError('INVALID_ACCOUNT', '；'.join(error.messages)) from error  # 向维护页面返回原因。
        account.save()  # 保存合法账号。
        audit(actor, 'USER_UPDATE' if account_id is not None else 'USER_CREATE', f'用户#{account.pk}', f'{account.username}；管理员={account.is_staff}；启用={account.is_active}')  # 操作记录不保存密码。
        return account  # 返回最新账号对象。
