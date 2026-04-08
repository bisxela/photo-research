# Tailscale 远程访问说明

本文说明如何通过 Tailscale 从局域网外访问本地运行的 Photo Search 前后端服务。

## 为什么使用 Tailscale

当前项目默认是本地服务：

- 前端端口：`3000`
- 后端端口：`8000`

如果不使用 Tailscale，通常只能在以下场景访问：

- 同一 Wi‑Fi 或同一热点下
- 能直接访问你电脑局域网 IP 的设备

Tailscale 会在你的设备之间建立私有网络，因此即使 iPhone 和 Linux 主机不在同一局域网，也可以直接互通。

官方文档：

- Linux 安装：https://tailscale.com/docs/install/linux
- 安装总览：https://tailscale.com/docs/install
- 快速开始：https://tailscale.com/docs/install/start

## 需要准备的内容

- 一个 Tailscale 账号
- Ubuntu 主机已安装 Tailscale
- iPhone 已安装 Tailscale
- 项目已经在 Ubuntu 主机上运行

## 主机配置（Ubuntu 22.04）

安装 Tailscale：

```bash
curl -fsSL https://tailscale.com/install.sh | sh
```

让主机上线：

```bash
sudo tailscale up
```

执行后会输出登录链接，用浏览器打开并完成认证。

登录完成后，查看分配到的 Tailscale IPv4：

```bash
tailscale ip -4
```

也可以查看当前状态：

```bash
tailscale status
```

## 启动项目

### 启动后端

GPU 模式：

```bash
cd /home/abin/projects/photo-search/photo-search-backend
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --no-build
```

CPU 模式：

```bash
cd /home/abin/projects/photo-search/photo-search-backend
docker compose up -d
```

### 启动前端

让 Next.js 监听所有网卡：

```bash
cd /home/abin/projects/photo-search/photo-search-frontend
npm run dev -- --hostname 0.0.0.0
```

这样前端才能通过 Tailscale 网卡被远程设备访问。

## iPhone 配置

1. 在 App Store 安装 Tailscale
2. 使用同一个 Tailscale 账号登录
3. 确认手机和电脑都出现在同一个 tailnet 中

## 访问地址

先在 Ubuntu 主机上获取 Tailscale IPv4：

```bash
tailscale ip -4
```

假设返回：

```text
100.101.102.103
```

则 iPhone 可访问：

- 前端：`http://100.101.102.103:3000`
- 后端健康检查：`http://100.101.102.103:8000/health`

由于前端会根据当前页面域名自动推断后端地址，所以通过 Tailscale IP 打开前端后，前端请求也会自动指向这台主机的 `8000` 端口。

## 可选：使用 MagicDNS

如果 Tailscale 已启用 MagicDNS，可以尝试直接使用主机名而不是 IP。

例如：

```text
http://abin-lenovo:3000
```

可以用以下命令查看当前可见的设备名称：

```bash
tailscale status
```

## 验证方式

在 Ubuntu 主机上：

```bash
tailscale status
tailscale ip -4
curl -s http://localhost:8000/health
```

在 iPhone 上：

- 打开 `3000` 端口的前端页面
- 点击页面中的“检查后端”

## 常见问题

### 已安装 Tailscale，但没有连上网络

执行：

```bash
sudo tailscale up
```

### 前端能打开，但接口请求失败

确认后端服务可用：

```bash
curl -s http://localhost:8000/health
```

### 主机本地能访问，但远程设备访问不了前端

确认前端使用的是：

```bash
npm run dev -- --hostname 0.0.0.0
```

### 以后想长期稳定运行

后续如果需要长期使用，建议把前端从 `next dev` 改为生产构建，再放到反向代理后面运行。
