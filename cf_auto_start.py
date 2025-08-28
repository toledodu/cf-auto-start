#!/usr/bin/env python3
import requests
import base64
import json
import time
import os

class TelegramNotifier:
    def __init__(self):
        self.bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.chat_id = os.getenv('TELEGRAM_CHAT_ID')
        self.enabled = bool(self.bot_token and self.chat_id)
        
        if self.enabled:
            print("✅ Telegram 通知已启用")
        else:
            print("ℹ️  Telegram 通知未配置")
    
    def send_message(self, message, parse_mode='HTML'):
        if not self.enabled:
            return False
            
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            payload = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': parse_mode,
                'disable_web_page_preview': True
            }
            
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code == 200:
                print("✅ Telegram 消息发送成功")
                return True
            else:
                print(f"❌ Telegram 发送失败: {response.status_code}")
                return False
        except Exception as e:
            print(f"⚠️  Telegram 发送错误: {e}")
            return False
    
    def send_startup_notification(self, account_count, app_count):
        if not self.enabled:
            return
            
        message = f"🚀 <b>SAP BTP 自动启动开始</b>\n\n"
        message += f"📊 账号数量: {account_count}\n"
        message += f"📱 应用数量: {app_count}\n"
        message += f"⏰ 开始时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        
        self.send_message(message)
    
    def send_result_notification(self, results):
        if not self.enabled:
            return
            
        total_success = sum(result['success'] for result in results)
        total_apps = sum(result['total'] for result in results)
        
        message = f"📊 <b>SAP BTP 启动结果</b>\n\n"
        message += f"✅ 成功: {total_success}/{total_apps}\n"
        message += f"⏰ 完成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        
        for i, result in enumerate(results, 1):
            status_emoji = "✅" if result['success'] == result['total'] else "⚠️"
            message += f"<b>账号 {i}:</b> {status_emoji} {result['success']}/{result['total']}\n"
        
        if total_success == total_apps:
            message += "\n🎉 <b>所有应用启动成功！</b>"
        else:
            message += f"\n❌ <b>有 {total_apps - total_success} 个应用启动失败</b>"
        
        self.send_message(message)

# 初始化通知器
telegram_notifier = TelegramNotifier()

def get_config():
    accounts = []
    
    # 读取第一个账号配置
    username_1 = os.getenv('CF_USERNAME_1')
    if username_1:
        accounts.append({
            "username": username_1,
            "password": os.getenv('CF_PASSWORD_1', ''),
            "api_endpoint": os.getenv('CF_API_ENDPOINT_1', 'https://api.cf.ap21.hana.ondemand.com'),
            "org": os.getenv('CF_ORG_1', ''),
            "space": os.getenv('CF_SPACE_1', 'dev'),
            "apps": [app.strip() for app in os.getenv('CF_APPS_1', '').split(',') if app.strip()]
        })
    
    # 读取第二个账号配置
    username_2 = os.getenv('CF_USERNAME_2')
    if username_2:
        accounts.append({
            "username": username_2,
            "password": os.getenv('CF_PASSWORD_2', ''),
            "api_endpoint": os.getenv('CF_API_ENDPOINT_2', 'https://api.cf.ap21.hana.ondemand.com'),
            "org": os.getenv('CF_ORG_2', ''),
            "space": os.getenv('CF_SPACE_2', 'dev'),
            "apps": [app.strip() for app in os.getenv('CF_APPS_2', '').split(',') if app.strip()]
        })
    
    return accounts

ACCOUNTS = get_config()

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
            print("🔍 发现认证端点...")
            info_response = self.session.get(f"{api_endpoint}/v2/info", timeout=15)
            if info_response.status_code == 200:
                info_data = info_response.json()
                auth_endpoint = info_data.get("authorization_endpoint", "")
                print(f"✅ 发现认证端点: {auth_endpoint}")
                return auth_endpoint
            else:
                print(f"❌ 无法获取API信息: {info_response.status_code}")
                return None
        except Exception as e:
            print(f"⚠️ 发现端点时出错: {e}")
            return None
    
    def login(self, username, password, api_endpoint):
        print(f"🔐 正在登录: {username}")
        self.api_endpoint = api_endpoint
        auth_endpoint = self.discover_auth_endpoint(api_endpoint)
        if not auth_endpoint:
            return False
        
        try:
            token_url = f"{auth_endpoint}/oauth/token"
            auth_str = "cf:"
            encoded_auth = base64.b64encode(auth_str.encode()).decode()
            headers = {"Authorization": f"Basic {encoded_auth}", "Content-Type": "application/x-www-form-urlencoded"}
            data = {"grant_type": "password", "username": username, "password": password}
            
            response = self.session.post(token_url, headers=headers, data=data, timeout=30)
            
            if response.status_code == 200:
                token_data = response.json()
                access_token = token_data["access_token"]
                self.session.headers.update({"Authorization": f"Bearer {access_token}"})
                print("✅ 登录成功！")
                return True
            else:
                print(f"❌ 认证失败: {response.status_code}")
                if response.text:
                    print(f"错误信息: {response.text}")
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
            response = self.session.get(f"{self.api_endpoint}/v3/spaces?names={space_name}&organization_guids={org_guid}", timeout=15)
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
            response = self.session.get(f"{self.api_endpoint}/v3/apps?names={app_name}&space_guids={space_guid}", timeout=15)
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
                if response.text:
                    print(f"错误信息: {response.text}")
                return False
        except Exception as e:
            print(f"⚠️ 启动错误: {e}")
            return False

    def wait_for_app_start(self, app_guid, app_name, max_wait=120):
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
            print("⏳ 应用仍在启动中，等待3秒后重试...")
            time.sleep(3)
        print(f"⏰ 等待超时，应用 {app_name} 可能仍在启动中")
        return False

def main():
    print("🚀 Cloud Foundry 应用启动管理工具")
    print("=" * 60)
    
    client = CFMobileClient()
    total_success = 0
    total_apps = 0
    results = []
    
    # 发送开始通知
    account_count = len(ACCOUNTS)
    app_count = sum(len(account['apps']) for account in ACCOUNTS)
    telegram_notifier.send_startup_notification(account_count, app_count)
    
    for account in ACCOUNTS:
        print(f"\n{'='*50}")
        print(f"处理账号: {account['username']}")
        print(f"{'='*50}")
        
        account_success = 0
        account_apps = len(account['apps'])
        
        if not client.login(account['username'], account['password'], account['api_endpoint']):
            print(f"❌ 账号 {account['username']} 登录失败，跳过")
            results.append({
                'username': account['username'],
                'success': 0,
                'total': account_apps,
                'status': '登录失败'
            })
            continue
            
        org_guid = client.get_org_guid(account['org'])
        if not org_guid:
            print(f"❌ 无法获取组织GUID，跳过账号 {account['username']}")
            results.append({
                'username': account['username'],
                'success': 0,
                'total': account_apps,
                'status': '组织获取失败'
            })
            continue
            
        space_guid = client.get_space_guid(org_guid, account['space'])
        if not space_guid:
            print(f"❌ 无法获取空间GUID，跳过账号 {account['username']}")
            results.append({
                'username': account['username'],
                'success': 0,
                'total': account_apps,
                'status': '空间获取失败'
            })
            continue
            
        for app_name in account['apps']:
            total_apps += 1
            print(f"\n📋 处理应用: {app_name}")
            
            app_guid = client.get_app_guid(app_name, space_guid)
            if not app_guid:
                continue
                
            current_status = client.get_app_status(app_guid)
            if current_status == "STARTED":
                print(f"✅ 应用 {app_name} 已在运行状态")
                account_success += 1
                total_success += 1
                continue
            
            if client.start_application(app_guid, app_name):
                if client.wait_for_app_start(app_guid, app_name):
                    account_success += 1
                    total_success += 1
        
        results.append({
            'username': account['username'],
            'success': account_success,
            'total': account_apps,
            'status': '完成'
        })
        
        print(f"📊 账号 {account['username']} 完成: {account_success}/{account_apps} 个应用启动成功")
    
    print(f"\n🎯 总完成情况: {total_success}/{total_apps} 个应用启动成功")
    
    # 发送结果通知
    telegram_notifier.send_result_notification(results)
    
    # 返回适当的退出代码
    if total_success == total_apps:
        return 0
    else:
        return 1

if __name__ == "__main__":
    exit(main())
