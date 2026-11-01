# 逻辑分区：路径、运行环境及本地配置。
import os  # 从进程环境读取可选配置。
import sys  # 区分测试启动与正常运行。
from pathlib import Path  # 构造可移植路径。
BASE_DIR = Path(__file__).resolve().parents[2]  # 根目录位于src的上一级。
RUNTIME = BASE_DIR / 'runtime'  # 本地数据集中保存在runtime。
RUNTIME.mkdir(parents=True, exist_ok=True)  # 首次运行时准备本地数据目录。
SECRET_KEY = os.environ.get('LAB_BOOKING_SECRET', 'local-course-demo-key-2026-change-for-public-hosting')  # 本地演示默认值可被进程配置替换。
DEBUG = os.environ.get('LAB_BOOKING_DEBUG', '0') == '1'  # 默认使用友好错误页；开发时可显式开启调试。
ALLOWED_HOSTS = ['127.0.0.1', 'localhost', 'testserver']  # 默认只允许本地与测试访问。
INSTALLED_APPS = ['django.contrib.auth', 'django.contrib.contenttypes', 'django.contrib.sessions', 'django.contrib.messages', 'django.contrib.staticfiles', 'labapp']  # 注册必需组件与业务应用。
MIDDLEWARE = ['django.middleware.security.SecurityMiddleware', 'django.contrib.sessions.middleware.SessionMiddleware', 'django.middleware.common.CommonMiddleware', 'django.middleware.csrf.CsrfViewMiddleware', 'django.contrib.auth.middleware.AuthenticationMiddleware', 'django.contrib.messages.middleware.MessageMiddleware', 'django.middleware.clickjacking.XFrameOptionsMiddleware']  # 启用会话、权限相关基础设施与CSRF防护。
ROOT_URLCONF = 'config.urls'  # 使用项目路由表。
TEMPLATES = [{'BACKEND': 'django.template.backends.django.DjangoTemplates', 'DIRS': [], 'APP_DIRS': True, 'OPTIONS': {'context_processors': ['django.template.context_processors.request', 'django.contrib.auth.context_processors.auth', 'django.contrib.messages.context_processors.messages']}}]  # 从应用加载页面并提供当前用户与提示。
WSGI_APPLICATION = 'config.wsgi.application'  # 暴露标准Web应用接口。

# 逻辑分区：数据库采用短IMMEDIATE写事务和专用测试文件。
DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': os.environ.get('LAB_BOOKING_DB', str(RUNTIME / 'db.sqlite3')), 'OPTIONS': {'timeout': 8, 'transaction_mode': 'IMMEDIATE'}, 'TEST': {'NAME': str(RUNTIME / 'test-suite.sqlite3')}}}  # 文件测试数据库支持独立连接的并发验证。
LANGUAGE_CODE = 'zh-hans'  # 页面和框架校验信息使用中文。
TIME_ZONE = 'Asia/Shanghai'  # 用户输入与展示使用北京时间。
USE_I18N = True  # 启用框架消息翻译。
USE_TZ = True  # 数据库时间保持可比较的时区信息。
STATIC_URL = '/static/'  # 本地静态资源URL。
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'  # 使用明确的自增主键类型。
LOGIN_URL = '/login/'  # 未登录访问跳转到登录页。
LOGIN_REDIRECT_URL = '/labs/'  # 登录后进入实验室查询。
LOGOUT_REDIRECT_URL = '/login/'  # 退出后回到登录页。
AUTH_PASSWORD_VALIDATORS = [{'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 8}}, {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'}, {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'}]  # 管理员设置密码时执行基本强度校验。
SESSION_COOKIE_HTTPONLY = True  # 页面脚本不能直接读取会话Cookie。
SESSION_COOKIE_SAMESITE = 'Lax'  # 减少跨站请求携带会话的机会。
SECURE_CONTENT_TYPE_NOSNIFF = True  # 要求浏览器遵循响应内容类型。
LOGGING = {'version': 1, 'disable_existing_loggers': False, 'handlers': {'file': {'class': 'logging.handlers.RotatingFileHandler', 'filename': str(RUNTIME / 'system.log'), 'maxBytes': 500000, 'backupCount': 3, 'encoding': 'utf-8'}}, 'loggers': {'django.request': {'handlers': ['file'], 'level': 'WARNING', 'propagate': False}}}  # 将请求异常集中保存并限制日志大小。
if 'test' in sys.argv:  # 仅在框架测试命令运行期间替换散列算法。
    PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']  # 正常应用仍使用框架默认的强密码散列。
