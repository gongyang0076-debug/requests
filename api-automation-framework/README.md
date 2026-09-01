# API Automation Framework

这是一个按 Sprint 逐步演进的接口自动化测试框架。当前使用 DummyJSON 公开 API 跑通最基础的 HTTP 请求、响应和断言链路。

## 当前范围

- Pytest 基础配置
- 框架健康测试
- 使用 `HttpClient` 统一发送 HTTP 请求
- 使用 `requests.Session` 复用连接和会话状态
- 支持 GET、POST、PUT、PATCH、DELETE
- 验证 HTTP 状态码、JSON 响应和关键业务字段

`HttpClient` 负责组合 Base URL、应用默认超时并把 headers、cookies、params、json 和 data 传递给 Requests。测试仍会手动创建 Client；这个依赖生命周期问题将在后续 Fixture Sprint 中解决。

当前调用链：

```text
Test Case → HttpClient → requests.Session → HTTP API
```

API Object、Fixture、配置、数据驱动和报告能力将在后续 Sprint 中按实际问题逐步加入。

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

```powershell
python -m pytest -v
```
