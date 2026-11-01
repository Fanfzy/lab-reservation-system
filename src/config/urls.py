# 路由分区：命名入口连接页面、认证和业务操作。
from django.contrib.auth.views import LoginView, LogoutView  # 使用框架会话登录与POST退出。
from django.urls import path  # 注册受控请求路径。
from django.views.generic import RedirectView  # 默认进入实验室查询。
from labapp import views  # 连接薄请求处理层。
handler404 = views.not_found  # 对不存在或无权读取的对象给出友好提示。
handler500 = views.server_error  # 请求异常不向用户暴露调试堆栈。
urlpatterns = [  # 页面和业务操作拥有稳定命名。
    path('', RedirectView.as_view(pattern_name='labs', permanent=False)),  # 根路径跳转查询页。
    path('login/', LoginView.as_view(template_name='labapp/login.html'), name='login'),  # 框架检查账号与密码。
    path('logout/', LogoutView.as_view(), name='logout'),  # POST退出会话。
    path('labs/', views.labs, name='labs'),  # 资源筛选列表。
    path('labs/<int:lab_id>/', views.lab_detail, name='lab_detail'),  # 资源与占用详情。
    path('labs/<int:lab_id>/book/', views.book_lab, name='book_lab'),  # 预约申请。
    path('bookings/', views.bookings, name='bookings'),  # 本人或全量记录。
    path('bookings/<int:booking_id>/', views.booking_detail, name='booking_detail'),  # 有归属限制的详情。
    path('bookings/<int:booking_id>/review/', views.review_booking, name='review_booking'),  # 管理审核写入。
    path('bookings/<int:booking_id>/cancel/', views.cancel_booking, name='cancel_booking'),  # 开始前取消。
    path('manage/labs/', views.manage_labs, name='manage_labs'),  # 实验室维护列表。
    path('manage/labs/new/', views.edit_lab, name='new_lab'),  # 创建资源。
    path('manage/labs/<int:lab_id>/', views.edit_lab, name='edit_lab'),  # 修改资源。
    path('manage/accounts/', views.accounts, name='accounts'),  # 账号列表。
    path('manage/accounts/new/', views.edit_account, name='new_account'),  # 创建账号。
    path('manage/accounts/<int:account_id>/', views.edit_account, name='edit_account'),  # 修改账号。
    path('statistics/', views.statistics, name='statistics'),  # 日期范围统计。
    path('manage/audit/', views.audit_events, name='audit'),  # 关键操作记录。
]  # 保持默认框架后台未暴露，业务维护统一通过服务入口。
