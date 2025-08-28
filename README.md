# SAP BTP 自动启动系统

自动启动 SAP BTP Cloud Foundry 环境中的应用程序，支持 Telegram 通知。

## 功能特性

- ✅ 多账号 SAP BTP 管理
- ✅ 定时自动启动应用（每天 8:30 北京时间）
- ✅ Telegram 实时通知
- ✅ 手动触发支持

## 配置要求

### GitHub Secrets 配置：

| Secret 名称 | 描述 | 必填 |
|------------|------|------|
| `TELEGRAM_BOT_TOKEN` | Telegram 机器人 Token | 是 |
| `TELEGRAM_CHAT_ID` | Telegram Chat ID | 是 |
| `CF_USERNAME_1` | SAP BTP 用户名 | 是 |
| `CF_PASSWORD_1` | SAP BTP 密码 | 是 |
| `CF_ORG_1` | SAP BTP 组织名 | 是 |
| `CF_APPS_1` | 应用列表（逗号分隔） | 是 |

## 使用说明

1. **自动运行**: 每天早上 8:30（北京时间）自动运行
2. **手动运行**: 在 GitHub Actions 页面手动触发
3. **通知**: 通过 Telegram 接收运行结果

## 本地测试

```bash
# 设置环境变量
export TELEGRAM_BOT_TOKEN="你的Token"
export TELEGRAM_CHAT_ID="你的ChatID"
export CF_USERNAME_1="你的用户名"
export CF_PASSWORD_1="你的密码"
export CF_ORG_1="你的组织"
export CF_APPS_1="应用1,应用2"

# 运行测试
python scripts/test-telegram.py
python scripts/cf-autostart.py
