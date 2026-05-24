# BigBanana AI Director — 完整部署教程

> 更新日期：2026-05-23 | 项目地址：https://github.com/shuyu-labs/BigBanana-AI-Director

---

## 一、项目简介

BigBanana AI Director 是一个 AI 短剧 / 漫剧一站式生产平台，核心工作流：

```
一句话输入 → AI 生成剧本 → 角色 / 场景资源库 → 分镜（Keyframe）→ 图像生成 → 视频合成 → 成片
```

使用 **Script-to-Asset-to-Keyframe** 工业化工作流，相比传统"抽卡式"生成：
- 精准控制角色一致性
- 支持场景连续性和镜头运动
- 一键从小说文本拆分多集

---

## 二、环境要求

| 组件 | 最低要求 | 推荐 |
|---|---|---|
| 操作系统 | Windows 10 / macOS 12 / Ubuntu 20.04 | Ubuntu 22.04 LTS |
| Docker | 24.x+ | 最新稳定版 |
| Docker Compose | 2.x+ | 最新稳定版 |
| 内存 | 4GB | 8GB+ |
| 磁盘空间 | 10GB | 20GB+（存储生成图片/视频） |
| 网络 | 能访问 Docker Hub | 国内可配镜像加速 |

---

## 三、安装 Docker 环境

### 3.1 Windows 安装

```
1. 下载 Docker Desktop: https://www.docker.com/products/docker-desktop
2. 安装并启动 Docker Desktop
3. 确认 Docker 可用：
   docker --version
   docker-compose --version
```

### 3.2 Linux (Ubuntu) 安装

```bash
# 安装 Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# 将当前用户加入 docker 组（避免每次 sudo）
sudo usermod -aG docker $USER
newgrp docker

# 安装 Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# 验证
docker --version
docker-compose --version
```

### 3.3 配置 Docker 镜像加速（国内必须）

```bash
# 编辑 /etc/docker/daemon.json
sudo tee /etc/docker/daemon.json <<EOF
{
  "registry-mirrors": [
    "https://registry.cn-hangzhou.aliyuncs.com",
    "https://mirror.baidubce.com"
  ]
}
EOF

sudo systemctl restart docker
```

---

## 四、部署 BigBanana

### 4.1 克隆项目

```bash
git clone https://github.com/shuyu-labs/BigBanana-AI-Director.git
cd BigBanana-AI-Director
```

### 4.2 查看 docker-compose.yaml

```bash
cat docker-compose.yaml
```

典型配置包含：前端容器（Next.js）+ 后端容器（.NET/Python）+ 数据库容器。

### 4.3 启动服务

```bash
# 首次启动（会拉取镜像，国内视网速需要 5-30 分钟）
docker-compose up -d

# 查看启动状态
docker-compose ps

# 查看日志
docker-compose logs -f
```

### 4.4 访问应用

启动完成后，浏览器访问：
```
http://localhost:3005
```

---

## 五、首次配置

### 5.1 配置 AI API Key

BigBanana 需要接入 AI 模型 API，支持两种方式：

**方式 A：使用攀升AI（tikpan.com）中转站（推荐国内用户）**

1. 访问 https://tikpan.com 注册账号
2. 在控制台创建 API Key
3. 在 BigBanana 设置中填入：
   - API Base URL: `https://tikpan.com/v1`
   - API Key: `sk-你的密钥`

**方式 B：直接使用 OpenAI / Gemini 官方**

1. 前往各平台获取 API Key
2. 在 BigBanana 设置中填入对应 Base URL 和 Key

### 5.2 新建项目流程

```
1. 点击「新建项目」
2. 输入项目名称和简介
3. 选择剧情类型（漫剧/短剧/动漫）
4. 在「项目资源」中添加角色（上传参考图）
5. 在「剧集」中创建第一集
6. 输入剧情摘要 → AI 生成分镜脚本
7. 逐帧生成图片 → 合成视频
```

---

## 六、常见问题

**Q：docker-compose up 报错 "connection refused"**

```bash
# 检查端口是否被占用
netstat -tlnp | grep 3005
# 修改 docker-compose.yaml 中的端口映射
```

**Q：图片生成失败，报 "API timeout"**

- 检查 API Key 是否正确
- 攀升AI账户余额是否充足
- 尝试降低分辨率参数

**Q：首次启动很慢**

镜像大小约 2-5GB，首次拉取需要时间。建议配置 Docker 镜像加速后再拉取。

**Q：如何更新到最新版本**

```bash
docker-compose pull
docker-compose up -d
```

---

## 七、数据持久化

Docker 容器重启后数据可能丢失，建议在 `docker-compose.yaml` 中挂载数据目录：

```yaml
volumes:
  - ./data/uploads:/app/uploads
  - ./data/outputs:/app/outputs
  - ./data/db:/app/data
```

---

## 八、生产环境部署建议

1. 使用 Nginx 反向代理
2. 配置 HTTPS（Let's Encrypt）
3. 设置强密码和访问控制
4. 定期备份 data 目录
5. 监控磁盘用量（图片/视频会占用大量空间）
