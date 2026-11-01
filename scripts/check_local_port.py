# 启动检查分区：仅使用标准库核对本机端口，不安装依赖或修改数据。
import socket  # 建立短期探测套接字。
import sys  # 读取启动脚本传入的端口。

def ensure_local_port_available(value):  # 验证端口并在探测结束时释放句柄。
    try:  # 将启动变量转换为整数。
        port = int(value)  # 小数或非数字输入不能进入服务启动。
    except (TypeError, ValueError) as error:  # 统一输入格式错误。
        raise ValueError('端口必须是1至65535之间的整数') from error  # 给出可修改的提示。
    if not 1 <= port <= 65535:  # 0会随机分配端口，不适合作为固定浏览器入口。
        raise ValueError('端口必须是1至65535之间的整数')  # 拒绝越界配置。
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:  # 自动关闭探测句柄。
        if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):  # Windows允许地址复用，需显式独占探测。
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)  # 拒绝已被其他服务使用的地址。
        probe.bind(('127.0.0.1', port))  # 其他平台默认不设置地址复用，同样检查本机占用。
    return port  # 返回已检查的数字，不保留监听服务。

# 命令入口分区：返回状态由CMD决定是否继续启动。
if __name__ == '__main__':  # 作为独立启动检查调用。
    try:  # 核对脚本提供的参数。
        port = ensure_local_port_available(sys.argv[1] if len(sys.argv) == 2 else '')  # 参数缺失或数量错误时拒绝。
    except (ValueError, OSError) as error:  # 格式错误与占用均属于可恢复启动问题。
        print(f'启动端口检查失败：{error}；请关闭已有服务，或更换 LAB_BOOKING_PORT。')  # 保留实际原因和下一步。
        raise SystemExit(1)  # 阻止重复启动并返回明确失败状态。
    print('启动前端口检查通过，随后检查数据库并启动服务。')  # 中文由Python输出，避免CMD解析中文源文本。
    print(f'服务启动成功后，浏览器访问：http://127.0.0.1:{port}/')  # 地址使用实际检查通过的端口。
    print('请保持此窗口打开；在此窗口按 Ctrl+C 可停止服务。')  # 说明服务窗口的作用。
    print('下方 development server 提示表示本机课程演示模式，不是报错。')  # 解释正常框架提示。
