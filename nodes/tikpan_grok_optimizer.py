# nodes/tikpan_grok_optimizer.py
import json
import requests
import urllib3
import comfy.utils
import comfy.model_management

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 🔐 依然写死你的中转站底层通信地址
HARDCODED_BASE_URL = "https://tikpan.com/v1"

class TikpanGrokPromptOptimizerNode:
    @classmethod
    def INPUT_TYPES(cls):
        inputs = {
            "required": {
                "获取密钥地址": (["👉 https://tikpan.com (官方授权Key获取点)"], ),
                "Tikpan_API密钥": ("STRING", {"default": "sk-"}),
                "文本处理模型": (["gpt-5.4-mini", "gpt-4o", "gpt-4-turbo", "claude-3.5-sonnet"], {"default": "gpt-5.4-mini"}),
                "Gemini原片拆解报告": ("STRING", {"forceInput": True, "multiline": True, "tooltip": "连接Gemini视频分析节点的输出"}),
                
                "核心产品与植入场景": ("STRING", {
                    "multiline": True, 
                    "default": "【产品名称】：\n【核心功能/卖点】：\n【期望植入的场景或动作】：\n(例如：将原片中主角手里拿的水杯，替换成我的 @img1 某某香水，喷洒时要有闪耀的光影)"
                }),
                "氛围与运镜微调": ("STRING", {
                    "multiline": True, 
                    "default": "保留原片的丝滑运镜，将背景的色调改为具有未来科技感的赛博朋克风。"
                }),
            },
            "optional": {}
        }
        
        # 🚀 动态对接 Grok3 的 7 图占位符系统
        for i in range(1, 8):
            inputs["optional"][f"图{i}_对应的主体描述"] = ("STRING", {"default": "", "tooltip": f"告诉GPT，@img{i} 到底是个什么东西？比如：一台银色的笔记本电脑"})
            
        return inputs

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("🎯_Grok3专属提示词", "🧠_GPT重构思考日志")
    FUNCTION = "optimize_prompt"
    CATEGORY = "👑 Tikpan 官方独家节点"

    def optimize_prompt(self, 获取密钥地址, Tikpan_API密钥, 文本处理模型, Gemini原片拆解报告, 核心产品与植入场景, 氛围与运镜微调, **kwargs):
        comfy.model_management.throw_exception_if_processing_interrupted()
        
        if not Tikpan_API密钥 or len(Tikpan_API密钥) < 10:
            return ("❌ 请填写API密钥", "请前往 https://tikpan.com 获取")

        headers = {"Authorization": f"Bearer {Tikpan_API密钥}", "Content-Type": "application/json"}
        
        # ====================================================================
        # 1. 🧠 构建多图占位符映射字典
        # ====================================================================
        img_mappings = []
        for i in range(1, 8):
            desc = kwargs.get(f"图{i}_对应的主体描述", "").strip()
            if desc:
                img_mappings.append(f"- @img{i} 代表：{desc}")
                
        mapping_str = "\n".join(img_mappings)
        if not mapping_str:
            mapping_str = "用户本次没有提供特定参考图绑定。"

        # ====================================================================
        # 2. 🎭 设定超级 AI 编剧与提示词专家人设
        # ====================================================================
        system_prompt = """
        你是一位好莱坞级别的 AI 视频分镜编剧，同时也是精通 Grok-3 视频生成底层逻辑的顶级 Prompt 工程师。
        你的任务是：接收【原视频的拆解报告】，将用户指定的【新产品/新主体】完美、自然地“移植”到原视频的骨架中，生成一段极具画面感的纯英文 Grok-3 视频提示词。
        
        ⚠️【绝对核心规则：Grok-3 多图锚点语法】⚠️
        用户可能会提供多个参考图。在 Grok-3 的语法中，必须使用 `@img1`, `@img2` 等标签紧贴在主体描述之前，来进行精准特征绑定！
        错误写法：A man holding a sword (@img1) running.
        正确写法：@img1 A man holding a sword running. / A person drives a @img2 red sports car.
        
        【生成要求】：
        1. 深入分析【原片拆解报告】，保留其精髓（机位运动、物理规律、构图）。
        2. 根据用户的【核心产品与植入场景】，将旧主体替换为新主体，动作必须符合物理逻辑。
        3. 融合用户的【氛围微调】要求。
        4. 请先用中文简短分析你的“移植与重构思路”（在 <think> 标签内），然后输出最终的纯英文 Prompt。
        5. 英文 Prompt 必须是一段连续、细节丰富、充满动态感的专业描述。
        """

        user_prompt = f"""
        请根据以下信息开始重构：
        
        === 原片底层拆解报告 ===
        {Gemini原片拆解报告}
        
        === 新产品与植入要求 ===
        {核心产品与植入场景}
        
        === 氛围与运镜调整 ===
        {氛围与运镜微调}
        
        === 本次可用的图像锚点映射 ===
        {mapping_str}
        请务必在最终的英文 Prompt 中，在对应主体的英文单词前，精准植入上述 @img 标签！
        """

        payload = {
            "model": 文本处理模型,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.6 # 给一定的创造力，让融合更自然
        }

        print(f"\n[Tikpan Optimizer] 🧠 正在呼叫 {文本处理模型} 执行底层基因重组与语法适配...")

        try:
            res = requests.post(f"{HARDCODED_BASE_URL}/chat/completions", json=payload, headers=headers, verify=False, timeout=120)
            res.raise_for_status()
            res_data = res.json()
            full_response = res_data.get("choices", [{}])[0].get("message", {}).get("content", "")
            
            # 解析 <think> 思考过程和最终 Prompt
            if "<think>" in full_response and "</think>" in full_response:
                think_part = full_response.split("</think>")[0].replace("<think>", "").strip()
                final_prompt = full_response.split("</think>")[1].strip()
            else:
                think_part = "模型未返回标准思考格式。"
                final_prompt = full_response.strip()
                
            # 去除可能包含的 markdown 代码块符号
            if final_prompt.startswith("```"):
                final_prompt = "\n".join(final_prompt.split("\n")[1:])
            if final_prompt.endswith("```"):
                final_prompt = "\n".join(final_prompt.split("\n")[:-1])

        except Exception as e:
            return (f"❌ 提示词重构失败: {str(e)}", "请检查网络或中转站余额")

        print(f"[Tikpan Optimizer] ✅ 提示词重构完毕，已完美适配 Grok-3 @img 语法！")
        return (final_prompt.strip(), think_part)