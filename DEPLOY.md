# 部署指南 · 阿里云轻量应用服务器

把「知势 Cheese」以**网站**形式部署到阿里云轻量应用服务器，含**用户登录系统**、**点数计费/充值**、**后台管理**与**在线发起深度研究**。采用 Docker Compose 一键起栈：

```
┌────────────────────────── 阿里云轻量服务器 ──────────────────────────┐
│                                                                      │
│   浏览器 ──HTTP:80──▶  nginx (frontend 容器)                          │
│                         ├─ 托管 React SPA 静态资源                    │
│                         └─ 反代 /api、/healthz ──▶ backend:8000       │
│                                                    (FastAPI)          │
│                                                    ├─ 登录/注册/会话   │
│                                                    ├─ 只读研究数据     │
│                                                    ├─ 点数/订单/充值   │
│                                                    ├─ 后台管理(admin)  │
│                                                    └─ 在线研究任务队列 │
│                                                          │            │
│                                              SQLite + 研究产物         │
│                                              (Docker volume: 持久化)   │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 一、准备工作（在你的服务器上）

1. **开放端口**：登录阿里云控制台 → 轻量应用服务器 → 防火墙，放行 **TCP 80**（如改了 `HTTP_PORT` 则放行对应端口）。

2. **安装 Docker 与 Compose 插件**（Ubuntu/Debian 示例）：
   ```bash
   curl -fsSL https://get.docker.com | sudo sh
   sudo systemctl enable --now docker
   docker compose version   # 确认 v2 插件可用
   ```

3. **拉取代码**：
   ```bash
   git clone <你的仓库地址> autoresearch
   cd autoresearch
   ```

---

## 二、配置

```bash
cp deploy.env.example .env
vim .env
```

关键项：

| 变量 | 说明 |
|---|---|
| `HTTP_PORT` | 对外 HTTP 端口，默认 `80` |
| `STOCK_LLM_BASE_URL` / `_API_KEY` / `_MODEL` | **在线深度研究**的大模型凭据。**留空则该功能关闭**（网站仍可正常登录 + 展示已有研究）。任何 OpenAI 兼容端点都行（火山方舟 / OpenAI / DeepSeek / 通义 …） |
| `COOKIE_SECURE` | 纯 HTTP 部署保持 `0`；将来上 HTTPS 后改 `1` |
| `RESEARCH_WORKERS` | 后台研究并发数，轻量服务器建议 `1` |
| `RESEARCH_DAILY_QUOTA` | 每用户**每日免费**研究次数，用完后从点数余额扣 |
| `RESEARCH_CREDIT_COST` | 单次深度研究消耗的点数（免费额度用完后生效） |
| `SIGNUP_BONUS_CREDITS` | 新用户注册赠送点数，默认 `0`（不送） |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASS` | **邮箱验证码**（注册 / 找回密码 / 绑定邮箱）的 SMTP 发信配置。**留空 = 开发模式**：验证码打进服务端日志并随接口回显（`dev_code`），仅供本地联调，**上线必须配好**。QQ 邮箱用「授权码」当 `SMTP_PASS` |
| `SUB_DAILY_QUOTA` | **会员**（订阅生效中）每日免费研究次数，默认 `20`（普通用户走 `RESEARCH_DAILY_QUOTA`） |
| `PAYMENT_PROVIDER` | 支付渠道，默认 `stub`（占位，下单即模拟支付成功）。接真实渠道后改名（见「六、计费与充值」） |

> `.env` 已被 `.gitignore` 忽略，**绝不会提交**。真实 key 只存在于服务器本地。

---

## 三、启动

```bash
docker compose up -d --build
```

首次启动，backend 容器会自动用确定性 `FakeLLM` **播种两只示例股票**（000100 / 002185）的真实研究产物，所以即使还没人发起在线研究，网站也有内容可看。

查看状态与日志：
```bash
docker compose ps
docker compose logs -f backend    # 看研究任务执行
docker compose logs -f frontend
```

浏览器访问：`http://<你的服务器公网IP>`（或 `:HTTP_PORT`）。

---

## 四、首次使用

1. 打开网站 → 自动跳转登录页。
2. 点「注册」创建账号 —— **第一个注册的账号自动成为管理员**（可进后台）。
3. 登录后进入终端主界面，顶栏可见**点数余额**与**今日免费次数**；管理员还会看到「后台」入口。
4. 在右侧「候选池」点一只**未深度研究**的股票 → 主区出现精简候选卡 → 若服务器配了大模型凭据，点「发起深度研究」即可排队跑一次真实 ODR（约数分钟）。
   - 每天前 `RESEARCH_DAILY_QUOTA` 次**免费**；用完后每次扣 `RESEARCH_CREDIT_COST` 点；余额不足会提示「去充值」。
   - 研究因**系统侧原因**（大模型/基础设施故障）失败时，扣的点数会**自动退回**。

---

## 五、计费与充值（点数系统）

深度研究采用「**每日免费额度 + 点数预付**」模式，底层是一套只增不减的**流水账（ledger）**，`余额 == 流水求和`，可对账、不会算错钱。

**用户侧**：顶栏点数余额 chip → 进「点数充值」页 → 选套餐（体验包 / 标准包 / 超值包 / 月卡）→ 下单支付 → 到账。页面同时展示**最近订单**与**点数流水**。

**管理员侧**：顶栏「后台」→ 后台管理页，含四个 Tab：
- **概览**：总用户、累计/今日研究、已支付订单、累计/今日营收、未消耗点数（相当于负债）。
- **用户**：用户列表 + 余额/累计充值/累计消耗，可**手动充值 / 扣减**点数（带备注，写入流水）。
- **订单**：全站订单查询（订单号 / 用户 / 套餐 / 金额 / 状态 / 时间）。
- **流水**：全站点数流水明细。

**支付渠道（`PAYMENT_PROVIDER`）**：
- 默认 `stub`（占位）：下单后前端调 `/simulate` 直接模拟支付成功，仅用于本地演示 / 联调，**切勿在真实售卖时使用**。
- 接入真实渠道（个人无营业执照推荐 **虎皮椒 xunhupay**，有资质可用 **支付宝当面付**）：在 [billing.py](file:///Users/bytedance/Desktop/autoresearch/autoresearch/stock-research-agent/webapp/billing.py) 里实现一个继承 `PaymentProvider` 的类（`create_payment` 返回真实 `pay_url`/`qr_url`，`verify_callback` 校验渠道签名），注册进 `_PROVIDERS`，再把 `.env` 的 `PAYMENT_PROVIDER` 改为对应名称即可——**路由与数据库无需改动**。真实渠道通过**异步回调**结算，回调已做**幂等**（同一订单重复回调不会重复加点）。

> 套餐价格/点数在 [billing.py](file:///Users/bytedance/Desktop/autoresearch/autoresearch/stock-research-agent/webapp/billing.py) 的 `PLANS` 里改（金额一律用**整数分**，点数用整数，绝不用浮点）。

> ⚠️ 合规提醒：本工具定位为「信息研究工具」，对外文案避免「荐股 / 预测涨跌 / 保证收益」等表述。

---

## 六、运维常用命令

```bash
docker compose restart backend        # 改了 .env 后重启后端
docker compose up -d --build          # 拉新代码后重新构建并滚动更新
docker compose down                   # 停止（数据卷保留）
docker compose down -v                # 停止并删除数据卷（会清空用户与研究数据！慎用）

# 数据卷位置（SQLite + 研究产物）：
docker volume inspect autoresearch_stock-data
```

**备份**：所有状态都在 `stock-data` 数据卷里（`app.db` + 各 run 目录）。定期备份：
```bash
docker run --rm -v autoresearch_stock-data:/data -v $(pwd):/backup alpine \
  tar czf /backup/stock-data-$(date +%F).tar.gz -C /data .
```

---

## 七、升级到 HTTPS（有域名后）

1. 域名解析 A 记录指向服务器公网 IP。
2. 推荐在 `frontend` 容器前再加一层带 Let's Encrypt 的反代（如 `nginx-proxy + acme-companion` 或 Caddy），或直接在本 nginx 配置里挂证书。
3. 把 `.env` 的 `COOKIE_SECURE` 改为 `1` 后 `docker compose restart backend`，让会话 cookie 仅在 HTTPS 下传输。

---

## 八、本地开发（前后端分离，可选）

不走 Docker 时：

```bash
# 后端（:8000），允许本地前端跨域
cd stock-research-agent
pip install -r requirements.txt
DEV_CORS_ORIGIN=http://localhost:5173 \
STOCK_DATA_DIR=/tmp/stock-terminal-data \
uvicorn webapp.app:app --reload --port 8000

# 前端（:5173），指向本地后端
cd stock-terminal
echo 'VITE_RESEARCH_API=http://127.0.0.1:8000' > .env.local
pnpm install && pnpm dev
```
