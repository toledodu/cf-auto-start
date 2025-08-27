#!/usr/bin/env python3
import requests
import base64
import json
import time
import os

# 从环境变量读取配置
def get_config():
    return [
        {
            "username": os.getenv('CF_USERNAME', '2372497899@qq.com'),
            "password": os.getenv('CF_PASSWORD', ''),
            "api_endpoint": os.getenv('CF_API_ENDPOINT', 'https://api.cf.ap21.hana.ondemand.com'),
            "org": os.getenv('CF_ORG', ''),
            "space": os.getenv('CF_SPACE', 'dev'),
            "apps": [app.strip() for app in os.getenv('CF_APPS', '').split(',') if app.strip()]
        }
    ]

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
                return False
        except Exception as e:
            print(f"⚠️ 登录过程中出错: {e}")
            return False

    # 这里省略其他方法，保持原有逻辑不变
    # get_org_guid, get_space_guid, get_app_guid, get_app_status, start_application, wait_for_app_start 等方法

def main():
    print("🚀 Cloud Foundry 应用启动管理工具")
    print("=" * 60)
    
    client = CFMobileClient()
    
    for account in ACCOUNTS:
        print(f"\n处理账号: {account['username']}")
        
        if not client.login(account['username'], account['password'], account['api_endpoint']):
            continue
            
        org_guid = client.get_org_guid(account['org'])
        if not org_guid:
            continue
            
        space_guid = client.get_space_guid(org_guid, account['space'])
        if not space_guid:
            continue
            
        success_count = 0
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
        
        print(f"📊 完成: {success_count}/{len(account['apps'])} 个应用启动成功")

if __name__ == "__main__":
    main()