# 标准Web应用入口。
import os  # 设置配置模块。
from django.core.wsgi import get_wsgi_application  # 构建框架WSGI应用。
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')  # 指定项目配置。
application = get_wsgi_application()  # 提供服务器可调用对象。
