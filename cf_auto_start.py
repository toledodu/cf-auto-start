#!/usr/bin/env python3
import requests
import base64
import json
import time
import os
import logging  # 新增：日志模块
from telegram import Bot
from telegram.utils.request import Request

# -------------------------- 新增：日志配置 --------------------------
def setup_logging():
    # 日志格式：时间 + 级别 + 消息
    log_format = "%(asctime)s - %(levelname)s - %(message)s"
    # 日志级别：从环境变量获取（默认 INFO，调试时可设为 DEBUG）
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, log_level, logging.INFO)  # 映射级别字符串到枚举值

    # 1. 配置控制台输出
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(log_format))

    # 2. 配置文件输出（生成 cf_auto_start.log）
    file_handler = logging.FileHandler("cf_auto_start.log", encoding="utf-8")  # 日志文件路径（脚本同目录）
    file_handler.setFormatter(logging.Formatter(log_format))

    # 3. 全局日志配置
    logging.basicConfig(
        level=level,
        handlers=[console_handler, file_handler]  # 同时输出到控制台和文件
    )
    return logging.getLogger(__name__)

# 初始化日志（脚本启动时执行）
logger = setup_logging()

# -------------------------- 原有逻辑修改（print → logger） --------------------------
def get_config():
    try:
        config = [
            {
                "username": os.getenv('CF_USERNAME_1'),
                "password": os.getenv('CF_PASSWORD_1'),
                "api_endpoint": os.getenv('CF_API_ENDPOINT_1'),  # 改为从环境变量读取（适配工作流）
                "org": os.getenv('CF_ORG_1'),
                "space": os.getenv('CF_SPACE_1', 'dev'),
                "apps": [app.strip() for app in os.getenv('CF_APPS_1', '').split(',') if app.strip()]
            },
            {
                "username": os.getenv('CF_USERNAME_2'),
                "password": os.getenv('CF_PASSWORD_2'),
                "api_endpoint": os.getenv('CF_API_ENDPOINT_2'),
                "org": os.getenv('CF_ORG_2'),
                "space": os.getenv('CF_SPACE_2', 'dev'),
                "apps": [app.strip() for app in os.getenv('CF_APPS_2', '').split(',') if app.strip()]
            }
        ]
        logger.info("成功加载配置，共 %d 个 CF 账号", len(config))
        return config
    except Exception as e:
        logger.error("加载配置失败：%s", str(e), exc_info=True)  # exc_info=True 打印堆栈信息
        return []

ACCOUNTS = get_config()
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

class CFMobileClient:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json"
        })
        self.api_endpoint = None

    def discover_auth_endpoint(self, api_endpoint):
        try:
            if not api_endpoint.startswith('https://'):
                api_endpoint = f"https://{api_endpoint}"
            info_url = f"{api_endpoint}/v2/info"
            logger.info("尝试获取 API 信息：%s", info_url)
            
            info_response = self.session.get(info_url, timeout=15, verify=True)
            info_response.raise_for_status()  # 触发 HTTP 错误（如 404/500）
            
            auth_endpoint = info_response.json().get("authorization_endpoint", "")
            if not auth_endpoint:
                logger.error("从 API 信息中未找到认证端点")
                return None
            logger.info("成功发现认证端点：%s", auth_endpoint)
            return auth_endpoint
        except requests.exceptions.RequestException as e:
            logger.error("发现认证端点失败（URL：%s）：%s", api_endpoint, str(e), exc_info=True)
            return None
        except Exception as e:
            logger.error("发现认证端点未知错误：%s", str(e), exc_info=True)
            return None

    def login(self, username, password, api_endpoint):
        logger.info("开始登录 CF 账号：%s（端点：%s）", username, api_endpoint)
        if not api_endpoint.startswith('https://'):
            api_endpoint = f"https://{api_endpoint}"
        self.api_endpoint = api_endpoint

        # 获取认证端点
        auth_endpoint = self.discover_auth_endpoint(api_endpoint)
        if not auth_endpoint:
            logger.error("账号 %s 登录失败：未获取到认证端点", username)
            return False

        try:
            token_url = f"{auth_endpoint}/oauth/token"
            encoded_auth = base64.b64encode("cf:".encode()).decode()
            headers = {
                "Authorization": f"Basic {encoded_auth}",
                "Content-Type": "application/x-www-form-urlencoded"
            }
            data = {
                "grant_type": "password",
                "username": username,
                "password": password
            }
            logger.debug("发送登录请求：%s（用户名：%s）", token_url, username)
            response = self.session.post(token_url, headers=headers, data=data, timeout=30)
            response.raise_for_status()

            access_token = response.json()["access_token"]
            self.session.headers.update({"Authorization": f"Bearer {access_token}"})
            logger.info("账号 %s 登录成功", username)
            return True
        except requests.exceptions.RequestException as e:
            logger.error("账号 %s 登录 HTTP 错误：%s（响应：%s）", 
                        username, str(e), response.text[:200] if 'response' in locals() else "无响应", 
                        exc_info=True)
            return False
        except Exception as e:
            logger.error("账号 %s 登录未知错误：%s", username, str(e), exc_info=True)
            return False

    # 以下方法均替换 print 为 logger，逻辑不变，仅示例关键修改...
    def get_org_guid(self, org_name):
        try:
            url = f"{self.api_endpoint}/v3/organizations?names={org_name}"
            logger.debug("获取组织 GUID：%s（URL：%s）", org_name, url)
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            resources = response.json()["resources"]
            if not resources:
                logger.error("未找到组织：%s", org_name)
                return None
            org_guid = resources[0]["guid"]
            logger.info("成功获取组织 %s 的 GUID：%s", org_name, org_guid)
            return org_guid
        except Exception as e:
            logger.error("获取组织 %s GUID 失败：%s", org_name, str(e), exc_info=True)
            return None

    def get_space_guid(self, org_guid, space_name):
        try:
            url = f"{self.api_endpoint}/v3/spaces?names={space_name}&organization_guids={org_guid}"
            logger.debug("获取空间 GUID：%s（组织 GUID：%s，URL：%s）", space_name, org_guid, url)
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            resources = response.json()["resources"]
            if not resources:
                logger.error("未找到空间：%s（组织 GUID：%s）", space_name, org_guid)
                return None
            space_guid = resources[0]["guid"]
            logger.info("成功获取空间 %s 的 GUID：%s", space_name, space_guid)
            return space_guid
        except Exception as e:
            logger.error("获取空间 %s GUID 失败：%s", space_name, str(e), exc_info=True)
            return None

    def get_app_guid(self, app_name, space_guid):
        try:
            url = f"{self.api_endpoint}/v3/apps?names={app_name}&space_guids={space_guid}"
            logger.debug("获取应用 GUID：%s（空间 GUID：%s，URL：%s）", app_name, space_guid, url)
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            resources = response.json()["resources"]
            if not resources:
                logger.error("未找到应用：%s（空间 GUID：%s）", app_name, space_guid)
                return None
            app_guid = resources[0]["guid"]
            logger.info("成功获取应用 %s 的 GUID：%s", app_name, app_guid)
            return app_guid
        except Exception as e:
            logger.error("获取应用 %s GUID 失败：%s", app_name, str(e), exc_info=True)
            return None

    def get_app_status(self, app_guid):
        try:
            url = f"{self.api_endpoint}/v3/apps/{app_guid}"
            logger.debug("获取应用状态：GUID=%s（URL：%s）", app_guid, url)
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            status = response.json().get("state", "UNKNOWN")
            logger.info("应用 GUID=%s 当前状态：%s", app_guid, status)
            return status
        except Exception as e:
            logger.error("获取应用 GUID=%s 状态失败：%s", app_guid, str(e), exc_info=True)
            return None

    def start_application(self, app_guid, app_name):
        try:
            url = f"{self.api_endpoint}/v3/apps/{app_guid}/actions/start"
            logger.info("开始启动应用：%s（GUID：%s，URL：%s）", app_name, app_guid, url)
            response = self.session.post(url, timeout=30)
            response.raise_for_status()
            logger.info("应用 %s 启动命令发送成功", app_name)
            return True
        except Exception as e:
            logger.error("应用 %s 启动失败：%s（响应：%s）", 
                        app_name, str(e), response.text[:200] if 'response' in locals() else "无响应", 
                        exc_info=True)
            return False

    def wait_for_app_start(self, app_guid, app_name, max_wait=60):
        logger.info("等待应用启动：%s（GUID：%s，超时时间：%d 秒）", app_name, app_guid, max_wait)
        start_time = time.time()
        while time.time() - start_time < max_wait:
            status = self.get_app_status(app_guid)
            if status == "STARTED":
                logger.info("应用 %s 启动成功（耗时：%.1f 秒）", app_name, time.time() - start_time)
                return True
            elif status == "STOPPED":
                logger.error("应用 %s 启动失败（状态保持为 STOPPED）", app_name)
                return False
            time.sleep(3)
            elapsed = time.time() - start_time
            logger.debug("应用 %s 启动中...（已等待：%.1f 秒，当前状态：%s）", app_name, elapsed, status)
        logger.warning("应用 %s 启动超时（超过 %d 秒）", app_name, max_wait)
        return False

def send_telegram_message(message):
    if not (TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID):
        logger.warning("Telegram 配置缺失（BOT_TOKEN/CHAT_ID），跳过消息发送")
        return
    try:
        request = Request(con_pool_size=8, read_timeout=10, connect_timeout=5)
        bot = Bot(token=TELEGRAM_BOT_TOKEN, request=request)
        formatted_msg = f"【GitHub Actions - CF 应用启动结果】\n{message}"
        logger.debug("发送 Telegram 消息（Chat ID：%s）：%s", TELEGRAM_CHAT_ID, formatted_msg[:100] + "...")
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=formatted_msg)
        logger.info("Telegram 消息发送成功")
    except Exception as e:
        logger.error("发送 Telegram 消息失败：%s", str(e), exc_info=True)

def main():
    logger.info("=" * 50)
    logger.info("Cloud Foundry 应用自动启动脚本开始执行（GitHub Actions）")
    logger.info("=" * 50)
    client = CFMobileClient()
    overall_success = 0
    overall_total = 0

    for account in ACCOUNTS:
        # 跳过配置不完整的账号
        required_fields = ["username", "password", "api_endpoint", "org", "apps"]
        if not all(account.get(field) for field in required_fields):
            logger.warning("跳过配置不完整的账号（缺失字段：%s）", 
                          [f for f in required_fields if not account.get(f)])
            continue
        
        username = account["username"]
        logger.info("\n" + "-" * 30)
        logger.info("开始处理账号：%s", username)
        logger.info("-" * 30)

        # 登录账号
        if not client.login(username, account["password"], account["api_endpoint"]):
            logger.error("账号 %s 处理终止：登录失败", username)
            continue
        
        # 获取组织和空间
        org_guid = client.get_org_guid(account["org"])
        if not org_guid:
            logger.error("账号 %s 处理终止：未获取到组织 GUID", username)
            continue
        space_guid = client.get_space_guid(org_guid, account["space"])
        if not space_guid:
            logger.error("账号 %s 处理终止：未获取到空间 GUID", username)
            continue
        
        # 处理应用
        apps = account["apps"]
        total = len(apps)
        success = 0
        overall_total += total
        logger.info("账号 %s 待处理应用：%s（共 %d 个）", username, apps, total)

        for app_name in apps:
            app_guid = client.get_app_guid(app_name, space_guid)
            if not app_guid:
                continue
            
            current_status = client.get_app_status(app_guid)
            if current_status == "STARTED":
                logger.info("应用 %s 已运行，无需启动", app_name)
                success += 1
                continue
            elif current_status in ["UNKNOWN", None]:
                logger.warning("应用 %s 状态未知，跳过启动", app_name)
                continue
            
            # 启动应用
            if client.start_application(app_guid, app_name):
                if client.wait_for_app_start(app_guid, app_name):
                    success += 1
        
        # 统计当前账号结果
        logger.info("账号 %s 处理完成：%d/%d 个应用启动成功", username, success, total)
        overall_success += success

    # 最终结果
    final_msg = f"""
总处理结果：
• 总应用数：{overall_total} 个
• 启动成功：{overall_success} 个
• 失败/跳过：{overall_total - overall_success} 个

执行环境：GitHub Actions
执行时间：{time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())}（UTC）
"""
    logger.info("\n" + "=" * 50)
    logger.info("脚本执行结束！%s", final_msg.strip())
    logger.info("=" * 50)
    send_telegram_message(final_msg)

if __name__ == "__main__":
    main()
