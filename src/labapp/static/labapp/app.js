// 逻辑分区：预约表单即时提示，最终规则仍由后端校验。
document.querySelectorAll('form[data-booking]').forEach((form) => { // 只增强预约输入。
  const start = form.querySelector('[name="start_at"]'); // 找到开始时间。
  const end = form.querySelector('[name="end_at"]'); // 找到结束时间。
  const check = () => { // 检查同日与时间顺序。
    const invalid = start.value && end.value && (start.value >= end.value || start.value.slice(0, 10) !== end.value.slice(0, 10)); // 比较标准格式的本地时间字符串。
    end.setCustomValidity(invalid ? '结束时间应晚于开始时间，并在同一天。' : ''); // 显示或清除浏览器校验消息。
  }; // 输入校验函数结束。
  start.addEventListener('input', check); // 修改开始时重新检查。
  end.addEventListener('input', check); // 修改结束时重新检查。
  check(); // 页面回显输入时立即核对已有时间。
}); // 预约表单增强结束。

// 逻辑分区：提交期间的按钮反馈；取消确认由页面必选框完成。
document.querySelectorAll('form').forEach((form) => { // 为真实HTML表单添加交互。
  form.addEventListener('submit', () => { // 在浏览器原生校验成功后处理提交。
    window.setTimeout(() => { // 等待浏览器序列化被点击按钮的name和value。
      form.querySelectorAll('button[type="submit"]').forEach((button) => { // 防止连续点击产生多次交互。
        if (!button.disabled) { // 不覆盖服务端预先禁用的审批按钮。
          button.dataset.submitDisabled = 'true'; // 标记只由提交反馈临时禁用的按钮。
          button.disabled = true; // 后端幂等与状态校验仍为最终依据。
        } // 临时状态标记结束。
      }); // 提交按钮反馈结束。
    }, 0); // 不影响原生表单携带审核结论。
  }); // 提交监听结束。
}); // 表单增强结束。

// 逻辑分区：返回缓存页面时恢复可交互状态。
window.addEventListener('pageshow', () => { // 浏览器前进后退缓存恢复时也触发。
  document.querySelectorAll('button[data-submit-disabled]').forEach((button) => { // 只恢复本脚本临时禁用的按钮。
    button.disabled = false; // 允许用户修改筛选或再次提交表单。
    delete button.dataset.submitDisabled; // 清理临时标识，保留原本因业务状态禁用的按钮。
  }); // 按钮恢复结束。
}); // 页面恢复监听结束。
