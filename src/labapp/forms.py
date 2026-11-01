# 表单分区：统一输入控件样式，不把业务权限放在浏览器中。
from django import forms  # 使用框架表单解析与字段校验。
from labapp.models import Lab, Reservation  # 为资源维护和筛选提供字段来源。

class StyledMixin:  # 复用输入框展示属性。
    def __init__(self, *args, **kwargs):  # 保留框架表单初始化约定。
        super().__init__(*args, **kwargs)  # 初始化字段与绑定数据。
        for field in self.fields.values():  # 对所有字段应用一致外观。
            field.widget.attrs['class'] = 'check-input' if isinstance(field.widget, forms.CheckboxInput) else 'field-input'  # 区分复选框和普通控件。

class ReservationForm(StyledMixin, forms.Form):  # 解析提交预约表单。
    start_at = forms.DateTimeField(label='开始时间', input_formats=['%Y-%m-%dT%H:%M'], widget=forms.DateTimeInput(format='%Y-%m-%dT%H:%M', attrs={'type': 'datetime-local'}))  # 转为带项目时区的时间。
    end_at = forms.DateTimeField(label='结束时间', input_formats=['%Y-%m-%dT%H:%M'], widget=forms.DateTimeInput(format='%Y-%m-%dT%H:%M', attrs={'type': 'datetime-local'}))  # 与开始时间采用相同精度。
    purpose = forms.CharField(label='预约用途', max_length=500, widget=forms.Textarea(attrs={'rows': 3}), help_text='说明实验内容或使用目的。')  # 限制用途长度。
    attendees = forms.IntegerField(label='参加人数', min_value=1)  # 解析合法整数，容量仍由业务层核对。
    request_key = forms.UUIDField(widget=forms.HiddenInput())  # 保存一次表单提交标识。

class LabForm(StyledMixin, forms.ModelForm):  # 管理员维护资源信息。
    class Meta:  # 明确可编辑字段和控件。
        model = Lab  # 使用实验室字段定义。
        fields = ['code', 'name', 'location', 'capacity', 'open_time', 'close_time', 'equipment', 'description', 'is_active']  # 限制管理表单范围。
        widgets = {'open_time': forms.TimeInput(format='%H:%M', attrs={'type': 'time'}), 'close_time': forms.TimeInput(format='%H:%M', attrs={'type': 'time'}), 'equipment': forms.Textarea(attrs={'rows': 3}), 'description': forms.Textarea(attrs={'rows': 3})}  # 选择适合字段的输入控件。

class AccountForm(StyledMixin, forms.Form):  # 管理员新建或更新账号。
    username = forms.CharField(label='登录账号', max_length=150)  # 最终由用户模型验证账号格式与唯一性。
    first_name = forms.CharField(label='显示姓名', max_length=150, required=False)  # 可用中文姓名展示。
    password = forms.CharField(label='设置密码', required=False, widget=forms.PasswordInput(), help_text='至少8位；修改时留空保留原密码。')  # 新建必填由业务层判断。
    is_staff = forms.BooleanField(label='管理员角色', required=False)  # 显式管理第二类角色。
    is_active = forms.BooleanField(label='账号启用', required=False, initial=True)  # 停用仍保留历史。

# 筛选分区：错误输入显示表单提示，不构造不受控查询。
class LabFilterForm(StyledMixin, forms.Form):  # 实验室查询条件。
    q = forms.CharField(label='关键词', required=False, max_length=100)  # 支持名称、编码和位置查询。
    min_capacity = forms.IntegerField(label='最低容量', required=False, min_value=1)  # 解析数字筛选条件。
    active = forms.ChoiceField(label='资源状态', required=False, choices=[('active', '可预约'), ('all', '全部'), ('disabled', '已停用')])  # 默认查看可用资源。

class DateForm(StyledMixin, forms.Form):  # 查询某一天的占用。
    date = forms.DateField(label='查看日期', widget=forms.DateInput(attrs={'type': 'date'}))  # 防止非法日期传入查询。

class BookingFilterForm(StyledMixin, forms.Form):  # 预约记录的组合筛选。
    lab = forms.ModelChoiceField(label='实验室', queryset=Lab.objects.all(), required=False, empty_label='全部实验室')  # 只允许真实资源编号。
    status = forms.ChoiceField(label='状态', required=False, choices=[('', '全部状态')] + list(Reservation.Status.choices))  # 只允许已定义状态。
    start_date = forms.DateField(label='开始日期', required=False, widget=forms.DateInput(attrs={'type': 'date'}))  # 按预约开始日期筛选。
    end_date = forms.DateField(label='结束日期', required=False, widget=forms.DateInput(attrs={'type': 'date'}))  # 包含最后一天。
    applicant = forms.CharField(label='申请人账号或姓名', required=False, max_length=150)  # 仅管理员查询中使用。
    def clean(self):  # 核对可选日期顺序。
        data = super().clean()  # 保留字段校验结果。
        if data.get('start_date') and data.get('end_date') and data['start_date'] > data['end_date']:  # 禁止反向日期范围。
            raise forms.ValidationError('开始日期不能晚于结束日期。')  # 向页面显示范围错误。
        return data  # 返回可安全用于查询的条件。

class StatisticsForm(StyledMixin, forms.Form):  # 明确统计窗口。
    start_date = forms.DateField(label='开始日期', widget=forms.DateInput(attrs={'type': 'date'}))  # 保存首日。
    end_date = forms.DateField(label='结束日期', widget=forms.DateInput(attrs={'type': 'date'}))  # 保存最后一日。
