# Tikpan AI Studio 正式商业上线 SOP

这份文档是从当前本地项目走到稳定商业网站的执行手册。目标不是“能打开网页”，而是做到：可注册、可登录、可充值、可扣费、可退款、可备份、可恢复、可持续上新模型。

## 0. 当前产品状态

当前网站已经具备商业产品骨架：

- 用户邮箱注册、登录、Google/GitHub OAuth 登录入口。
- 用户余额 `balance`。
- 充值订单 `orders`。
- 余额流水 `balance_ledger`。
- 生成记录 `generation_logs`。
- 模型、字段、分类、渠道、路由、定价后台。
- 生成前扣费，失败自动退款。
- 生成链路进度：用户、服务器、计费、上游、OSS、CDN。
- 生产环境默认拒绝弱密钥、默认后台密码和本地域名启动。
- 生产环境默认禁止模拟充值直接到账。

还必须补齐的生产部件：

- 真实支付回调和验签。
- 生产 `.env`。
- 服务器、域名、HTTPS。
- OSS/CDN。
- 邮件 SMTP。
- 数据库备份。
- 监控告警。
- 规范化模型上新流程。

## 1. 推荐上线方式

不要长期 SSH 到服务器直接改代码。推荐流程：

```text
本地电脑修改代码/catalog
-> 本地测试
-> 提交到 Git 私有仓库
-> SSH 到服务器 git pull
-> docker compose up -d --build
-> 同步 catalog
-> 跑部署检查
-> 验证线上功能
```

服务器只负责运行网站。本地仓库是代码和模型配置的唯一源头。

## 2. 准备服务器和域名

推荐起步配置：

```text
系统：Ubuntu 22.04 或 Ubuntu 24.04
CPU/内存：2C4G 可以内测，4C8G 更适合小规模商业运营
系统盘：40G+
数据盘：按生成记录和日志量决定
带宽：页面和 API 不重，媒体结果必须走 OSS/CDN
```

域名建议：

```text
www.example.com      主站
cdn.example.com      图片/视频/音频 CDN
```

DNS 解析示例：

```text
A     www      你的服务器公网 IP
CNAME cdn      你的 OSS/CDN 加速域名
```

## 3. 服务器基础环境安装

SSH 登录服务器：

```bash
ssh root@你的服务器IP
```

安装基础依赖：

```bash
apt update
apt install -y git curl nginx certbot python3-certbot-nginx docker.io docker-compose-plugin
systemctl enable docker
systemctl start docker
```

检查 Docker：

```bash
docker --version
docker compose version
```

## 4. 建立 Git 私有仓库

如果项目还没有 Git 私有仓库，先在本地初始化：

```bash
cd D:\ComfyUI-aki-v2\ComfyUI\custom_nodes\ComfyUI-Tikpan-Pro
git init
git add .
git commit -m "initial tikpan web app"
```

然后在 GitHub/GitLab/Gitee 创建私有仓库，把远程地址加上：

```bash
git remote add origin 你的私有仓库地址
git push -u origin main
```

服务器拉取：

```bash
cd /opt
git clone 你的私有仓库地址 tikpan-web
cd /opt/tikpan-web/web_app
```

## 5. 配置生产环境变量

进入项目：

```bash
cd /opt/tikpan-web/web_app
cp .env.example .env
nano .env
```

必须修改：

```env
APP_ENV=production
PUBLIC_BASE_URL=https://www.example.com
ALLOWED_ORIGINS=https://www.example.com

TIKPAN_API_KEY=sk-你的正式上游key

TIKPAN_SECRET=随机长字符串
FLASK_SECRET=随机长字符串
ADMIN_PASSWORD=强后台密码

TRUST_PROXY=true
```

生成随机密钥：

```bash
openssl rand -hex 32
openssl rand -hex 32
```

分别填入：

```env
TIKPAN_SECRET=第一条随机值
FLASK_SECRET=第二条随机值
```

支付相关：

```env
ENABLE_DEV_RECHARGE=false
PAYMENT_PROVIDER=alipay
```

注意：`ENABLE_DEV_RECHARGE=false` 在生产环境必须保持关闭。真实支付回调未完成前，用户充值只会创建待支付订单，不会入账。

## 6. 配置 OSS/CDN

推荐生产必须开启 OSS/CDN，否则生成文件会落在服务器本地，后续迁移、扩容、备份都麻烦。

`.env` 示例：

```env
OSS_ENABLED=true
OSS_BUCKET=你的bucket
OSS_ENDPOINT=oss-ap-southeast-1.aliyuncs.com
OSS_KEY_ID=你的AccessKeyId
OSS_KEY_SECRET=你的AccessKeySecret
OSS_PREFIX=tikpan-web
OSS_CDN_DOMAIN=https://cdn.example.com
```

上线前检查：

```text
1. OSS bucket 可写。
2. CDN 域名能访问 OSS 对象。
3. 生成一张图后，返回链接应是 https://cdn.example.com/...。
4. 不要把 OSS_KEY_SECRET 提交进 Git。
```

## 7. 配置邮件 SMTP

注册验证码依赖 SMTP。生产环境如果没有 SMTP，验证码不会返回给前端，用户无法正常注册。

`.env` 示例：

```env
SMTP_SERVER=smtp.qq.com
SMTP_PORT=465
SMTP_USE_SSL=true
SMTP_ACCOUNT=你的邮箱
SMTP_SENDER=你的邮箱
SMTP_PASSWORD=邮箱授权码
```

后台也可以在“系统设置”里配置 SMTP。建议上线前真实注册一个账号测试验证码。

## 8. 启动 Docker 服务

```bash
cd /opt/tikpan-web/web_app
docker compose up -d --build
docker compose ps
docker compose logs -f
```

健康检查：

```bash
curl http://127.0.0.1:5000/healthz
```

预期：

```json
{"ok": true}
```

如果容器启动失败，查看日志：

```bash
docker compose logs --tail=200 tikpan-web
```

常见失败原因：

```text
APP_ENV=production 但仍使用 admin123。
PUBLIC_BASE_URL 还是 localhost。
TIKPAN_SECRET 或 FLASK_SECRET 太短。
TIKPAN_API_KEY 没配置。
```

## 9. 配置 Nginx 反向代理

创建配置：

```bash
nano /etc/nginx/conf.d/tikpan.conf
```

写入：

```nginx
server {
    listen 80;
    server_name www.example.com example.com;

    client_max_body_size 100m;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 60s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
    }
}
```

检查并重载：

```bash
nginx -t
systemctl reload nginx
```

## 10. 配置 HTTPS

使用 Certbot：

```bash
certbot --nginx -d www.example.com -d example.com
```

检查自动续期：

```bash
certbot renew --dry-run
```

访问：

```text
https://www.example.com
```

浏览器必须显示 HTTPS 正常。

## 11. 跑部署检查

进入容器执行：

```bash
cd /opt/tikpan-web/web_app
docker compose exec tikpan-web python scripts/deploy_check.py
```

必须全部 OK。典型成功结果：

```text
[OK] APP_ENV=production
[OK] FLASK_SECRET 已替换
[OK] TIKPAN_SECRET 已替换
[OK] ADMIN_PASSWORD 已替换
[OK] TIKPAN_API_KEY 已配置
[OK] PUBLIC_BASE_URL 为公网 HTTPS
[OK] ALLOWED_ORIGINS 已配置
[OK] 生产环境未开启模拟充值
[OK] 数据库目录可写
[OK] 输出目录可写
[OK] 至少一个启用渠道
[OK] 至少一个启用定价
```

如果失败，不要上线，先按提示修。

## 12. 后台初始化检查

打开：

```text
https://www.example.com/admin/
```

用 `.env` 里的 `ADMIN_PASSWORD` 登录。

检查：

```text
1. 分类是否存在。
2. 模型是否存在。
3. 字段是否能正常展示。
4. 渠道是否启用。
5. 路由是否绑定。
6. 价格是否合理。
7. 系统设置里的 SMTP/OAuth 是否正确。
```

后台 API 未登录应该返回 401，这是正常的安全行为。

## 13. 同步模型 Catalog

每次新增或修改模型，都建议先在本地改：

```text
web_app/catalog/tikpan_nodes.py
```

服务器同步：

```bash
cd /opt/tikpan-web/web_app
docker compose exec tikpan-web python scripts/sync_tikpan_nodes.py --dry-run
docker compose exec tikpan-web python scripts/sync_tikpan_nodes.py
```

说明：

```text
--dry-run 只显示将同步多少分类、模型、字段、路由。
不带 --dry-run 才会真正写入数据库。
```

同步后到后台检查模型字段。

## 14. 新增模型的标准流程

本地打开：

```text
web_app/catalog/tikpan_nodes.py
```

添加模型示例：

```python
{
    "id": "new-image-model",
    "name": "新图像模型",
    "category_key": "image_generation",
    "provider": "Tikpan / 上游供应商",
    "description": "给用户看的模型说明。",
    "api_type": "tikpan_proxy",
    "endpoint": "/v1/images/generations",
    "upstream_model": "real-upstream-model-name",
    "sort_order": 99,
    "pricing": {
        "credits_1k": 6,
        "credits_2k": 10,
        "credits_4k": 18,
        "billing_mode": "resolution"
    },
    "fields": [
        field("prompt", "textarea", "提示词", "", required=1, rows=5, sort_order=1),
        field("model", "select", "模型", "real-upstream-model-name", options=["real-upstream-model-name"], sort_order=2),
        field("resolution", "select", "分辨率", "2K", options=["1K", "2K", "4K"], sort_order=3),
        field("aspect_ratio", "select", "画面比例", "1:1", options=["1:1", "16:9", "9:16"], sort_order=4),
    ],
}
```

字段类型：

```text
text          单行文本
textarea      多行文本
select        下拉选项
number        数字输入
checkbox      开关
file_image    图片上传
```

本地检查：

```powershell
cd D:\ComfyUI-aki-v2\ComfyUI\custom_nodes\ComfyUI-Tikpan-Pro\web_app
.venv\Scripts\python.exe -B -m py_compile catalog\tikpan_nodes.py scripts\sync_tikpan_nodes.py
.venv\Scripts\python.exe scripts\sync_tikpan_nodes.py --dry-run
```

提交代码：

```bash
git add web_app/catalog/tikpan_nodes.py
git commit -m "add new model"
git push
```

服务器发布：

```bash
ssh root@你的服务器IP
cd /opt/tikpan-web
git pull
cd web_app
docker compose up -d --build
docker compose exec tikpan-web python scripts/sync_tikpan_nodes.py --dry-run
docker compose exec tikpan-web python scripts/sync_tikpan_nodes.py
docker compose exec tikpan-web python scripts/deploy_check.py
```

## 15. 真实支付接入

当前生产环境不会模拟到账。正式收费必须完成真实支付。

正确支付流程：

```text
用户选择充值金额
-> 创建 orders 记录，状态 pending
-> 跳转支付宝/微信/Stripe
-> 支付平台异步回调服务器
-> 服务器验签
-> 校验订单号、金额、用户、状态
-> 调用 complete_order(order_id)
-> 用户余额增加
-> balance_ledger 写入 recharge 流水
```

上线前绝对不要把 `ENABLE_DEV_RECHARGE=true` 放到生产环境。

支付回调必须做到：

```text
1. 验签。
2. 金额一致。
3. 订单未完成。
4. 幂等处理，重复回调不重复加余额。
5. 写日志。
6. 异常时保留待处理订单。
```

## 16. 数据库和备份

当前 SQLite 可以早期试运营。正式增长后建议迁移 PostgreSQL/MySQL。

最低限度先做每日备份：

```bash
mkdir -p /opt/backups/tikpan
crontab -e
```

加入：

```cron
0 3 * * * cp /opt/tikpan-web/web_app/data/tikpan.db /opt/backups/tikpan/tikpan-$(date +\%F).db
```

如果有本地输出文件，也一起备份：

```cron
10 3 * * * tar -czf /opt/backups/tikpan/tikpan-files-$(date +\%F).tar.gz /opt/tikpan-web/web_app/data /opt/tikpan-web/web_app/outputs
```

更稳的做法是把备份上传到 OSS/R2/S3。

## 17. 监控和日志

最低限度检查：

```bash
docker compose ps
docker compose logs --tail=100 tikpan-web
curl -fsS https://www.example.com/healthz
```

建议配置：

```text
1. UptimeRobot 或云监控，每 1 分钟检查 /healthz。
2. Nginx access/error log 保留。
3. Docker 日志轮转。
4. 服务器磁盘使用率告警。
5. 余额流水异常告警。
6. 上游失败率告警。
```

Docker 日志轮转可在 `/etc/docker/daemon.json` 配：

```json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "50m",
    "max-file": "5"
  }
}
```

然后：

```bash
systemctl restart docker
cd /opt/tikpan-web/web_app
docker compose up -d
```

## 18. 上线前完整测试清单

必须逐项测试：

```text
[ ] 首页能打开。
[ ] HTTPS 正常。
[ ] /healthz 返回 ok。
[ ] 后台能登录。
[ ] 后台 API 未登录返回 401。
[ ] 邮箱验证码能发送。
[ ] 用户能注册。
[ ] 用户能登录。
[ ] 用户余额能显示。
[ ] 充值创建订单。
[ ] 生产环境充值不会模拟到账。
[ ] 后台能看到订单/流水。
[ ] 新增模型能在前台显示。
[ ] 请求预览能正常返回。
[ ] 余额不足时生成失败，提示计费环节失败。
[ ] 余额充足时生成会扣费。
[ ] 上游成功后生成记录为 success。
[ ] 上游失败后自动退款。
[ ] 退款写入 balance_ledger。
[ ] OSS/CDN 链接能打开。
[ ] 重复提交不会重复扣费。
[ ] 手机端布局正常。
```

## 19. 发布更新流程

本地：

```bash
git status
git add .
git commit -m "describe change"
git push
```

服务器：

```bash
ssh root@你的服务器IP
cd /opt/tikpan-web
git pull
cd web_app
docker compose up -d --build
docker compose exec tikpan-web python scripts/sync_tikpan_nodes.py --dry-run
docker compose exec tikpan-web python scripts/sync_tikpan_nodes.py
docker compose exec tikpan-web python scripts/deploy_check.py
curl -fsS https://www.example.com/healthz
```

如果更新失败，先看日志：

```bash
docker compose logs --tail=200 tikpan-web
```

必要时回滚：

```bash
cd /opt/tikpan-web
git log --oneline -5
git checkout 上一个稳定commit
cd web_app
docker compose up -d --build
```

## 20. 内测到正式发布

推荐节奏：

```text
第 1 阶段：本地开发测试
第 2 阶段：服务器预发，只有自己访问
第 3 阶段：邀请 3-10 个用户内测
第 4 阶段：开启真实支付，但限量开放
第 5 阶段：观察失败率、退款率、成本、利润
第 6 阶段：正式开放注册和充值
```

不要一开始就大规模投放。先确认：

```text
1. 每个模型都有利润。
2. 上游失败会退款。
3. OSS/CDN 成本可控。
4. 支付对账准确。
5. 数据库每天可恢复。
```

## 21. 每日运维清单

每天检查：

```bash
curl -fsS https://www.example.com/healthz
docker compose ps
df -h
```

后台检查：

```text
1. 今日充值订单。
2. 今日生成成功率。
3. 今日失败退款。
4. 上游渠道失败情况。
5. 用户反馈。
6. 余额流水是否异常。
```

## 22. 每次上新模型检查清单

```text
[ ] 上游模型真实可用。
[ ] 参数默认值可跑通。
[ ] 下拉选项比手填优先。
[ ] pricing 覆盖成本并有利润。
[ ] route 绑定正确渠道。
[ ] request-preview 正常。
[ ] 小额度真实生成成功。
[ ] 失败能退款。
[ ] 前台展示文案清楚。
[ ] 后台排序合理。
```

## 23. 关键原则

```text
1. 本地改代码，服务器只运行。
2. catalog 是模型配置源头，后台用于检查和微调。
3. 生产绝不允许模拟充值到账。
4. 所有余额变化都必须有 balance_ledger。
5. 所有生成任务都必须有 generation_logs。
6. 结果媒体必须尽快走 OSS/CDN。
7. 上线前 scripts/deploy_check.py 必须通过。
8. 有收入后尽快从 SQLite 迁移到 PostgreSQL/MySQL。
```

