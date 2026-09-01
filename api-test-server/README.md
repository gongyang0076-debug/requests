# API Test Server

这是接口自动化项目的可控被测服务。当前提供 FastAPI 健康检查，并通过 SQLAlchemy + PyMySQL 连接真实 MySQL、创建 `users` 表。

## 当前接口

```text
GET /health
GET /health/db
```

成功响应：

```json
{
  "status": "ok"
}
```

`/health` 只验证应用进程存活；`/health/db` 会实际执行数据库查询。数据库配置错误或不可用时返回 HTTP 503 和稳定、无敏感信息的错误描述。

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

## MySQL 配置

复制示例配置并填写本地测试凭据：

```powershell
Copy-Item .env.example .env
```

服务读取以下环境变量：

```text
DB_HOST
DB_PORT
DB_USER
DB_PASSWORD
DB_NAME
```

`.env` 已被 Git 忽略，不得提交真实密码。测试必须使用隔离数据库 `api_test`，不使用 SQLite。服务启动时会创建当前 Sprint 所需的 `users` 表。

本机 Sprint 9 验收使用已有的 `mysql:8.4.5` Docker 镜像和 3308 端口。下面的命令通过当前 Shell 环境变量传递密码，不把密码写入命令或仓库：

```powershell
$env:MYSQL_ROOT_PASSWORD = Read-Host "MySQL root password" -MaskInput
$env:MYSQL_PASSWORD = Read-Host "MySQL api_test_user password" -MaskInput

docker run --name api-test-mysql `
  --detach `
  --publish 127.0.0.1:3308:3306 `
  --env MYSQL_ROOT_PASSWORD `
  --env MYSQL_DATABASE=api_test `
  --env MYSQL_USER=api_test_user `
  --env MYSQL_PASSWORD `
  mysql:8.4.5
```

如果本地已有可用的隔离 MySQL，也可以直接填写对应连接信息，不要求必须使用 Docker。

## 启动服务

```powershell
uvicorn app.main:app --reload
```

启动后访问 `http://127.0.0.1:8000/health`。

## 运行服务测试

```powershell
python -m pytest -v
```

数据库测试会真实执行连接、建表、写入、读取和清理，因此运行前必须保证 `.env` 指向可用的 `api_test` MySQL 数据库。
