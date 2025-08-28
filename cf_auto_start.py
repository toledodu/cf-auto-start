#!/usr/bin/env python3
import requests
import base64
import json
import time
import os
# 只保留必要的telegram导入（适配v20.7）
from telegram import Bot
from telegram.constants import ParseMode

# 从环境变量读取CF配置
def get_config():
    return [
        {
            "username": os.getenv('CF_USERNAME_1'),
            "password": os.getenv('CF_PASSWORD_1'),
            "api_endpoint": "api.cf.ap21.hana.ondemand.com",
            "org": os.getenv('CF_ORG_1'),
            "space": os.getenv('CF_SPACE_1', 'dev'),
            "apps": [app.strip() for app in os.getenv('CF_APPS_1', '').split(',') if app.strip()]
        },
        {
            "username": os.getenv('CF_USERNAME_2'),
            "password": os.getenv('CF_PASSWORD_2'),
            "api_endpoint": "api.cf.us10-001.hana.ondemand.com",
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
        self.session.headers.update({"Content-Type": "application/json", "Accept": "application/json"})
        self.api_endpoint = None

    def discover_auth_endpoint(self, api_endpoint):
        try:
            if not api_endpoint.startswith('https://'):
                api_endpoint = f"https://{api_endpoint}"
            info_url = f"{api_endpoint}/v2/info"
            info_response = self.session.get(info_url, timeout=15, verify=True)
            if info_response.status_code == 200:
                return info_response.json().get("authorization_endpoint", "")
            print(f"❌ 获取API信息失败，状态码：{info_response.status_code}")
            return None
        except Exception as e:
            print(f"⚠️ 发现认证端点错误：{e}")
            return None

    def login(self, username, password, api_endpoint):
        print(f"🔐 登录账号：{username}")
        if not api_endpoint.startswith('https://'):
            api_endpoint = f"https://{api_endpoint}"
        self.api_endpoint = api_endpoint
        auth_endpoint = self.discover_auth_endpoint(api_endpoint)
        if not auth_endpoint:
            print("❌ 未找到认证端点，登录失败")
            return False

        try:
            token_url = f"{auth_endpoint}/oauth/token"
            encoded_auth = base64.b64encode("cf:".encode()).decode()
            headers = {"Authorization": f"Basic {encoded_auth}", "Content-Type": "application/x-www-form-urlencoded"}
            data = {"grant_type": "password", "username": username, "password": password}
            response = self.session.post(token_url, headers=headers, data=data, timeout=30)
            
            if response.status_code == 200:
                access_token = response.json()["access_token"]
                self.session.headers.update({"Authorization": f"Bearer {access_token}"})
                print("✅ 登录成功")
                return True
            print(f"❌ 登录失败，状态码：{response.status_code}，响应：{response.text[:200]}")
            return False
        except Exception as e:
            print(f"⚠️ 登录错误：{e}")
            return False

    def get_org_guid(self, org_name):
        try:
            response = self.session.get(f"{self.api_endpoint}/v3/organizations?names={org_name}", timeout=15)
            if response.status_code == 200 and response.json()["resources"]:
                org_guid = response.json()["resources"][0]["guid"]
                print(f"✅ 找到组织 {org_name}（GUID：{org_guid}）")
                return org_guid
            print(f"❌ 找不到组织 {org_name}")
            return None
        except Exception as e:
            print(f"⚠️ 获取组织错误：{e}")
            return None

    def get_space_guid(self, org_guid, space_name):
        try:
            response = self.session.get(f"{self.api_endpoint}/v3/spaces?names={space_name}&organization_guids={org_guid}", timeout=15)
            if response.status_code == 200 and response.json()["resources"]:
                space_guid = response.json()["resources"][0]["guid"]
                print(f"✅ 找到空间 {space_name}（GUID：{space_guid}）")
                return space_guid
            print(f"❌ 找不到空间 {space_name}")
            return None
        except Exception as e:
            print(f"⚠️ 获取空间错误：{e}")
            return None

    def get_app_guid(self, app_name, space_guid):
        try:
            response = self.session.get(f"{self.api_endpoint}/v3/apps?names={app_name}&space_guids={space_guid}", timeout=15)
            if response.status_code == 200 and response.json()["resources"]:
                app_guid = response.json()["resources"][0]["guid"]
                print(f"✅ 找到应用 {app_name}（GUID：{app_guid}）")
                return app_guid
            print(f"❌ 找不到应用 {app_name}")
            return None
        except Exception as e:
            print(f"⚠️ 获取应用错误：{e}")
            return None

    def get_app_status(self, app_guid):
        try:
            response = self.session.get(f"{self.api_endpoint}/v3/apps/{app_guid}", timeout=15)
            if response.status_code == 200:
                status = response.json().get("state", "UNKNOWN")
                print(f"📊 应用状态：{status}")
                return status
            print(f"❌ 获取应用状态失败，状态码：{response.status_code}")
            return None
        except Exception as e:
            print(f"⚠️ 获取状态错误：{e}")
            return None

    def start_application(self, app_guid, app_name):
        try:
            print(f"🚀 启动应用 {app_name}")
            response = self.session.post(f"{self.api_endpoint}/v3/apps/{app_guid}/actions/start", timeout=30)
            if response.status_code in [200, 201]:
                print("✅ 启动命令发送成功")
                return True
            print(f"❌ 启动失败，状态码：{response.status_code}，响应：{response.text[:200]}")
            return False
        except Exception as e:
            print(f"⚠️ 启动错误：{e}")
            return False

    def wait_for_app_start(self, app_guid, app_name, max_wait=60):
        print(f"⏳ 等待应用 {app_name} 启动（超时：{max_wait}秒）")
        start_time = time.time()
        while time.time() - start_time < max_wait:
            status = self.get_app_status(app_guid)
            if status == "STARTED":
                print(f"🎉 应用 {app_name} 启动成功")
                return True
            elif status == "STOPPED":
                print(f"❌ 应用 {app_name} 启动失败（状态：STOPPED）")
                return False
            time.sleep(3)
        print(f"⏰ 应用 {app_name} 启动超时")
        return False

# 简化Telegram消息发送（移除复杂依赖）
def send_telegram_message(message):
    if not (TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID):
        print("⚠️ Telegram配置缺失，跳过消息发送")
        return
    try:
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=f"【CF应用启动结果】\n\n{message}\n\n时间：{time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(time.time() + 8*3600))}",
            parse_mode=ParseMode.MARKDOWN
        )
        print("📤 Telegram消息发送成功")
    except Exception as e:
        print(f"⚠️ 发送Telegram错误：{e}")

def main():
    print("🚀 Cloud Foundry 应用自动启动脚本")
    print("=" * 50)
    client = CFMobileClient()
    total_success = 0
    total_apps = 0
    result_msg = []

    for account in ACCOUNTS:
        username = account["username"]
        print(f"\n--- 处理账号：{username} ---")
        if not client.login(username, account["password"], account["api_endpoint"]):
            result_msg.append(f"❌ 账号 {username}：登录失败")
            continue
        
        org_guid = client.get_org_guid(account["org"])
        if not org_guid:
            result_msg.append(f"❌ 账号 {username}：未找到组织 {account['org']}")
            continue
        
        space_guid = client.get_space_guid(org_guid, account["space"])
        if not space_guid:
            result_msg.append(f"❌ 账号 {username}：未找到空间 {account['space']}")
            continue
        
        apps = account["apps"]
        total_apps += len(apps)
        success = 0
        app_results = []
        for app in apps:
            app_guid = client.get_app_guid(app, space_guid)
            if not app_guid:
                app_results.append(f"❌ {app}：未找到")
                continue
            if client.get_app_status(app_guid) == "STARTED":
                app_results.append(f"✅ {app}：已运行")
                success += 1
                continue
            if client.start_application(app_guid, app) and client.wait_for_app_start(app_guid, app):
                app_results.append(f"🎉 {app}：启动成功")
                success += 1
            else:
                app_results.append(f"❌ {app}：启动失败")
        
        total_success += success
        result_msg.append(f"\n✅ 账号 {username}：{success}/{len(apps)} 个应用成功")
        result_msg.extend(app_results)
    
    final_msg = f"总结果：{total_success}/{total_apps} 个应用启动成功\n\n" + "\n".join(result_msg)
    print(f"\n{final_msg}")
    send_telegram_message(final_msg)

if __name__ == "__main__":
    main()
