#!/usr/bin/env python3
import requests
import base64
import json
import time
import os
from telegram import Bot
from telegram.utils.request import Request  # 添加这行导入

# 从环境变量读取配置
def get_config():
    return [
        {
            "username": os.getenv('CF_USERNAME_1'),
            "password": os.getenv('CF_PASSWORD_1'),
            "api_endpoint": "api.cf.ap21.hana.ondemand.com",  # 固定的SAP BTP端点
            "org": os.getenv('CF_ORG_1'),
            "space": os.getenv('CF_SPACE_1', 'dev'),
            "apps": [app.strip() for app in os.getenv('CF_APPS_1', '').split(',') if app.strip()]
        },
        {
            "username": os.getenv('CF_USERNAME_2'),
            "password": os.getenv('CF_PASSWORD_2'),
            "api_endpoint": "api.cf.us10-001.hana.ondemand.com",  # 固定的SAP BTP端点
            "org": os.getenv('CF_ORG_2'),
            "space": os.getenv('CF_SPACE_2', 'dev'),
            "apps": [app.strip() for app in os.getenv('CF_APPS_2', '').split(',') if app.strip()]
        }
    ]

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
            print(f"🔍 发现认证端点: {api_endpoint}")
            
            # 确保端点格式正确
            if not api_endpoint.startswith('https://'):
                api_endpoint = f"https://{api_endpoint}"
            
            info_url = f"{api_endpoint}/v2/info"
            print(f"🌐 访问: {info_url}")
            
            info_response = self.session.get(info_url, timeout=15, verify=True)
            print(f"📊 响应状态码: {info_response.status_code}")
            
            if info_response.status_code == 200:
                info_data = info_response.json()
                auth_endpoint = info_data.get("authorization_endpoint", "")
                print(f"✅ 发现认证端点: {auth_endpoint}")
                return auth_endpoint
            else:
                print(f"❌ 无法获取API信息: {info_response.status_code}")
                print(f"响应内容: {info_response.text[:200]}")
                return None
        except Exception as e:
            print(f"⚠️ 发现端点时出错: {e}")
            return None

    def login(self, username, password, api_endpoint):
        print(f"🔐 正在登录: {username}")
        
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
                print("✅ 登录成功！")
                return True
            else:
                print(f"❌ 认证失败: {response.status_code}")
                print(f"响应内容: {response.text[:200]}")
                return False
        except Exception as e:
            print(f"⚠️ 登录过程中出错: {e}")
            return False

    def get_org_guid(self, org_name):
        try:
            response = self.session.get(f"{self.api_endpoint}/v3/organizations?names={org_name}", timeout=15)
            if response.status_code == 200:
                data = response.json()
                if data["resources"]:
                    org_guid = data["resources"][0]["guid"]
                    print(f"✅ 找到组织: {org_name}")
                    return org_guid
                else:
                    print(f"❌ 找不到组织: {org_name}")
                    return None
            else:
                print(f"❌ 获取组织失败: {response.status_code}")
                return None
        except Exception as e:
            print(f"⚠️ 获取组织错误: {e}")
            return None

    def get_space_guid(self, org_guid, space_name):
        try:
            response = self.session.get(f"{self.api_endpoint}/v3/spaces?names={space_name}&organization_guids={org_guid}",
                                        timeout=15)
            if response.status_code == 200:
                data = response.json()
                if data["resources"]:
                    space_guid = data["resources"][0]["guid"]
                    print(f"✅ 找到空间: {space_name}")
                    return space_guid
                else:
                    print(f"❌ 找不到空间: {space_name}")
                    return None
            else:
                print(f"❌ 获取空间失败: {response.status_code}")
                return None
        except Exception as e:
            print(f"⚠️ 获取空间错误: {e}")
            return None

    def get_app_guid(self, app_name, space_guid):
        try:
            response = self.session.get(f"{self.api_endpoint}/v3/apps?names={app_name}&space_guids={space_guid}",
                                        timeout=15)
            if response.status_code == 200:
                data = response.json()
                if data["resources"]:
                    app_guid = data["resources"][0]["guid"]
                    print(f"✅ 找到应用: {app_name}")
                    return app_guid
                else:
                    print(f"❌ 找不到应用: {app_name}")
                    return None
            else:
                print(f"❌ 获取应用失败: {response.status_code}")
                return None
        except Exception as e:
            print(f"⚠️ 获取应用错误: {e}")
            return None

    def get_app_status(self, app_guid):
        try:
            response = self.session.get(f"{self.api_endpoint}/v3/apps/{app_guid}", timeout=15)
            if response.status_code == 200:
                data = response.json()
                status = data.get("state", "UNKNOWN")
                print(f"📊 应用状态: {status}")
                return status
            else:
                print(f"❌ 获取应用状态失败: {response.status_code}")
                return None
        except Exception as e:
            print(f"⚠️ 获取状态错误: {e}")
            return None

    def start_application(self, app_guid, app_name):
        try:
            print(f"🚀 正在启动应用: {app_name}")
            response = self.session.post(f"{self.api_endpoint}/v3/apps/{app_guid}/actions/start", timeout=30)
            if response.status_code in [200, 201]:
                print("✅ 启动命令发送成功！")
                return True
            else:
                print(f"❌ 启动失败: {response.status_code}")
                print(f"响应内容: {response.text[:200]}")
                return False
        except Exception as e:
            print(f"⚠️ 启动错误: {e}")
            return False

    def wait_for_app_start(self, app_guid, app_name, max_wait=60):
        print(f"⏳ 等待应用启动，最多等待 {max_wait} 秒...")
        start_time = time.time()
        while time.time() - start_time < max_wait:
            status = self.get_app_status(app_guid)
            if status == "STARTED":
                print(f"🎉 应用 {app_name} 启动成功！")
                return True
            elif status == "STOPPED":
                print(f"❌ 应用 {app_name} 启动失败")
                return False
            time.sleep(3)
        print(f"⏰ 等待超时，应用 {app_name} 可能仍在启动中")
        return False


def send_telegram_message(message):
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        try:
            # 使用Request创建会话，避免可能的连接问题
            request = Request(con_pool_size=8)
            bot = Bot(token=TELEGRAM_BOT_TOKEN, request=request)
            bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
            print("📤 Telegram消息发送成功")
        except Exception as e:
            print(f"⚠️ 发送Telegram消息出错: {e}")
    else:
        print("⚠️ 未配置Telegram令牌或聊天ID，无法发送消息")


def main():
    print("🚀 Cloud Foundry 应用启动管理工具")
    print("=" * 60)
    client = CFMobileClient()
    overall_success_count = 0
    overall_app_count = 0
    
    for account in ACCOUNTS:
        print(f"\n处理账号: {account['username']}")
        if not client.login(account['username'], account['password'], account['api_endpoint']):
            print(f"❌ 账号 {account['username']} 登录失败，跳过处理")
            continue
            
        org_guid = client.get_org_guid(account['org'])
        if not org_guid:
            print(f"❌ 无法获取组织 {account['org']} 的GUID，跳过处理")
            continue
            
        space_guid = client.get_space_guid(org_guid, account['space'])
        if not space_guid:
            print(f"❌ 无法获取空间 {account['space']} 的GUID，跳过处理")
            continue
            
        success_count = 0
        app_count = len(account['apps'])
        overall_app_count += app_count
        
        for app_name in account['apps']:
            app_guid = client.get_app_guid(app_name, space_guid)
            if not app_guid:
                continue
                
            current_status = client.get_app_status(app_guid)
            if current_status == "STARTED":
                print(f"✅ 应用 {app_name} 已在运行状态")
                success_count += 1
                continue
                
            if client.start_application(app_guid, app_name):
                if client.wait_for_app_start(app_guid, app_name):
                    success_count += 1
        
        print(f"📊 完成: {success_count}/{app_count} 个应用启动成功")
        overall_success_count += success_count
    
    send_telegram_message(f"Cloud Foundry应用启动结果: {overall_success_count}/{overall_app_count} 个应用启动成功")


if __name__ == "__main__":
    main()
