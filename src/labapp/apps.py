# 应用注册信息。
from django.apps import AppConfig  # 导入框架应用配置基类。
class LabappConfig(AppConfig):  # 注册课程设计业务应用。
    default_auto_field = 'django.db.models.BigAutoField'  # 与项目默认主键保持一致。
    name = 'labapp'  # 使用明确的应用包名。
    verbose_name = '实验室预约管理'  # 在模型信息中显示中文名称。
