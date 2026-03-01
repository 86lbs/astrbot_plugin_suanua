"""
AstrBot 算卦插件
用户发送 "算一卦" 触发本插件，生成卦象并输出本地解卦
引用输出内容发送 "ai解卦" 进行AI解卦
支持作为函数工具供 AI 调用
"""

import json
import random
import re
from pathlib import Path
from typing import Optional

from astrbot.api import llm_tool, logger, star
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.message_components import Reply
from astrbot.api.star import Context


# 八卦线条映射
TRIGRAM_LINES: dict[str, list[str]] = {
    "☰": ["━━━", "━━━", "━━━"],
    "☷": ["━ ━", "━ ━", "━ ━"],
    "☳": ["━ ━", "━ ━", "━━━"],
    "☶": ["━━━", "━ ━", "━ ━"],
    "☲": ["━━━", "━ ━", "━━━"],
    "☵": ["━ ━", "━━━", "━ ━"],
    "☱": ["━━━", "━━━", "━ ━"],
    "☴": ["━ ━", "━━━", "━━━"],
}


def get_hexagram_display(hexagram_data: dict) -> str:
    """将卦象转换为六行显示格式"""
    gua_xiang = hexagram_data.get("卦象", "")
    
    if not gua_xiang:
        return "卦象缺失"
    
    if len(gua_xiang) == 1 and gua_xiang in TRIGRAM_LINES:
        lines = TRIGRAM_LINES[gua_xiang]
        return "\n".join(lines + lines)
    
    if len(gua_xiang) == 2:
        upper_lines = TRIGRAM_LINES.get(gua_xiang[0], ["?", "?", "?"])
        lower_lines = TRIGRAM_LINES.get(gua_xiang[1], ["?", "?", "?"])
        return "\n".join(upper_lines + lower_lines)
    
    return gua_xiang


def validate_hexagram_data(data: dict, name: str) -> bool:
    """验证卦象数据结构"""
    required_fields = ["卦象", "性质", "含义", "爻辞"]
    for field in required_fields:
        if field not in data:
            logger.warning(f"卦象「{name}」缺少字段: {field}")
            return False
        if field == "爻辞" and not isinstance(data[field], list):
            logger.warning(f"卦象「{name}」爻辞字段类型错误")
            return False
    return True


class SuanguaPlugin(star.Star):
    """算卦插件"""
    
    def __init__(self, context: Context):
        super().__init__(context)
        self._hexagrams: dict[str, dict] = {}
        self._loaded = False
    
    def _load_hexagrams(self) -> bool:
        """加载六十四卦数据"""
        if self._loaded:
            return bool(self._hexagrams)
        
        data_file = Path(__file__).parent / "hexagrams.json"
        try:
            with open(data_file, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
            
            # 验证数据结构
            valid_count = 0
            for name, data in raw_data.items():
                if validate_hexagram_data(data, name):
                    self._hexagrams[name] = data
                    valid_count += 1
            
            if valid_count == 0:
                logger.error("没有有效的卦象数据")
                return False
            
            logger.info(f"成功加载 {valid_count} 个卦象")
            self._loaded = True
            return True
            
        except FileNotFoundError:
            logger.error(f"卦象数据文件不存在: {data_file}")
            return False
        except json.JSONDecodeError as e:
            logger.error(f"卦象数据文件格式错误: {e}")
            return False
        except Exception as e:
            logger.error(f"加载卦象数据失败: {e}")
            return False
    
    async def initialize(self):
        """插件初始化"""
        if self._load_hexagrams():
            logger.info("算卦插件已加载")
        else:
            logger.warning("算卦插件加载失败，请检查 hexagrams.json 文件")
    
    def _get_reply_content(self, event: AstrMessageEvent) -> tuple[bool, str]:
        """获取引用消息的内容"""
        messages = event.get_messages()
        for msg in messages:
            if isinstance(msg, Reply):
                if hasattr(msg, 'message_str') and isinstance(msg.message_str, str) and msg.message_str.strip():
                    return True, msg.message_str.strip()
                
                reply_text = ""
                if hasattr(msg, 'chain') and msg.chain:
                    for comp in msg.chain:
                        if hasattr(comp, 'text') and isinstance(comp.text, str):
                            reply_text += comp.text
                if reply_text.strip():
                    return True, reply_text.strip()
                
        return False, ""
    
    def _build_divination_result(self, hexagram_name: str, hexagram_data: dict, question: str = "") -> str:
        """构建算卦结果（公共方法）"""
        hexagram_display = get_hexagram_display(hexagram_data)
        
        lines = []
        lines.append(f"【{hexagram_name}卦】")
        lines.append(hexagram_display)
        lines.append(f"卦性：{hexagram_data.get('性质', '未知')}")
        lines.append(f"含义：{hexagram_data.get('含义', '未知')}")
        
        yao_ci_list = hexagram_data.get('爻辞', [])
        if yao_ci_list:
            yao_ci = random.choice(yao_ci_list)
            lines.append(f"爻辞：{yao_ci}")
        
        interpretations = [
            "当前运势稳中有进，宜保持耐心。",
            "事业方面：脚踏实地，稳扎稳打。",
            "感情方面：真诚待人，缘分自来。",
            "财运方面：量入为出，积少成多。",
            "健康方面：劳逸结合，注意休息。"
        ]
        
        lines.append("运势指引：")
        for interp in random.sample(interpretations, min(3, len(interpretations))):
            lines.append(f"  • {interp}")
        
        result = "\n".join(lines)
        
        if question:
            result = f"求卦问题：{question}\n\n{result}"
        
        return result
    
    def _extract_hexagram_name(self, content: str) -> Optional[str]:
        """从内容中提取卦名（使用正则）"""
        # 匹配行首的【xxx卦】格式
        pattern = r"^【(.+?)卦】"
        match = re.search(pattern, content, re.MULTILINE)
        if match:
            name = match.group(1)
            if name in self._hexagrams:
                return name
        return None
    
    async def _get_ai_interpretation(self, event: AstrMessageEvent, hexagram_name: str, hexagram_data: dict) -> str:
        """调用 AI 进行解卦"""
        try:
            provider = self.context.get_using_provider(umo=event.unified_msg_origin)
        except Exception as e:
            logger.error(f"获取 provider 失败: {e}")
            return "未检测到可用的大语言模型提供商。"
        
        if not provider:
            return "未检测到可用的大语言模型提供商。"
        
        user_prompt = f"""请根据以下卦象为求卦者解卦。

卦名：{hexagram_name}
卦象：{hexagram_data.get('卦象', '未知')}
性质：{hexagram_data.get('性质', '未知')}
基本含义：{hexagram_data.get('含义', '未知')}

请提供详细的解卦分析，用通俗易懂的语言，给出积极正面的指引。"""

        system_prompt = "你是一位精通易经的算命大师，擅长用通俗易懂的语言为人们解卦指引。"
        
        try:
            llm_resp = await provider.text_chat(
                prompt=user_prompt,
                context=[],
                system_prompt=system_prompt,
                image_urls=[],
            )
            
            # 获取返回内容
            completion_text = getattr(llm_resp, "completion_text", None)
            if completion_text and isinstance(completion_text, str) and completion_text.strip():
                return completion_text.strip()
            
            text = getattr(llm_resp, "text", None)
            if text and isinstance(text, str) and text.strip():
                return text.strip()
            
            logger.warning(f"AI 返回内容为空，响应对象: {type(llm_resp).__name__}")
            return "AI未返回有效内容，请稍后重试。"
            
        except Exception as e:
            logger.error(f"AI 解卦失败: {e}")
            return f"AI解卦出错，请稍后重试。"
    
    @llm_tool(name="divine_hexagram")
    async def divine_hexagram(self, event: AstrMessageEvent, question: str = "") -> str:
        """易经算卦工具。当用户想要算卦、占卜、预测运势、询问未来时使用此工具。
        
        Args:
            question(string): 用户想要询问的问题或想要了解的方面（可选）
        """
        # 检查是否有引用消息
        has_reply, reply_content = self._get_reply_content(event)
        if has_reply and reply_content:
            question = reply_content
        
        if not self._hexagrams:
            # 尝试重新加载
            if not self._load_hexagrams():
                return "卦象数据加载失败，请联系管理员检查插件配置。"
        
        # 生成卦象
        hexagram_name = random.choice(list(self._hexagrams.keys()))
        hexagram_data = self._hexagrams[hexagram_name]
        
        return self._build_divination_result(hexagram_name, hexagram_data, question)
    
    @filter.command("算一卦")
    async def divine(self, event: AstrMessageEvent):
        """算一卦 - 生成卦象并输出本地解卦"""
        logger.info("收到算卦请求")
        
        if not self._hexagrams:
            # 尝试重新加载
            if not self._load_hexagrams():
                yield event.plain_result("卦象数据加载失败，请联系管理员检查插件配置。")
                return
        
        hexagram_name = random.choice(list(self._hexagrams.keys()))
        hexagram_data = self._hexagrams[hexagram_name]
        
        result = self._build_divination_result(hexagram_name, hexagram_data)
        result += "\n\n引用此消息发送「ai解卦」可获取AI详细解读"
        
        yield event.plain_result(result)
    
    @filter.command("ai解卦")
    async def ai_divine(self, event: AstrMessageEvent):
        """ai解卦 - 引用算卦结果进行AI解卦"""
        logger.info("收到AI解卦请求")
        
        if not self._hexagrams:
            yield event.plain_result("卦象数据加载失败，请联系管理员检查插件配置。")
            return
        
        has_reply, reply_content = self._get_reply_content(event)
        
        if not has_reply or not reply_content:
            yield event.plain_result("请引用算卦结果后再发送「ai解卦」")
            return
        
        # 使用正则提取卦名
        hexagram_name = self._extract_hexagram_name(reply_content)
        
        if not hexagram_name:
            yield event.plain_result("无法识别引用的卦象，请引用正确的算卦结果")
            return
        
        hexagram_data = self._hexagrams[hexagram_name]
        
        await event.send(event.plain_result(f"正在为您AI解卦【{hexagram_name}卦】，请稍候..."))
        
        ai_result = await self._get_ai_interpretation(event, hexagram_name, hexagram_data)
        
        hexagram_display = get_hexagram_display(hexagram_data)
        result = f"【{hexagram_name}卦 · AI解卦】\n"
        result += f"{hexagram_display}\n"
        result += f"卦性：{hexagram_data.get('性质', '未知')}\n"
        result += f"\n{ai_result}"
        
        yield event.plain_result(result)
    
    @filter.command("卦象")
    async def hexagram_info(self, event: AstrMessageEvent, name: str = ""):
        """卦象查询
        
        Args:
            name: 卦名
        """
        if not self._hexagrams:
            yield event.plain_result("卦象数据加载失败，请联系管理员检查插件配置。")
            return
        
        hexagram_name = name.strip() if name else ""
        
        if not hexagram_name or hexagram_name not in self._hexagrams:
            available = "、".join(list(self._hexagrams.keys())[:8]) + "..."
            yield event.plain_result(f"未找到「{hexagram_name}」卦\n可查询的卦象包括：{available}")
            return
        
        hexagram_data = self._hexagrams[hexagram_name]
        hexagram_display = get_hexagram_display(hexagram_data)
        
        result = f"【{hexagram_name}卦】\n"
        result += f"{hexagram_display}\n\n"
        result += f"性质：{hexagram_data.get('性质', '未知')}\n"
        result += f"含义：{hexagram_data.get('含义', '未知')}\n\n"
        result += "爻辞：\n"
        for yao in hexagram_data.get('爻辞', []):
            result += f"  {yao}\n"
        
        yield event.plain_result(result)
    
    @filter.command("六十四卦")
    async def list_hexagrams(self, event: AstrMessageEvent):
        """六十四卦列表"""
        if not self._hexagrams:
            yield event.plain_result("卦象数据加载失败，请联系管理员检查插件配置。")
            return
        
        result = "【六十四卦列表】\n\n"
        
        hexagrams = list(self._hexagrams.keys())
        for i in range(0, len(hexagrams), 8):
            batch = hexagrams[i:i+8]
            result += "、".join(batch) + "\n"
        
        result += "\n使用「卦象+卦名」查询详细信息"
        
        yield event.plain_result(result)
    
    async def terminate(self):
        """插件销毁"""
        logger.info("算卦插件已卸载")
