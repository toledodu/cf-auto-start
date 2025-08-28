#!/usr/bin/env python3
import requests
import base64
import json
import time
import os
import logging
from telegram import Bot
from telegram.utils.request import Request

# 配置日志记录
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# 从环境变量读取配置
def get_config():
    configs = []
    
    # 第一个账号配置
    if os.getenv('CF_USERNAME_1') and os.getenv('CF_PASSWORD_1'):
        configs.append({
            "username": os.getenv('CF_USERNAME_1'),
            "password": os.getenv('CF_PASSWORD_1'),
            "api_endpoint": os.getenv('CF_API_ENDPOINT_1', 'api.cf.ap21.hana.ondemand.com'),
            "org": os.getenv('CF_ORG_1'),
            "space": os.getenv('CF_SPACE_1', 'dev'),
            "apps": [app.strip() for app in os.getenv('CF_APPS_1', '').split(',') if app.strip()]
        })
    
    # 第二个账号配置
    if os.getenv('CF_USERNAME_2') and os.getenv('CF_PASSWORD_2'):
        configs.append({
            "username": os.getenv('CF_USERNAME_2'),
            "password": os.getenv('CF_PASSWORD_2'),
            "api_endpoint": os.getenv('CF_API_ENDPOINT_2', 'api.cf.us10-001.hana.ondemand.com'),
            "org": os.getenv('CF_ORG_2'),
            "space": os.getenv('CF_SPACE_2', 'dev'),
            "apps": [app.strip() for app in os.getenv('CF_APPS_2', '').split(',') if app.strip()]
        })
    
    return configs

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
            logger.info(f"发现认证端点: {api_endpoint}")
            
            # 确保端点格式正确
            if not api_endpoint.startswith('https://'):
                api_endpoint = f"https://{api_endpoint}"
            
            info_url = f"{api_endpoint}/v2/info"
            logger.info(f"访问: {info_url}")
            
            info_response = self.session.get(info_url, timeout=15, verify=True)
            logger.info(f"响应状态码: {info_response.status_code}")
            
            if info_response.status_code == 200:
                info_data = info_response.json()
                auth_endpoint = info_data.get("authorization_endpoint", "")
                logger.info(f"发现认证端点: {auth_endpoint}")
                return auth_endpoint
            else:
                logger.error(f"无法获取API信息: {info_response.status_code}")
                logger.error(f"响应内容: {info_response.text[:200]}")
                return None
        except Exception as e:
            logger.error(f"发现端点时出错: {e}")
            return None

    def login(self, username, password, api_endpoint):
        logger.info(f"正在登录: {username}")
        
        # 确保API端点格式正确
        if not api_endpoint.startswith('https://'):
            api_endpoint = f"https://{api_endpoint}"
        
        self.api_endpoint = api_endpoint
        auth_endpoint = self.discover_auth_endpoint(api_endpoint)
        if not auth_endpoint:
            return False

        try:
            token_url = f"{auth_endpoint}/oauth/token"
            auth_str = "cf:"
            encoded_auth = base64.b64encode(auth_str.encode()).decode()
            
            headers = {
                "Authorization": f"Basic {encoded_auth}", 
                "Content-Type": "application/x-www-form-urlencoded"
            }
            
            data = {
                "grant_type": "password", 
                "username": username, 
                "password": password
            }

            response = self.session.post(token_url, headers=headers, data=data, timeout=30)

            if response.status_code == 200:
                token_data = response.json()
                access_token = token_data["access_token"]
                self.session.headers.update({"Authorization": f"Bearer {access_token}"})
                logger.info("登录成功！")
                return True
            else:
                logger.error(f"认证失败: {response.status_code}")
                logger.error(f"响应内容: {response.text[:200]}")
                return False
        except Exception as e:
            logger.error(f"登录过程中出错: {e}")
            return False

    def get_org_guid(self, org_name):
        try:
            response = self.session.get(f"{self.api_endpoint}/v3/organizations?names={org_name}", timeout=15)
            if response.status_code == 200:
                data = response.json()
                if data["resources"]:
                    org_guid = data["resources"][0]["guid"]
                    logger.info(f"找到组织: {org_name}")
                    return org_guid
                else:
                    logger.error(f"找不到组织: {org_name}")
                    return None
            else:
                logger.error(f"获取组织失败: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"获取组织错误: {e}")
            return None

    def get_space_guid(self, org_guid, space_name):
        try:
            response = self.session.get(f"{self.api_endpoint}/v3/spaces?names={space_name}&organization_guids={org_guid}",
                                        timeout=15)
            if response.status_code == 200:
                data = response.json()
                if data["resources"]:
                    space_guid = data["resources"][0]["guid"]
                    logger.info(f"找到空间: {space_name}")
                    return space_guid
                else:
                    logger.error(f"找不到空间: {space_name}")
                    return None
            else:
                logger.error(f"获取空间失败: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"获取空间错误: {e}")
            return None

    def get_app_guid(self, app_name, space_guid):
        try:
            response = self.session.get(f"{self.api_endpoint}/v3/apps?names={app_name}&space_guids={space_guid}",
                                        timeout=15)
            if response.status_code == 200:
                data = response.json()
                if data["resources"]:
                    app_guid = data["resources"][0]["guid"]
                    logger.info(f"找到应用: {app_name}")
                    return app_guid
                else:
                    logger.error(f"找不到应用: {app_name}")
                    return None
            else:
                logger.error(f"获取应用失败: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"获取应用错误: {e}")
            return None

    def get_app_status(self, app_guid):
        try:
            response = self.session.get(f"{self.api_endpoint}/v3/apps/{app_guid}", timeout=15)
            if response.status_code == 200:
                data = response.json()
                status = data.get("state", "UNKNOWN")
                logger.info(f"应用状态: {status}")
                return status
            else:
                logger.error(f"获取应用状态失败: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"获取状态错误: {e}")
            return None

    def start_application(self, app_guid, app_name):
        try:
            logger.info(f"正在启动应用: {app_name}")
            response = self.session.post(f"{self.api_endpoint}/v3/apps/{app_guid}/actions/start", timeout=30)
            if response.status_code in [200, 201]:
                logger.info("启动命令发送成功！")
                return True
            else:
                logger.error(f"启动失败: {response.status_code}")
                logger.error(f"响应内容: {response.text[:200]}")
                return False
        except Exception as e:
            logger.error(f"启动错误: {e}")
            return False

    def wait_for_app_start(self, app_guid, app_name, max_wait=120):
        logger.info(f"等待应用启动，最多等待 {max_wait} 秒...")
        start_time = time.time()
        while time.time() - start_time < max_wait:
            status = self.get_app_status(app_guid)
            if status == "STARTED":
                logger.info(f"应用 {app_name} 启动成功！")
                return True
            elif status == "STOPPED":
                logger.error(f"应用 {app_name} 启动失败")
                return False
            elif status == "CRASHED":
                logger.error(f"应用 {app_name} 启动时崩溃")
                return False
            time.sleep(5)
        logger.warning(f"等待超时，应用 {app_name} 可能仍在启动中")
        return False


def send_telegram_message(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("Telegram Bot Token 或 Chat ID 未设置，跳过发送消息")
        return False
    
    try:
        # 使用更宽松的超时设置
        request = Request(connect_timeout=20, read_timeout=20)
        bot = Bot(token=TELEGRAM_BOT_TOKEN, request=request)
        
        # 添加时间戳和格式化
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        formatted_message = f"🔄 Cloud Foundry 监控通知\n⏰ 时间: {timestamp}\n\n{message}"
        
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=formatted_message)
        logger.info("Telegram 消息发送成功")
        return True
    except Exception as e:
        logger.error(f"发送Telegram消息出错: {e}")
        # 尝试使用 requests 直接发送作为备用方案
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            data = {
                "chat_id": TELEGRAM_CHAT_ID,
                "text": message,
                "parse_mode": "HTML"
            }
            response = requests.post(url, json=data, timeout=20)
            if response.status_code == 200:
                logger.info("使用备用方法发送Telegram消息成功")
                return True
            else:
                logger.error(f"备用方法发送失败: {response.status_code} - {response.text}")
                return False
        except Exception as fallback_error:
            logger.error(f"备用发送方法也失败: {fallback_error}")
            return False


def check_telegram_connection():
    """检查Telegram连接是否正常"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("Telegram 配置不完整，无法测试连接")
        return False
    
    try:
        # 测试网络连通性
        test_response = requests.get("https://api.telegram.org", timeout=10)
        if test_response.status_code != 200:
            logger.error("无法访问 Telegram API，请检查网络连接")
            return False
        
        # 测试Bot token有效性
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getMe"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            logger.info("Telegram Bot token 有效")
            return True
        else:
            logger.error(f"Telegram Bot token 无效: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        logger.error("网络连接失败，请检查服务器网络或使用代理")
        return False
    except Exception as e:
        logger.error(f"检查Telegram连接时出错: {e}")
        return False


def main():
    logger.info("🚀 Cloud Foundry 应用启动管理工具")
    logger.info("=" * 60)
    
    # 检查Telegram连接
    telegram_connected = check_telegram_connection()
    if not telegram_connected:
        logger.warning("Telegram 连接测试失败，消息通知可能无法正常工作")
    
    client = CFMobileClient()
    overall_success_count = 0
    overall_app_count = 0
    detailed_results = []
    
    for account in ACCOUNTS:
        logger.info(f"\n处理账号: {account['username']}")
        if not client.login(account['username'], account['password'], account['api_endpoint']):
            error_msg = f"❌ 账号 {account['username']} 登录失败"
            logger.error(error_msg)
            detailed_results.append(error_msg)
            continue
            
        org_guid = client.get_org_guid(account['org'])
        if not org_guid:
            error_msg = f"❌ 无法获取组织 {account['org']} 的GUID"
            logger.error(error_msg)
            detailed_results.append(error_msg)
            continue
            
        space_guid = client.get_space_guid(org_guid, account['space'])
        if not space_guid:
            error_msg = f"❌ 无法获取空间 {account['space']} 的GUID"
            logger.error(error_msg)
            detailed_results.append(error_msg)
            continue
            
        success_count = 0
        app_count = len(account['apps'])
        overall_app_count += app_count
        account_results = []
        
        for app_name in account['apps']:
            app_guid = client.get_app_guid(app_name, space_guid)
            if not app_guid:
                app_result = f"❌ {app_name}: 未找到应用"
                account_results.append(app_result)
                continue
                
            current_status = client.get_app_status(app_guid)
            if current_status == "STARTED":
                app_result = f"✅ {app_name}: 已在运行状态"
                account_results.append(app_result)
                success_count += 1
                continue
                
            if client.start_application(app_guid, app_name):
                if client.wait_for_app_start(app_guid, app_name):
                    app_result = f"✅ {app_name}: 启动成功"
                    success_count += 1
                else:
                    app_result = f"❌ {app_name}: 启动失败或超时"
            else:
                app_result = f"❌ {app_name}: 启动命令发送失败"
            
            account_results.append(app_result)
        
        account_summary = f"📊 {account['username']}: {success_count}/{app_count} 个应用启动成功"
        logger.info(account_summary)
        detailed_results.extend([account_summary] + account_results)
        overall_success_count += success_count
    
    # 构建最终消息
    final_message = f"Cloud Foundry应用启动完成\n\n总结果: {overall_success_count}/{overall_app_count} 个应用启动成功\n\n详细结果:\n" + "\n".join(detailed_results)
    
    # 发送Telegram消息
    if telegram_connected:
        send_telegram_message(final_message)
    else:
        logger.info("由于Telegram连接问题，消息未发送")
    
    logger.info("任务执行完成")


if __name__ == "__main__":
    main()
