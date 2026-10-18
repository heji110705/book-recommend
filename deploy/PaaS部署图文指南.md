# 免费 PaaS 部署图文指南（无需自己买服务器）

> 目标：把项目推到代码仓库，然后在 Render（或国内 Sealos）一键部署，得到一个公网 `https://xxx.onrender.com` 网址，评委扫码即可访问。
> 全程约 15～25 分钟，不需要会运维，按步骤点即可。

---

## 方案 A：GitHub + Render（推荐，最省事、免费）

> Render 免费版：休眠后首次访问约 30 秒唤醒，答辩演示前先点开一次即可。

### 第 1 步：把项目变成 Git 仓库

在项目目录 `D:\biyesheji\book_recommend` 打开 PowerShell：

```powershell
cd D:\biyesheji\book_recommend
git init
git add .
git commit -m "init: 个性化图书推荐系统（可解释推荐+多样性评估+兴趣引导+Docker）"
```

> 仓库已自带 `.gitignore`，会自动排除虚拟环境、缓存和截图；**演示数据库 db.sqlite3 与封面 media/ 会保留**。

### 第 2 步：在 GitHub 建仓库并推送

1. 打开 <https://github.com/new>（没有账号先注册）。
2. Repository name 填 `book-recommend`，选 **Private 或 Public 均可**，**不要**勾选 README/gitignore（本地已有）。
3. 建完后复制仓库地址，在 PowerShell 执行（会让你登录 GitHub，按提示用浏览器授权一次）：

```powershell
git branch -M main
git remote add origin https://github.com/你的用户名/book-recommend.git
git push -u origin main
```

### 第 3 步：在 Render 一键部署

1. 打开 <https://dashboard.render.com>，用 **GitHub 账号登录**（Sign in with GitHub）。
2. 点 **New → Blueprint**（或 New → Web Service），选择刚推送的 `book-recommend` 仓库并授权。
3. Render 会自动识别仓库里的 `render.yaml`：
   - 运行环境：**Docker**；
   - 计划：**Free**；
   - `SECRET_KEY` 会自动生成（蓝图已配置 `generateValue: true`）。
4. 点 **Apply / Create Web Service**，等待 5～8 分钟自动构建（拉依赖 → collectstatic → migrate → gunicorn）。
5. 构建成功后，顶部会给出公网地址，形如：
   `https://book-recommend-xxxx.onrender.com` —— 这就是可发给评委的网址。

> 若不是用 Blueprint 而是手动建 Web Service：
> Environment 选 **Docker**，Dockerfile Path 填 `./Dockerfile`，Port 留空（会自动读取 `$PORT`），Plan 选 Free。

### 第 4 步：答辩前自检

- 先在浏览器打开一次网址（唤醒免费实例）。
- 访问 `/admin/` 用 `admin / admin12345` 登录后台；用 `demo / demo12345` 演示个性化推荐。
- 现场注册一个新账号，演示「兴趣引导 → 冷启动推荐」。

---

## 方案 B：国内 Sealos（无需外网访问 GitHub，适合国内网络）

> Sealos 提供"应用管理"，可直接部署 Docker 镜像；需先在本地或用平台构建镜像。

1. 注册并登录 <https://sealos.io>（国内手机号即可）。
2. 进入「应用管理 → 应用 → 部署应用」：
   - 镜像来源：先用平台"镜像构建"把 GitHub/Gitee 仓库的 `Dockerfile` 构建成镜像（也可本机 `docker build -t book-recommend .` 后推到镜像仓库）。
   - 容器端口：`8000`；开启"外网访问"。
   - 环境变量：`ALLOWED_HOSTS=*`、`SECRET_KEY=任意长随机串`。
3. 部署后平台分配一个公网域名，可直接访问。

> 国内平台（Sealos / 阿里云 SAE / 腾讯云 CloudBase 等）流程类似：给镜像、给端口 8000、给环境变量、开外网访问即可。

---

## 常见问题

| 问题 | 处理 |
|---|---|
| 构建时下载依赖很慢/失败 | 把 `Dockerfile` 里 pip 命令加回国内源：`-i https://pypi.tuna.tsinghua.edu.cn/simple`（海外平台则不要加） |
| 首次打开很慢 | 免费实例休眠，30 秒内唤醒；提前点开一次 |
| 注册/评分后重启容器数据没了 | 免费平台磁盘是临时的；演示数据已内置在镜像中，重置不影响演示。如需持久化，绑定免费 PostgreSQL 并设置 `DATABASE_URL` |
| 样式/封面丢失 | 确认仓库里包含 `media/covers/` 且构建日志有 `collectstatic` 成功记录 |
| 域名变了导致登录/表单报错 | 若绑了域名，在环境变量补 `CSRF_ORIGINS=https://你的域名` |

---

## 演示账号

| 账号 | 密码 | 用途 |
|---|---|---|
| admin | admin12345 | 后台管理 `/admin/` |
| demo | demo12345 | 数据充足、推荐个性化 |
| 现场新注册 | — | 演示兴趣引导 + 冷启动 |
