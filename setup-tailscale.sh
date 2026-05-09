#!/usr/bin/env bash
# Tailscale 配置脚本 — 只需要跑一次
set -e

echo "🦞 配置 Tailscale Serve + Funnel..."

# 1. 设置 operator（之后 tailscale serve/funnel 就不需要 sudo 了）
echo "[1/3] 设置 tailscale operator..."
sudo tailscale set --operator=$USER

# 2. 配置 serve：443 端口代理到前端 3000
echo "[2/3] 配置 Tailscale Serve (HTTPS) ..."
tailscale serve --bg --https 443 http://127.0.0.1:3000

# 3. 配置 funnel：允许公网访问（带上 HTTPS 证书）
echo "[3/3] 配置 Tailscale Funnel (公网) ..."
tailscale funnel --bg 443

echo ""
echo "✅ 配置完成！"
echo "   内网访问: https://dogzi-ms-7d73.tailbc211b.ts.net"
echo "   公网访问: https://dogzi-ms-7d73.tailbc211b.ts.net (Funnel)"
echo ""
echo "   后端 API: https://dogzi-ms-7d73.tailbc211b.ts.net/api"
echo ""
echo "如需关闭 Funnel: tailscale funnel 443 off"
