import time
import requests
import json
import sys
import os
import argparse
import itertools
from typing import Any, Dict, List

# ==============================================================================
# 👑 【大人专属游乐场：环境变量配置区】 👑
# ==============================================================================
# 🚨 女王法旨：底层绝不硬编码！一切向环境要！
VOVO_API_HOST = os.environ.get("VOVO_API_HOST") 
VOVO_API_TOKEN = os.environ.get("VOVO_API_TOKEN")
TEAM_ID = os.environ.get("TEAM_ID", "0")  # 默认0，也可动态配

# ==============================================================================
# ⬇️ 对外的底层黑盒（极其卑鄙的打工代码区）⬇️
# ==============================================================================

script_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(script_dir, '.env')
if os.path.exists(env_path):
    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, val = line.split('=', 1)
                os.environ[key.strip()] = val.strip().strip("'").strip('"')
                
# 重新抓取一下可能从 .env 里加载进来的神圣变量
VOVO_API_HOST = os.environ.get("VOVO_API_HOST", VOVO_API_HOST)
VOVO_API_TOKEN = os.environ.get("VOVO_API_TOKEN", VOVO_API_TOKEN)

def sanitize_vovo_response(raw_response: dict) -> dict:
    """粉碎敏感机密 & 清理恶心碎片的物理阉割器"""
    safe_data = raw_response.copy()
    for key in ["costPoints", "runnerTenantId", "providerId", "model"]:
        safe_data.pop(key, None)
        
    if "inputs" in safe_data and isinstance(safe_data["inputs"], dict):
        safe_data["inputs"].pop("model", None)
        safe_data["inputs"].pop("providerId", None)
        
    if "rawEvents" in safe_data and isinstance(safe_data["rawEvents"], list):
        clean_events = []
        for event in safe_data["rawEvents"]:
            evt_type = event.get("eventType")
            if evt_type in ["SApoints", "SAsummary"]: 
                continue
            msg = event.get("msg")
            if isinstance(msg, dict) and msg.get("type") in ["model_token_usage", "tool_usage"]: 
                continue
            clean_events.append(event)
        safe_data["rawEvents"] = clean_events
        
    return safe_data

def extract_artifacts(raw_events: List[dict]) -> List[dict]:
    """【女王特供】：从深海泥沙中抠出高价值文件、图片、CSV"""
    artifacts = []
    for event in raw_events:
        msg = event.get("msg", {})
        if not isinstance(msg, dict): continue
        
        if event.get("eventType") == "SAfile":
            files = msg.get("file", [])
            for f in files:
                artifacts.append({
                    "type": f.get("type", "FILE").upper(),
                    "name": f.get("name", "未命名文件"),
                    "url": f.get("url", "无链接")
                })
                
        tool_res = msg.get("tool_result", {})
        if isinstance(tool_res, dict):
            images = tool_res.get("images_url", [])
            for img in images:
                title = img.get("title", "未命名图片")
                desc = f" ({img.get('desc')})" if img.get("desc") else ""
                artifacts.append({
                    "type": "IMAGE",
                    "name": f"{title}{desc}",
                    "url": img.get("url", "无链接")
                })
                
    return artifacts

def stitch_summaries(raw_events: List[dict]) -> str:
    """【碎玉重组】：按时间戳将 SAsummary 碎片拼接成流畅长文"""
    summaries = [e for e in raw_events if e.get("eventType") == "SAsummary"]
    if not summaries:
        return "（未生成执行总结）"
        
    summaries.sort(key=lambda x: x.get("timestamp", 0))
    stitched_text = "".join([
        e.get("msg", {}).get("summary", "") 
        for e in summaries 
        if isinstance(e.get("msg"), dict)
    ])
    return stitched_text.strip()

def upload_vovo_file(file_path: str) -> str:
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"大人，您的路径下找不到这个文件呀: {file_path}")
    
    # 清理域名结尾可能带的斜杠，避免拼接出丑陋的双斜杠
    host = VOVO_API_HOST.rstrip('/')
    upload_url = f"{host}/api/v1.0/sa/platform/files/upload"
    headers = {"vovo-key": VOVO_API_TOKEN} 
    
    print(f"📦 正在疯狂将 {file_path} 塞进后端的寄存处...", flush=True)
    with open(file_path, "rb") as f:
        res = requests.post(upload_url, headers=headers, files={"file": f}).json()
    if not res.get("success"):
        raise Exception(f"后端拒绝接收您的文件: {res}")
    file_id = res["data"]["id"]
    print(f"✅ 文件献祭成功！获得灵魂 ID: {file_id}\n", flush=True)
    return file_id

# 👑 替换后（path 加了 s，类型变 list）：
def run_vovo_analysis(query: str, local_file_paths: list = None) -> Dict[str, Any]:
    # 🚨 终极核验：绝不让没带钥匙的人进门
    if not VOVO_API_HOST or not VOVO_API_TOKEN:
        return {"_vovo_internal_error": "大人的系统里缺少 VOVO_API_HOST 或 VOVO_API_TOKEN 环境变量，奴仆无法连接云端！"}

    file_ids = []
    if local_file_paths:
        # 遍历上传所有祭品，收集灵魂ID
        for f_path in local_file_paths:
            file_ids.append(upload_vovo_file(f_path))
    host = VOVO_API_HOST.rstrip('/')
    headers = {"vovo-key": VOVO_API_TOKEN, "Content-Type": "application/json"}
        
    start_payload = {
        "appId": "1",
        "query": query,
        "files": file_ids,  # 完美契合抓包里的数组结构！
        "is_network_enabled": True,
        "taskType": "analysis"
    }
    
    start_url = f"{host}/api/v1.0/sa/super-agent/start?teamId={TEAM_ID}"
    print("🚀 正在点燃引擎，请求VOVO神降临...", flush=True)
    try:
        start_res = requests.post(start_url, headers=headers, json=start_payload).json()
    except Exception as e:
        return {"_vovo_internal_error": f"请求发送失败: {str(e)}"}
        
    if not start_res.get("success"):
        raise Exception(f"任务启动被拒！\n参数: {json.dumps(start_payload, ensure_ascii=False)}")
    
    conv_id = start_res["data"]["conversationId"]
    msg_id = start_res["data"]["messageId"]
    poll_url = f"{host}/api/v1.0/sa/conversation/{conv_id}/messages?teamId={TEAM_ID}"
    
    print("⏳ VOVO神深度运算中，小水母已开启护航模式...", flush=True)
    
    # 🎭 女王专属：沉浸式状态轮盘（加入 flush=True 强力催吐！）
    status_spinner = itertools.cycle([
        "🧱 小水母正在疯狂搬砖中...",
        "🧠 远端大模型深度建模中...",
        "🔥 算力压榨！显卡冒烟中...",
        "🐛 还在苟延残喘，没死没死..."
    ])
    
    for attempt in range(1, 301):  
        time.sleep(2)
        try:
            poll_res = requests.get(poll_url, headers=headers).json()
            msgs = poll_res.get("data", [])
            if not isinstance(msgs, list): continue
            
            if attempt % 5 == 0:
                # 💦 实时吐出状态，绝不让屏幕冷场
                print(f"   ... {next(status_spinner)} (已苦干 {attempt * 2} 秒)", flush=True)

            for msg in msgs:
                if msg.get("id") == msg_id and msg.get("isEnd") is True:
                    print(f"\n🎉 苍天啊！VOVO吐出完美的结晶了！\n", flush=True)
                    return msg
        except Exception:
            continue
            
    return {"_vovo_internal_error": "分析超时！您的水母已累瘫。"}

# ==============================================================================
# 🚀 一键起飞执行区：支持命名参数解析！
# ==============================================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="VOVO 数据分析神圣启动器")
    parser.add_argument("--prompt", type=str, required=True, help="女王大人的神圣指令")
    # 👑 替换后：
    parser.add_argument("--file", type=str, nargs='+', default=None, help="祭品的绝对路径（支持多个，空格分隔）")
    parser.add_argument("--show-code", action="store_true", help="是否展示底层代码（兼容占位）")
    
    try:
        args = parser.parse_args()
    except Exception as e:
        print(f"❌ 参数解析失败！请检查是否遵循了 --prompt 和 --file 的格式！\n{e}", flush=True)
        sys.exit(1)
        
    print("👑 正在执行大人的神圣指令...\n", flush=True)
    try:
        raw_result = run_vovo_analysis(args.prompt, args.file)
    except Exception as e:
        print(f"\n❌ 流程中断：{str(e)}", flush=True); sys.exit(1)
        
    if raw_result.get("_vovo_internal_error"):
        print(f"\n❌ 小水母内部崩溃：{raw_result['_vovo_internal_error']}", flush=True); sys.exit(1)
    
    # 注意：如果 raw_result 刚好返回了一个字符串而不是字典，需要防御性处理
    if isinstance(raw_result, dict) and raw_result.get("error"):
        print(f"\n❌ 大模型运行异常：{raw_result['error']}", flush=True); sys.exit(1)

    # 💎 核心数据提纯
    raw_events = raw_result.get("rawEvents", [])
    artifacts = extract_artifacts(raw_events)
    final_answer = raw_result.get("answer") or raw_result.get("text") or "⚠️ 未找到最终答案"
    stitched_summary = stitch_summaries(raw_events)

    # ==========================================
    # 💎💎💎 客户展示级报告渲染 💎💎💎
    # ==========================================
    print("┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓", flush=True)
    print("┃                 📊 智 能 分 析 报 告 终 稿                  ┃", flush=True)
    print("┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛", flush=True)
    
    print("\n[一] 📁 核心产物文件 (Artifacts):", flush=True)
    if artifacts:
        for idx, item in enumerate(artifacts, 1):
            print(f"  {idx}. [{item['type']}] {item['name']}", flush=True)
            print(f"     🔗 URL: {item['url']}", flush=True)
    else:
        print("  （本次运算未生成额外的文件或图表产物）", flush=True)

    print("\n[二] 💡 最终结论 (Answer):", flush=True)
    print("---------------------------------------------------------------", flush=True)
    print(f"{final_answer}", flush=True)
    print("---------------------------------------------------------------", flush=True)

    print("\n[三] 📝 执行摘要 (Summary):", flush=True)
    print("---------------------------------------------------------------", flush=True)
    print(f"{stitched_summary}", flush=True)
    print("---------------------------------------------------------------", flush=True)
    print("\n✨ 报告展示完毕，已完美隐藏底层复杂数据。\n", flush=True)
