# API Automation Framework

这是一个按 Sprint 逐步演进的接口自动化测试框架。当前调用项目内的 FastAPI + MySQL 被测服务，已经跑通认证、商品 CRUD、订单创建以及支付/取消状态流转。

## 当前范围

- Pytest 基础配置
- 框架健康测试
- 使用 `HttpClient` 统一发送 HTTP 请求
- 使用 `requests.Session` 复用连接和会话状态
- 支持 GET、POST、PUT、PATCH、DELETE
- 使用 `AuthApi`、`UserApi`、`ProductApi`、`OrderApi` 封装业务接口
- 使用 Pytest Fixture 注入配置、Client 和 API Object
- 使用 YAML 管理 test/pre 环境配置
- 支持 CLI、环境变量和 `.env` 切换环境
- 使用 YAML 分离用户测试数据与测试逻辑
- 使用 `pytest.mark.parametrize` 执行多条带 Case ID 的用例
- 统一记录脱敏后的 HTTP Request、Response、Failure 和耗时
- 同时输出控制台日志与 `logs/api_test.log` 文件日志
- 生成包含 Epic、Feature、Story、Step 和附件的 Allure Results
- 使用 Fixture 管理注册用户、JWT Token 和带认证 Session
- 通过 Session Header 自动注入 `Authorization: Bearer ...`
- 使用认证 API Factory 支持 E2E Case 基于自身登录结果创建独立 Session
- 验证 HTTP 状态码、JSON 响应和关键业务字段

`HttpClient` 负责组合 Base URL、应用默认超时并把 headers、cookies、params、json 和 data 传递给 Requests。API Object 负责描述业务接口如何调用，但不负责业务断言。Pytest Fixture 负责注册用户、登录、保存 Token、创建认证 Client，并在测试结束后关闭 Session。

Fixture scope：

- `config`：session scope，当前测试进程只创建一次
- `client`：session scope，整个测试进程复用同一个 Session
- `registered_user`：session scope，本次测试进程只注册一个动态用户
- `auth_token`：session scope，只登录一次并复用 JWT
- `auth_client`：session scope，通过默认 Header 自动携带 JWT
- `user_api`：function scope，每个测试获得一个新的轻量 API Object
- `product_api`：function scope，复用认证 Client，但不在 API Object 中保存测试数据
- `order_api`：function scope，订单和商品 ID 由测试步骤动态传入
- `authenticated_api_factory`：function scope，根据 E2E 动态 Token 创建并自动关闭认证 Client

当前调用链：

```text
Test Case → Fixture → AuthApi / UserApi / ProductApi / OrderApi → HttpClient → requests.Session → FastAPI
```

敏感字段会在日志和 Allure 附件中递归脱敏。当前覆盖
`Authorization`、`Token`、`Password` 和 `Cookie`（不区分大小写，并支持嵌套数据）。

认证、商品和订单数据分别位于 `data/auth.yaml`、`data/product.yaml`、`data/order.yaml`。订单测试从商品创建响应动态获取 Product ID，再从订单创建响应动态获取 Order ID，不依赖固定数据库记录。

完整 E2E Case 位于 `tests/test_e2e_order_payment.py`，显式执行注册、登录、当前用户校验、创建商品、创建订单、支付前查询、支付和支付后查询。Token、Product ID、Order ID 均来自同一用例的前置响应。

注册用户由 Fixture 动态生成，不依赖固定用户 ID，也不依赖用例执行顺序。当前被测服务还没有用户删除接口，完整测试数据清理将在测试数据生命周期 Sprint 中实现；本阶段验收使用一次性 MySQL 容器。

## 环境要求

- Python 3.11 或更高版本
- 推荐使用 Python 3.11，与后续 GitHub Actions 运行环境保持一致

## 安装

在 `api-automation-framework` 目录执行：

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

如果系统没有 Python Launcher，请使用对应的 Python 3.11 可执行文件创建虚拟环境。

## 运行测试

使用默认 `test` 环境：

```powershell
python -m pytest -v
```

生成 Allure 原始结果：

```powershell
python -m pytest -v --alluredir=allure-results --clean-alluredir
```

`allure-results` 不需要 Allure CLI 即可生成，是框架集成的核心产物。如果本机另外安装了 Allure CLI，可以再生成并打开 HTML 报告：

```powershell
allure generate allure-results -o reports/allure-report --clean
allure open reports/allure-report
```

通过 CLI 使用 `pre` 环境：

```powershell
python -m pytest -v --env=pre
```

通过当前 Shell 的环境变量切换：

```powershell
$env:TEST_ENV = "pre"
python -m pytest -v
```

也可以复制 `.env.example` 为不会提交的 `.env`。配置优先级为：

```text
--env → TEST_ENV → test
API_BASE_URL / API_TIMEOUT → config/config.yaml
```

`test` 默认调用 `http://127.0.0.1:8000`，`pre` 默认调用 `http://127.0.0.1:8001`。URL 只存在于配置文件或环境变量中，不写在测试代码里。
