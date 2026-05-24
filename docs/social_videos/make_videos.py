"""
攀升AI节点教程视频生成器 v2 — 快速版
策略：Pillow 静态切片 + FFmpeg xfade 转场，单期 < 15s
"""
import os, subprocess, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920
FONT_CJK = "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf"
FONT_LAT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
OUT  = Path("/sessions/sleepy-gracious-cray/mnt/ComfyUI-Tikpan-Pro/docs/social_videos")
TMP  = Path("/tmp/tv2")

THEMES = {
    1:(12,18,40,   99,179,255, 50,120,200),
    2:(30,18,10,  255,185,80, 200,120,30),
    3:(15,10,35,  160,100,255,100,60,200),
    4:(35,12,12,  255,100,80, 200,60,40),
    5:(10,30,15,   80,220,130, 40,160,80),
    6:(20,20,20,  200,200,255,120,100,200),
}

def th(n):
    t=THEMES[n]; return (t[0],t[1],t[2]),(t[3],t[4],t[5]),(t[6],t[7],t[8])

def _is_cjk(ch):
    cp=ord(ch)
    return any(s<=cp<=e for s,e in [
        (0x4E00,0x9FFF),(0x3400,0x4DBF),(0xF900,0xFAFF),
        (0x3000,0x303F),(0xFF00,0xFFEF),(0x3040,0x309F),(0x30A0,0x30FF),
        (0x2E80,0x2EFF),(0x2F00,0x2FDF)])

def _font(sz, ch):
    return ImageFont.truetype(FONT_CJK if _is_cjk(ch) else FONT_LAT, sz)

def fnt(sz): return ImageFont.truetype(FONT_CJK, sz)

# 双字体绘制：Latin 用 DejaVu，CJK 用 Droid
def dtext(draw, text, x, y, sz, fill, shadow=False):
    cx=x
    for ch in text:
        f=_font(sz,ch)
        if shadow: draw.text((cx+2,y+2),ch,font=f,fill=(0,0,0,80))
        draw.text((cx,y),ch,font=f,fill=fill)
        bb=f.getbbox(ch); cx+=bb[2]-bb[0]
    return cx-x  # returns total width

def dtextw(text, sz):
    w=0
    for ch in text:
        f=_font(sz,ch); bb=f.getbbox(ch); w+=bb[2]-bb[0]
    return w

def ctext(draw, text, cy_center, sz, fill, maxw=940, shadow=True):
    """居中双字体多行文字"""
    # 分行
    raw_lines=text.split("\n"); lines=[]; mw=maxw
    for raw in raw_lines:
        line=""; lw=0
        for ch in raw:
            chw=_font(sz,ch).getbbox(ch)[2]-_font(sz,ch).getbbox(ch)[0]
            if lw+chw<=mw: line+=ch; lw+=chw
            else:
                if line: lines.append(line)
                line=ch; lw=chw
        lines.append(line)
    lh=sz+14; total=len(lines)*lh; y=cy_center-total//2
    for ln in lines:
        lw=dtextw(ln,sz); x=(W-lw)//2
        if shadow: dtext(draw,ln,x+2,y+2,sz,(0,0,0,80))
        dtext(draw,ln,x,y,sz,fill)
        y+=lh

def grad(img, c1, c2):
    d=ImageDraw.Draw(img)
    for y in range(H):
        t=y/H; r=int(c1[0]+(c2[0]-c1[0])*t); g=int(c1[1]+(c2[1]-c1[1])*t); b=int(c1[2]+(c2[2]-c1[2])*t)
        d.line([(0,y),(W,y)],fill=(r,g,b))

def rrect(d, x0,y0,x1,y1, r, fill):
    d.rectangle([x0+r,y0,x1-r,y1],fill=fill)
    d.rectangle([x0,y0+r,x1,y1-r],fill=fill)
    for cx,cy in [(x0,y0),(x1-2*r,y0),(x0,y1-2*r),(x1-2*r,y1-2*r)]:
        d.ellipse([cx,cy,cx+2*r,cy+2*r],fill=fill)

def dots(d, ac):
    for x in range(0,W,100):
        for y in range(0,H,100):
            d.ellipse([x-2,y-2,x+2,y+2],fill=(*ac,30))

def tag(d, text, x, y, sz, bg):
    """渲染标签按钮（双字体）"""
    tw=dtextw(text,sz); th2=sz+4; px,py=22,10
    rrect(d,x,y,x+tw+px*2,y+th2+py*2,16,bg)
    dtext(d,text,x+px,y+py,sz,(255,255,255))

def make_slide(ep, slide_idx, slide_type, content, theme_id):
    bg,ac,tg=th(theme_id)
    img=Image.new("RGB",(W,H))
    bg2=tuple(min(255,c+20) for c in bg)
    grad(img,bg2,bg)
    d=ImageDraw.Draw(img)
    dots(d,ac)

    if slide_type=="intro":
        title,subtitle=content
        for i in range(4):
            d.line([(80,70+i*16),(W-80,70+i*16)],fill=(*ac,100-i*22),width=1)
        tag(d,f"第 {ep:02d} 期",60,140,34,tg)
        ctext(d,title,H//2-80,76,(255,255,255),maxw=920)
        ctext(d,subtitle,H//2+120,46,ac,maxw=880)
        ctext(d,"攀升AI  x  ComfyUI",H-180,38,(*ac,160),maxw=800)
        d.line([(120,H-220),(W-120,H-220)],fill=(*ac,80),width=1)

    elif slide_type=="section":
        title,points=content
        d.rectangle([0,110,W,280],fill=tuple(c//4 for c in ac))
        ctext(d,title,195,56,(255,255,255),maxw=920)
        sz=44; y=330; lh=100
        icons=["◆","◈","▸","◉","◆","◈"]
        for ic,pt in zip(icons,points):
            dtext(d,ic,70,y,sz,ac)
            # 逐字换行
            ln=""; lw=0; mw=800; lines=[]
            for ch in pt:
                chw=_font(sz,ch).getbbox(ch)[2]-_font(sz,ch).getbbox(ch)[0]
                if lw+chw<=mw: ln+=ch; lw+=chw
                else: lines.append(ln); ln=ch; lw=chw
            lines.append(ln)
            for j,l in enumerate(lines):
                dtext(d,l,150,y+j*(sz+8),sz,(255,255,255))
            y+=len(lines)*(sz+8)+40
        ctext(d,"攀升AI  x  ComfyUI",H-80,28,(*ac,90),maxw=700)

    elif slide_type=="flow":
        title,steps=content
        ctext(d,title,200,54,(255,255,255),maxw=900)
        rrect(d,60,280,W-60,280+len(steps)*90+60,22,tuple(max(0,c-6) for c in bg))
        d.rounded_rectangle([60,280,W-60,280+len(steps)*90+60],radius=22,outline=(*ac,120),width=2)
        for i,s in enumerate(steps):
            col=ac if ("↓" in s or "→" in s or "A " in s or "B " in s or "C " in s or "D " in s) else (255,255,255)
            dtext(d,s,100,300+i*90,40,col)
        ctext(d,"攀升AI  x  ComfyUI",H-80,28,(*ac,90),maxw=700)

    elif slide_type=="step":
        num,tot,title,desc=content
        d.rectangle([0,0,8,H],fill=ac)
        tag(d,f"Step {num} / {tot}",60,110,36,tg)
        cx=W//2; cy=360; r=50
        d.ellipse([cx-r,cy-r,cx+r,cy+r],outline=ac,width=4)
        ns=str(num); nw=dtextw(ns,56); nh=56
        dtext(d,ns,cx-nw//2,cy-nh//2,56,ac)
        ctext(d,title,560,64,(255,255,255),maxw=900)
        ctext(d,desc,750,42,ac,maxw=900)
        ctext(d,"攀升AI  x  ComfyUI",H-80,28,(*ac,90),maxw=700)

    elif slide_type=="tip":
        title,tips=content
        rrect(d,W//2-90,120,W//2+90,280,40,(*tg,200))
        ctext(d,"TIP",200,60,(255,255,255),maxw=200)
        ctext(d,title,360,58,(255,255,255),maxw=920)
        d.line([(100,430),(W-100,430)],fill=ac,width=2)
        sz=42; y=460
        for tip in tips:
            d.rectangle([60,y+4,72,y+sz-4],fill=ac)
            ln=""; lw=0; mw=840; lines=[]
            for ch in tip:
                chw=_font(sz,ch).getbbox(ch)[2]-_font(sz,ch).getbbox(ch)[0]
                if lw+chw<=mw: ln+=ch; lw+=chw
                else: lines.append(ln); ln=ch; lw=chw
            lines.append(ln)
            for j,l in enumerate(lines):
                dtext(d,l,96,y+j*(sz+8),sz,(255,255,255))
            y+=len(lines)*(sz+8)+44
        ctext(d,"攀升AI  x  ComfyUI",H-80,28,(*ac,90),maxw=700)

    elif slide_type=="outro":
        next_ep,=content
        for i in range(4):
            d.line([(60,80+i*18),(W-60,80+i*18)],fill=(*ac,80-i*18),width=1)
        ctext(d,"感谢观看",H//2-280,80,(255,255,255),maxw=920)
        ctext(d,f"下期：{next_ep}",H//2-80,46,ac,maxw=880)
        rrect(d,W//2-240,H//2+60,W//2+240,H//2+165,40,tg)
        ctext(d,"关注  不错过下期更新",H//2+112,46,(255,255,255),maxw=460)
        rrect(d,W//2-200,H//2+200,W//2+200,H//2+300,40,tuple(max(0,c-20) for c in tg))
        ctext(d,"收藏这篇教程",H//2+250,46,(255,255,255),maxw=380)
        ctext(d,"攀升AI节点教程系列",H-160,40,(*ac,180),maxw=800)
        ctext(d,"ComfyUI-Tikpan-Pro",H-100,30,(*ac,100),maxw=700)

    return img


# ─── 每期幻灯片脚本 ────────────────────────────────────────────────────────────
SCRIPTS = {
1:{"theme":1,"dur":4,"slides":[
    ("intro",("一个插件\nAI图片视频音频全搞定","攀升AI节点  ·  入门教程")),
    ("section",("这个插件能做什么",["生成商品图、海报、创意图","文字 / 图片生成视频","AI作曲 + 口播配音","拆解爆款，反推提示词"])),
    ("step",(1,3,"安装插件","ComfyUI Manager\n搜索 Tikpan  →  Install  →  重启")),
    ("step",(2,3,"注册攀升AI账号","访问攀升AI官网\n注册  →  控制台  →  创建 API Key")),
    ("step",(3,3,"填入 API 密钥","在节点的 API_密钥 框里粘贴 Key\n即可开始使用所有节点")),
    ("tip",("省钱小技巧",["测试用低分辨率，确认后再升高","充值约 0.6元  =  1美元余额","批量任务用异步模式，更稳定"])),
    ("outro",("AI商品图换背景，3步出大片",)),
]},
2:{"theme":2,"dur":4,"slides":[
    ("intro",("AI换背景\n商品图秒变大片","GPT-Image-2 修图实战")),
    ("section",("这个节点能做什么",["一键换背景（保留产品完整）","改风格：奢华 / 自然 / 简约","遮罩局部重绘精准控制","最多4张参考图指导生成"])),
    ("flow",("最简工作流",["[LoadImage: 商品原图]","      ↓","[GPT-Image-2 官方修图 V2]","      ↓","[PreviewImage  /  SaveImage]"])),
    ("step",(1,4,"加载商品图","右键画布  →  LoadImage\n选择商品原图（白底最佳）")),
    ("step",(2,4,"写提示词（关键）","「保留产品主体完全不变，\n将背景替换为...，真实摄影质感」")),
    ("tip",("提示词公式",["「保留产品主体 / 材质 / logo 完全不变」","「将背景替换为【场景描述】」","「真实自然光，商业摄影质感」"])),
    ("outro",("一张图片生成10秒展示视频",)),
]},
3:{"theme":3,"dur":4,"slides":[
    ("intro",("一张图片\n生成10秒展示视频","HappyHorse 图生视频实战")),
    ("section",("HappyHorse 4种视频节点",["T2V：纯文字  →  视频","I2V：一张图  →  视频  (推荐入门)","R2V：多参考图  →  视频","Video-Edit：已有视频再编辑"])),
    ("flow",("图生视频工作流",["[LoadImage: 商品图]","      ↓  首帧图片","[HappyHorse 1.0 I2V]","      ↓","[PreviewVideo]"])),
    ("step",(1,4,"设置异步参数","mode  →  异步\nresolution  →  1080p\nduration  →  8s / 10s")),
    ("step",(2,4,"写视频提示词","「镜头缓慢推进，产品周围水汽流动\n保持产品外观颜色logo完全不变」")),
    ("tip",("视频提示词公式",["写运镜：「镜头缓慢推进 / 环绕旋转」","写变化：「周围有水汽 / 光粒效果」","锁定：「保持产品外观颜色logo不变」"])),
    ("outro",("AI作词作曲 + 口播配音",)),
]},
4:{"theme":4,"dur":4,"slides":[
    ("intro",("AI作词作曲\n+ 口播配音","Suno  &  豆包TTS 实战")),
    ("section",("音频节点一览",["Suno：AI作词作曲，出完整歌曲","豆包TTS 2.0：中文口播配音","MiniMax speech：高端配音","Gemini TTS：多语言配音"])),
    ("step",(1,3,"Suno 生成背景音乐","节点：音频 | Suno 音乐生成\n生成模式  →  普通生成\n模型  →  V5 最新通用")),
    ("tip",("Suno 提示词示例",["「适合美妆产品的中文流行电子歌」","「副歌朗朗上口，整体明亮积极」","风格标签：pop / cinematic / lofi"])),
    ("step",(2,3,"豆包TTS 配音旁白","节点：音频 | 豆包语音合成 2.0\n粘入旁白文案  →  选音色  →  运行")),
    ("tip",("实用建议",["Suno 一次出2首，选最好的那首","停顿控制：插入  <#0.5#>","纯音乐时打开「生成纯音乐」开关"])),
    ("outro",("拆解爆款视频，AI反推提示词",)),
]},
5:{"theme":5,"dur":4,"slides":[
    ("intro",("拆解爆款视频\nAI反推提示词","Gemini 分析  +  Grok 重构")),
    ("section",("这条链路能做什么",["拆解爆款视频镜头逻辑","分析运镜 / 色调 / 节奏","生成可直接使用的提示词","复刻同款，植入你的产品"])),
    ("flow",("视频拆解工作流",["[填入爆款视频URL]","      ↓","[Gemini 3 Flash 视频分析]","      ↓  分析报告","[Grok 多图剧本重构]","      ↓  生成提示词","[视频节点生成视频]"])),
    ("step",(1,3,"Gemini 分析视频","节点：Gemini 3 Flash 图片/视频分析\n分析任务  →  视频分镜拆解")),
    ("step",(2,3,"Grok 重构提示词","把分析报告接入 Grok 重构节点\n填入产品描述  →  生成视频提示词")),
    ("tip",("不止视频分析",["商品图：用「商品卖点分析」任务","长文档：用 Gemini 3.5 Flash 节点","联网搜索：GPT-5.4 Mini 开启搜索"])),
    ("outro",("全自动AI内容工厂综合实战",)),
]},
6:{"theme":6,"dur":4,"slides":[
    ("intro",("AI内容工厂\n全自动一条龙","1张图  →  图片+视频+音乐+配音")),
    ("section",("今天要完成什么",["4种风格商品精修图","2条展示视频（异步批量）","1首品牌背景音乐","1条产品旁白配音"])),
    ("flow",("4条并行支线",["商品原图","  A  →  多风格精修图","  B  →  展示视频（异步）","  C  →  背景音乐（Suno）","  D  →  旁白配音（TTS）"])),
    ("step",(1,4,"Phase 1：图片精修","4个修图实例并排，不同场景\n约2-5分钟，约1-3元")),
    ("step",(2,4,"Phase 2：视频+音乐并发","HappyHorse I2V 设为异步\nSuno 同时提交，两个任务并跑")),
    ("step",(3,4,"Phase 3-4：配音 + 收货","豆包TTS 30秒内完成\n视频/音乐后台生成完后统一下载")),
    ("tip",("实际成本对比",["传统方案：摄影+视频+音乐+配音  2000元+","AI方案：全套素材约 5-12元","节省成本 > 99%，效率提升 10倍+"])),
    ("outro",("更多垂直场景专题持续更新",)),
]},
}

def render_ep(ep):
    s=SCRIPTS[ep]; tid=s["theme"]; dur=s["dur"]; slides=s["slides"]
    ep_dir=TMP/f"ep{ep:02d}"; ep_dir.mkdir(parents=True,exist_ok=True)
    paths=[]
    for i,(st,content) in enumerate(slides):
        img=make_slide(ep,i,st,content,tid)
        p=ep_dir/f"slide_{i:02d}.png"; img.save(p); paths.append(str(p))
        print(f"  [{ep}] slide {i} [{st}] OK",flush=True)

    # 用 FFmpeg concat + xfade 合成视频
    # 每张幻灯片 dur 秒，0.5s xfade 淡入淡出
    n=len(paths); fade=0.5
    filter_lines=[]
    inputs=[]; [inputs.extend(["-loop","1","-t",str(dur+fade),"-i",p]) for p in paths]

    # scale 所有输入
    for i in range(n):
        filter_lines.append(f"[{i}:v]scale={W}:{H},setsar=1,fps=15[v{i}]")

    # xfade 链
    last=f"v0"
    for i in range(1,n):
        offset=i*dur-fade*(i-1) if i==1 else offset+dur-fade
        out=f"xf{i}"
        filter_lines.append(f"[{last}][v{i}]xfade=fade:duration={fade}:offset={offset:.2f}[{out}]")
        last=out

    filtergraph=";".join(filter_lines)
    out_path=OUT/f"ep{ep:02d}_攀升AI节点教程.mp4"
    cmd=(["ffmpeg","-y"]+inputs+
         ["-filter_complex",filtergraph,
          "-map",f"[{last}]",
          "-c:v","libx264","-pix_fmt","yuv420p","-crf","22","-preset","ultrafast",
          "-movflags","+faststart",str(out_path)])
    r=subprocess.run(cmd,capture_output=True,text=True)
    if r.returncode!=0:
        print(f"  FFmpeg error: {r.stderr[-600:]}",flush=True); return False
    sz=os.path.getsize(out_path)/1024/1024
    print(f"  [ep{ep:02d}] done  {sz:.1f}MB  →  {out_path.name}",flush=True)
    return True

if __name__=="__main__":
    OUT.mkdir(parents=True,exist_ok=True)
    TMP.mkdir(parents=True,exist_ok=True)
    eps=list(map(int,sys.argv[1:])) if len(sys.argv)>1 else list(range(1,7))
    print(f"渲染第 {eps} 期  输出目录: {OUT}",flush=True)
    ok={ep:render_ep(ep) for ep in eps}
    print("="*40,flush=True)
    for ep,v in ok.items(): print(f"  第{ep:02d}期: {'OK' if v else 'FAIL'}",flush=True)
