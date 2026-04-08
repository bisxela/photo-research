# Photo Search 前端

这是 Photo Search 的 Next.js 前端，用于本地或局域网环境下与后端交互。

## 技术栈

- Next.js
- React
- Tailwind CSS

## 当前目录关系

前端与后端并列放在同一个仓库中：

```text
photo-search-frontend/
photo-search-backend/
```

## 当前功能

- 检查后端健康状态
- 注册和登录账号
- 单图或批量上传
- 上传后轮询图片编码状态
- 文本搜图
- 相似图检索
- OCR 搜索入口
- 上传后自动执行本地 OCR
- 图片详情内的本地 OCR 文字识别
- OCR 结果自动回写后端，供后续 OCR 搜索使用
- 查看缩略图和原图

## 环境配置

如果需要可以创建本地环境文件：

```bash
cp .env.local.example .env.local
```

如果你希望手动固定后端地址，可配置：

```env
NEXT_PUBLIC_API_BASE_URL=http://<你的主机IP>:8000
```

如果不配置，前端会自动使用当前页面域名，并默认后端在 `8000` 端口。

## 本地启动

首次安装依赖：

```bash
npm install
```

如果这台机器已经安装过依赖，并且 `node_modules/` 仍然存在，一般不需要每次重复执行。

启动开发服务器：

```bash
npm run dev -- --hostname 0.0.0.0
```

本机打开：

```text
http://localhost:3000
```

同一局域网内其他设备打开：

```text
http://<你的主机IP>:3000
```

例如：

```text
http://192.168.1.23:3000
```

请确保：

- 后端已运行，且可从当前主机访问 `8000`
- 前端开发服务器已经监听 `0.0.0.0`
- 手机和电脑在同一网络中，或已通过 Tailscale 互通
- 本地防火墙没有拦截 `3000` 和 `8000`

## 开发说明

- 当前页面优先面向本地前后端联调
- 结果图片关闭了远程图片优化，方便直接加载本地后端静态资源
- 使用系统字体，不依赖 Google Fonts
- 已包含基础 PWA 配置与图标
- 当前目标仍然是移动端友好的 Web Demo，而不是原生 iOS 应用

## iPhone Safari 使用方式

在 iPhone Safari 中通过主机局域网 IP 打开前端后：

1. 点击 Safari 的分享按钮
2. 选择“添加到主屏幕”
3. 从主屏幕图标启动

当前是一个轻量 PWA：

- 支持独立窗口启动
- 带应用图标
- 带主题色

当前还没有离线缓存和 Service Worker。

## 常用命令

启动开发服务器：

```bash
npm run dev
```

执行 lint：

```bash
npm run lint
```
