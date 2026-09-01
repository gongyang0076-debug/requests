# API Test Server

这是接口自动化项目的可控被测服务。Sprint 8 只提供最小 FastAPI 应用和健康检查接口，暂不包含数据库、鉴权或业务实体。

## 当前接口

```text
GET /health
```

成功响应：

```json
{
  "status": "ok"
}
```

## 环境要求

- Python 3.11 或更高版本
- 推荐使用 Python 3.11，与后续 GitHub Actions 环境保持一致

## 安装

在 `api-test-server` 目录执行：

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

如果本机没有 Python 3.11，请使用已有且兼容的 Python 版本创建虚拟环境，不要在项目中硬编码解释器路径。

## 启动服务

```powershell
uvicorn app.main:app --reload
```

启动后访问 `http://127.0.0.1:8000/health`。

## 运行服务测试

```powershell
python -m pytest -v
```
