# API Automation Framework

这是一个按 Sprint 逐步演进的接口自动化测试框架。Sprint 0 只建立最小可运行的 Pytest 项目，用于验证 Python 测试环境和 Pytest 测试发现机制。

## 当前范围

- Pytest 基础配置
- 框架健康测试

HTTP 请求、API Object、Fixture、配置、数据驱动和报告能力将在后续 Sprint 中按实际问题逐步加入。

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
