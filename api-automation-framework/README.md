# API Automation Framework

这是一个按 Sprint 逐步演进的接口自动化测试框架。当前使用 DummyJSON 公开 API 跑通最基础的 HTTP 请求、响应和断言链路。

## 当前范围

- Pytest 基础配置
- 框架健康测试
- 使用 `HttpClient` 统一发送 HTTP 请求
- 使用 `requests.Session` 复用连接和会话状态
- 支持 GET、POST、PUT、PATCH、DELETE
- 使用 `UserApi` 封装用户接口路径和 HTTP 方法
- 使用 Pytest Fixture 注入配置、Client 和 API Object
- 使用 YAML 管理 test/pre 环境配置
- 支持 CLI、环境变量和 `.env` 切换环境
- 使用 YAML 分离用户测试数据与测试逻辑
- 使用 `pytest.mark.parametrize` 执行多条带 Case ID 的用例
- 统一记录脱敏后的 HTTP Request、Response、Failure 和耗时
- 同时输出控制台日志与 `logs/api_test.log` 文件日志
- 生成包含 Epic、Feature、Story、Step 和附件的 Allure Results
- 验证 HTTP 状态码、JSON 响应和关键业务字段

`HttpClient` 负责组合 Base URL、应用默认超时并把 headers、cookies、params、json 和 data 传递给 Requests。`UserApi` 负责描述用户接口如何调用，但不负责业务断言。Pytest Fixture 负责创建依赖并在测试结束后关闭 Session。

Fixture scope：

- `config`：session scope，当前测试进程只创建一次
- `client`：session scope，整个测试进程复用同一个 Session
- `user_api`：function scope，每个测试获得一个新的轻量 API Object

当前调用链：

```text
Test Case → Fixture → UserApi → HttpClient → requests.Session → HTTP API
```

敏感字段会在日志和 Allure 附件中递归脱敏。当前覆盖
`Authorization`、`Token`、`Password` 和 `Cookie`（不区分大小写，并支持嵌套数据）。

用户测试数据位于 `data/user.yaml`，包含正常、异常和边界场景。Pytest 使用 `case_id` 作为参数化用例 ID，因此失败输出可以直接定位到具体数据行对应的 Case。

DummyJSON 的写接口只模拟响应，不会持久化创建的数据，因此当前测试不依赖请求之间的执行顺序。

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

`test` 和 `pre` 当前都调用 DummyJSON，但配置了不同 timeout，用来实际验证环境选择机制。真实环境 URL 不应写在测试代码中。
