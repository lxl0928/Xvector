# xvector_web

Xvector 管理控制台（Vue3 + Ant Design Vue），设计说明见 [`docs/DESIGN-xvector-web.md`](../docs/DESIGN-xvector-web.md)。

## 本地开发

需本机 Gateway 已启动（默认 `http://127.0.0.1:19530`）。

```bash
cd xvector_web
npm install
npm run dev
```

浏览器打开 Vite 地址（默认 `http://127.0.0.1:5173/login`）。  
开发时 `/api/*` 由 Vite proxy 转发到 Gateway。

## Docker Compose

仓库根目录：

```bash
docker compose up -d --build
```

登录页：`http://{host}:19531/login`  
浏览器请求走同源 `/api/*`，由 Nginx 反代到 Gateway `:19530`。

默认账号与集群一致（`XVECTOR_USERNAME` / `XVECTOR_PASSWORD`，默认 `root` / `Xvector`）。
