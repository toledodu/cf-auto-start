# Cloud Foundry Auto Start

自动启动 Cloud Foundry 应用的 GitHub Actions 工作流。

## 设置步骤

1. 在 GitHub 仓库的 Settings → Secrets 中添加以下环境变量：
   - `CF_USERNAME`: Cloud Foundry 用户名
   - `CF_PASSWORD`: Cloud Foundry 密码
   - `CF_API_ENDPOINT`: API 端点
   - `CF_ORG`: 组织名称
   - `CF_APPS`: 应用名称（多个用逗号分隔）

2. 工作流会在每天 UTC 时间 8:00 自动运行
