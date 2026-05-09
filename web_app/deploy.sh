#!/bin/bash
# 🚀 Tikpan Web - 全自动部署脚本（支持 Debian 11）
set -e

echo "=========================================="
echo "  Tikpan AI Studio - 全自动部署"
echo "=========================================="

# 0. 自动修复 Debian 11 源仓库
echo "[0/5] 检查并修复系统源..."
if grep -q "bullseye" /etc/debian_version 2>/dev/null; then
    cat > /etc/apt/sources.list << 'EOF'
deb http://archive.debian.org/debian/ bullseye main contrib non-free
deb-src http://archive.debian.org/debian/ bullseye main contrib non-free
EOF
fi

# 1. 系统依赖
echo "[1/5] 安装系统依赖..."
apt-get update -y
apt-get install -y python3 python3-pip python3-venv nginx curl

# 2. Python 依赖
echo "[2/5] 安装 Python 依赖..."
cd "$(dirname "$0")"
pip3 install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 3. 环境变量
echo "[3/5] 创建配置文件..."
cat > /root/web_app/.env << EOF
TIKPAN_API_KEY=sk-你的key
TIKPAN_SECRET=$(tr -dc 'a-zA-Z0-9' < /dev/urandom | head -c 32)
FLASK_SECRET=$(tr -dc 'a-zA-Z0-9' < /dev/urandom | head -c 32)
EOF

# 4. Nginx
echo "[4/5] 配置 Nginx..."
read -p "请输入你的域名: " DOMAIN

cat > /etc/nginx/sites-available/tikpan << NGINXEOF
server {
    listen 80;
    server_name $DOMAIN;
    client_max_body_size 100M;
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
NGINXEOF

ln -sf /etc/nginx/sites-available/tikpan /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

# 5. 开机自启
echo "[5/5] 创建系统服务..."
cat > /etc/systemd/system/tikpan.service << SERVICEEOF
[Unit]
Description=Tikpan AI Studio
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/web_app
EnvironmentFile=/root/web_app/.env
ExecStart=$(which python3) /root/web_app/app.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SERVICEEOF

systemctl daemon-reload
systemctl enable tikpan
systemctl restart tikpan

echo ""
echo "=========================================="
echo "  ✅ 部署完成！"
echo "  🌐 http://$DOMAIN"
echo "  🔐 http://$DOMAIN/admin"
echo "=========================================="
echo "  1. 首次打开网站会显示后台管理登录页"
echo "  2. 密码: admin123"
echo "  3. 登录后先去「系统设置」配 SMTP"
echo "=========================================="
