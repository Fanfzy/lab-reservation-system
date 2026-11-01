from pathlib import Path  # 根据脚本所在位置定位软件。
from html import escape  # 保护XML中文及类型标记。
import json  # 读取统一模型布局数据。
import xml.etree.ElementTree as ET  # 验证生成的SVG结构。
ROOT = Path(__file__).resolve().parents[1]  # 软件根目录。
OUT = ROOT/'02_系统设计'/'模型图'  # 正式模型输出位置。
LAYOUT = Path(__file__).with_name('model_layout.json')  # 数据与生成器共同交付。
INK,LINE = '#17365D','#2F75B5'  # 软件模型采用统一蓝色。
def measure(text,size):  # 估计中英文宽度以防止节点文字越界。
    return sum(size if ord(c)>255 else size*0.56 for c in text)  # 中文使用全字宽。
def text(x,y,value,size=24,anchor='middle',bold=False):  # 生成可搜索文字。
    weight=' font-weight="600"' if bold else ''  # 仅在对象标题处加粗。
    return ''.join(f'<text x="{x}" y="{y+i*(size+6)}" font-family="Microsoft YaHei" font-size="{size}" text-anchor="{anchor}" fill="{INK}"{weight}>{escape(str(v))}</text>' for i,v in enumerate(str(value).split('\n')))  # 多行标签保持靠近关系。
def render(d):  # 使用已核对的对象、端口、走线和标签生成模型。
    total=d['height']+160  # 顶部标题与底部图例各留80像素。
    parts=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{d["width"]}" height="{total}" viewBox="0 0 {d["width"]} {total}">',f'<title>{escape(d["title"])}</title>',f'<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L7,4 L0,8" fill="none" stroke="{LINE}" stroke-width="1.4"/></marker></defs>','<rect width="100%" height="100%" fill="white"/>',text(20,31,d['title'],28,'start',True),text(20,62,d['purpose'],20,'start'),'<g transform="translate(0,80)">']  # 独立可打开的SVG文档。
    for f in d['frames']:  # 范围框先于对象和关系绘制。
        dashed=' stroke-dasharray="7 5"' if f.get('dashed') else ''  # 事务使用虚线范围。
        parts.append(f'<rect x="{f["x"]}" y="{f["y"]}" width="{f["w"]}" height="{f["h"]}" fill="none" stroke="{LINE}" stroke-width="1.2"{dashed}/>')  # 外框不填色。
        parts.append(text(f.get('labelX',f['x']+f['w']/2),f.get('labelY',f['y']+27),f['title'],21))  # 框名与线条分开。
    for e in d['edges']:  # 路线来自固定通道，不重新猜测连接。
        marker=' marker-end="url(#arrow)"' if e['arrow'] else ''  # 只在有方向的模型中使用箭头。
        dashed=' stroke-dasharray="7 6"' if e['dashed'] else ''  # 生命线和返回具有各自图例。
        points=' '.join(f'{x},{y}' for x,y in e['points'])  # 显式保留每个折点。
        parts.append(f'<polyline points="{points}" fill="none" stroke="{LINE}" stroke-width="1.7"{marker}{dashed}/>')  # 避开对象正文。
    for n in d['nodes']:  # 按图种使用对应符号。
        x,y,w,h=n['x'],n['y'],n['w'],n['h']  # 对象边界。
        kind=n['kind']; fill='#D9EAF7' if n['tone']=='primary' else '#F1F5FA' if n['tone']=='muted' else '#F5F9FD'  # 配色辅助说明。
        if kind in ['start','end']:  # 活动图开始和结束。
            radius=9 if kind=='end' else 8  # 靶心内圆与开始点。
            parts.append(f'<circle cx="{x+w/2}" cy="{y+h/2}" r="{radius}" fill="{INK}"/>')  # 实心圆。
            if kind=='end': parts.append(f'<circle cx="{x+w/2}" cy="{y+h/2}" r="14" fill="none" stroke="{INK}"/>')  # 外圈表示结束。
            continue  # 圆点不写标题。
        if kind=='actor':  # 用例参与者。
            cx=x+w/2  # 人形中心。
            parts.append(f'<circle cx="{cx}" cy="{y+10}" r="12" fill="white" stroke="{LINE}"/><path d="M{cx},{y+22} V{y+65} M{cx-29},{y+40} H{cx+29} M{cx},{y+65} L{cx-22},{y+95} M{cx},{y+65} L{cx+22},{y+95}" fill="none" stroke="{LINE}" stroke-width="2"/>')  # 标准人形。
            parts.append(text(cx,y+129,n['title'],25)); continue  # 角色名紧邻人形。
        if kind=='ellipse': parts.append(f'<ellipse cx="{x+w/2}" cy="{y+h/2}" rx="{w/2}" ry="{h/2}" fill="{fill}" stroke="{LINE}"/>')  # 用例目标。
        elif kind=='diamond': parts.append(f'<polygon points="{x+w/2},{y} {x+w},{y+h/2} {x+w/2},{y+h} {x},{y+h/2}" fill="{fill}" stroke="{LINE}"/>')  # 条件判断。
        elif kind=='store': parts.append(f'<path d="M{x+w},{y} H{x} V{y+h} H{x+w}" fill="none" stroke="{LINE}" stroke-width="1.8"/>')  # DFD开口存储。
        else: parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{12 if kind=="action" else 0}" fill="{fill}" stroke="{LINE}" stroke-width="1.5"/>')  # 实体、功能或圆角动作框。
        size=21 if kind=='class' else 24  # 普通模型字号。
        while measure(n['title'],size)>w-20 and size>18: size-=1  # 保留长标题内边距。
        if not n['lines']: parts.append(text(x+w/2,y+h/2+size*0.34,n['title'],size,'middle',kind=='box'))  # 单行居中。
        elif kind=='class':  # 类名与成员分区。
            parts.extend([text(x+w/2,y+30,n['title'],23,'middle',True),f'<line x1="{x+8}" y1="{y+43}" x2="{x+w-8}" y2="{y+43}" stroke="{LINE}"/>'])  # UML标题分隔。
            for i,v in enumerate(n['lines']):  # 属性和方法逐行保存。
                if v=='---': parts.append(f'<line x1="{x+8}" y1="{y+63+i*25}" x2="{x+w-8}" y2="{y+63+i*25}" stroke="{LINE}"/>')  # 方法区分隔。
                else: parts.append(text(x+12,y+70+i*25,v,min(21,(w-24)/measure(v,1)),'start'))  # 类型与名称不溢出。
        else:  # 一般对象显示标题和说明。
            start=y+(h-(len(n['lines'])+1)*29)/2+24  # 文字块整体居中。
            parts.append(text(x+w/2,start,n['title'],size,'middle',True))  # 对象标题。
            for i,v in enumerate(n['lines']): parts.append(text(x+w/2,start+30+i*29,v,min(23,(w-20)/measure(v,1))))  # 说明分行。
    for l in d['labels']: parts.append(text(l['x'],l['y'],l['text'],l['size'],l['anchor']))  # 标签沿已验证的近邻位置绘制。
    parts.extend(['</g>',text(20,total-32,d['legend'],19,'start'),'</svg>'])  # 完整图例和结尾。
    result='\n'.join(item+'<!-- 当前图形元素。 -->' for item in parts)+'\n'  # 为SVG逐行保存说明。
    ET.fromstring(result)  # XML格式不正确时停止生成。
    return result  # 返回当前模型。
if __name__=='__main__':  # 使用专用Conda解释器运行。
    data=json.loads(LAYOUT.read_text(encoding='utf-8'))  # 模型布局文件不引入新依赖。
    OUT.mkdir(parents=True,exist_ok=True)  # 仅创建模型输出目录。
    for d in data: (OUT/(d['name']+'.svg')).write_text(render(d),encoding='utf-8')  # 覆盖维护当前十幅正式模型。
    print(f'已生成并检查{len(data)}幅模型图')  # 报告实际数量。
