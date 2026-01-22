import os
import json
import time
import hashlib
import datetime
from xhs import XhsClient, DataFetchError
import requests

# --- 配置区 ---
# 监控关键词 (建议具体一点，避免搜出太多无关内容)
KEYWORDS = ["韶关市妇幼保健院", "韶关妇幼", "韶关产科"]
# 敏感词库 (命中这些词会标红)
NEGATIVE_WORDS = ["避雷", "坑", "态度差", "医疗事故", "垃圾", "无语", "投诉", "死了", "误诊"]

# 环境变量
COOKIE = os.environ.get("XHS_COOKIE")
PUSH_TOKEN = os.environ.get("PUSH_TOKEN")
HISTORY_FILE = "history.json"

def get_client():
    """初始化小红书客户端"""
    if not COOKIE:
        return None
    # 只需要cookie即可，库会自动处理签名
    return XhsClient(cookie=COOKIE)

def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            try:
                return set(json.load(f))
            except:
                return set()
    return set()

def save_history(history_set):
    # 只保留最近1000条，防止文件过大
    limited_history = list(history_set)[-1000:]
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(limited_history, f)

def check_risk(text):
    """检查敏感词"""
    for w in NEGATIVE_WORDS:
        if w in text:
            return True
    return False

def send_wechat(title, content):
    """发送微信推送"""
    if not PUSH_TOKEN:
        print("❌ 未设置 PUSH_TOKEN")
        return
        
    url = "http://www.pushplus.plus/send"
    data = {
        "token": PUSH_TOKEN,
        "title": title,
        "content": content,
        "template": "markdown"
    }
    try:
        requests.post(url, json=data)
        print("✅ 微信推送已发送")
    except Exception as e:
        print(f"❌ 推送失败: {e}")

def main():
    print(">>> 启动小红书监控脚本...")
    
    if not COOKIE:
        send_wechat("❌ 监控报警", "错误：未检测到 XHS_COOKIE，请去 GitHub Secrets 添加！")
        return

    client = get_client()
    history = load_history()
    new_notes = []
    
    # 状态标记
    run_success = True
    error_msg = ""

    try:
        for keyword in KEYWORDS:
            print(f"正在搜索: {keyword} ...")
            # sort='time' 表示按时间排序（最新），只抓前20条
            # note_type=0 表示所有类型（图文+视频）
            try:
                notes = client.get_note_by_keyword(keyword, sort='time', page=1, page_size=20)
            except DataFetchError as e:
                # 这是一个非常有用的捕捉：如果Cookie过期，这里会报错
                run_success = False
                error_msg = f"小红书接口拒绝访问，可能是Cookie过期了。\n报错信息: {str(e)}"
                break
            except Exception as e:
                run_success = False
                error_msg = f"未知错误: {str(e)}"
                break

            if not notes or 'items' not in notes:
                continue

            for note in notes['items']:
                # 提取核心字段
                note_id = note.get('id')
                title = note.get('note_card', {}).get('display_title', '无标题')
                user_name = note.get('note_card', {}).get('user', {}).get('nickname', '未知用户')
                # 拼接唯一指纹
                uid = hashlib.md5(note_id.encode()).hexdigest()

                if uid in history:
                    continue

                # 发现新笔记
                history.add(uid)
                is_risk = check_risk(title)
                
                # 只有命中敏感词，或者关键词本身包含"避雷"等强意图时，才视为风险
                # 如果你想所有新笔记都看，可以把下面的 if 去掉
                emoji = "🔴" if is_risk else "📝"
                risk_tag = "**[⚠️高危]** " if is_risk else ""
                
                link = f"https://www.xiaohongshu.com/explore/{note_id}"
                
                entry = f"{emoji} {risk_tag}**{title}**\n" \
                        f"> 👤 作者：{user_name}\n" \
                        f"> 🔗 [点击查看笔记]({link})"
                new_notes.append(entry)
            
            # 礼貌等待
            time.sleep(2)

    except Exception as GlobalE:
        run_success = False
        error_msg = str(GlobalE)

    # --- 最终推送逻辑 ---
    if not run_success:
        # 1. 运行失败（Cookie过期等）-> 发报警
        send_wechat("⚠️ 监控脚本运行出错", f"请检查 GitHub Action 日志或更新 Cookie。\n\n错误详情：\n{error_msg}")
    
    elif new_notes:
        # 2. 有新内容 -> 发日报
        content = "#### 🔍 小红书舆情日报\n" + "\n\n".join(new_notes)
        send_wechat(f"📢 发现 {len(new_notes)} 条新笔记", content)
        save_history(history)
        
    else:
        # 3. 运行成功但无新内容 -> 发心跳（你要的功能）
        # 我们可以只在每天早上的那一次发心跳，避免太烦，或者每次都发
        # 这里设置为每次都发，让你安心
        print("今日无新内容，发送心跳...")
        send_wechat("✅ 监控运行正常", f"脚本于 {datetime.datetime.now().strftime('%H:%M')} 成功运行。\n\n目前未发现关于 {KEYWORDS} 的新增内容。")

if __name__ == "__main__":
    main()
