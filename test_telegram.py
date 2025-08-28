#!/usr/bin/env python3
import requests
import json

def test_telegram_bot():
    """测试Telegram机器人配置"""
    token = "7599252176:AAHfK_sN6AGQQfGH3bVgqayOLczC1IMF9No"
    chat_id = "773524291"
    
    print("🤖 测试Telegram机器人配置...")
    
    # 测试getMe
    response = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=10)
    if response.status_code == 200:
        bot_info = response.json()['result']
        print(f"✅ 机器人信息: @{bot_info['username']} ({bot_info['first_name']})")
    else:
        print("❌ Token无效")
        return False
    
    # 发送测试消息
    message = {
        'chat_id': chat_id,
        'text': '✅ <b>Telegram 配置测试成功！</b>\n\n机器人配置正确，可以正常接收通知。',
        'parse_mode': 'HTML'
    }
    
    response = requests.post(f"https://api.telegram.org/bot{token}/sendMessage", json=message, timeout=10)
    if response.status_code == 200:
        print("✅ 测试消息发送成功！")
        return True
    else:
        print(f"❌ 消息发送失败: {response.json()}")
        return False

if __name__ == "__main__":
    test_telegram_bot()
