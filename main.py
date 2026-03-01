"""
AstrBot 算卦插件
仅支持作为函数工具供 AI 调用
"""

import json
import random
from pathlib import Path

from astrbot.api import llm_tool, logger, star
from astrbot.api.event import AstrMessageEvent
from astrbot.api.message_components import Reply
from astrbot.api.star import Context


# 八卦线条映射
TRIGRAM_LINES = {
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
    
    if len(gua_xiang) == 1 and gua_xiang in TRIGRAM_LINES:
        lines = TRIGRAM_LINES[gua_xiang]
        return "\n".join(lines + lines)
    
    if len(gua_xiang) == 2:
        upper_lines = TRIGRAM_LINES.get(gua_xiang[0], ["?", "?", "?"])
        lower_lines = TRIGRAM_LINES.get(gua_xiang[1], ["?", "?", "?"])
        return "\n".join(upper_lines + lower_lines)
    
    return gua_xiang


def load_hexagrams() -> dict:
    """加载六十四卦数据"""
    data_file = Path(__file__).parent / "hexagrams.json"
    try:
        with open(data_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.error(f"加载卦象数据失败: {e}")
        return {}


# 加载六十四卦数据
SIXTY_FOUR_HEXAGRAMS = load_hexagrams()


class SuanguaPlugin(star.Star):
    """算卦插件 - 仅支持LLM调用"""
    
    def __init__(self, context: Context):
        super().__init__(context)
    
    async def initialize(self):
        """插件初始化"""
        if SIXTY_FOUR_HEXAGRAMS:
            logger.info(f"算卦插件已加载，共 {len(SIXTY_FOUR_HEXAGRAMS)} 个卦象")
        else:
            logger.warning("算卦插件加载失败，请检查 hexagrams.json 文件")
    
    def _get_reply_content(self, event: AstrMessageEvent) -> tuple:
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
    
    @llm_tool(name="divine_hexagram")
    async def divine_hexagram(self, event: AstrMessageEvent, question: str = "") -> str:
        """易经算卦工具。当用户想要算卦、占卜、预测运势、询问未来时使用此工具。
        调用此工具后，请在回复中完整展示卦象结果，然后进行解卦分析。
        
        Args:
            question(string): 用户想要询问的问题或想要了解的方面（可选）
        """
        # 检查是否有引用消息
        has_reply, reply_content = self._get_reply_content(event)
        if has_reply and reply_content:
            question = reply_content
        
        if not SIXTY_FOUR_HEXAGRAMS:
            return "卦象数据加载失败，请检查插件配置。"
        
        # 生成卦象
        hexagram_name = random.choice(list(SIXTY_FOUR_HEXAGRAMS.keys()))
        hexagram_data = SIXTY_FOUR_HEXAGRAMS[hexagram_name]
        hexagram_display = get_hexagram_display(hexagram_data)
        
        # 生成本地解卦
        lines = []
        lines.append(f"【{hexagram_name}卦】")
        lines.append(hexagram_display)
        lines.append(f"卦性：{hexagram_data['性质']}")
        lines.append(f"含义：{hexagram_data['含义']}")
        
        yao_ci = random.choice(hexagram_data['爻辞'])
        lines.append(f"爻辞：{yao_ci}")
        
        interpretations = [
            "当前运势稳中有进，宜保持耐心。",
            "事业方面：脚踏实地，稳扎稳打。",
            "感情方面：真诚待人，缘分自来。",
            "财运方面：量入为出，积少成多。",
            "健康方面：劳逸结合，注意休息。"
        ]
        
        lines.append("运势指引：")
        for interp in random.sample(interpretations, 3):
            lines.append(f"  • {interp}")
        
        result = "\n".join(lines)
        
        if question:
            result = f"求卦问题：{question}\n\n{result}"
        
        # 添加提示，让AI在回复中展示结果
        result += "\n\n---\n请在回复中完整展示以上卦象结果，然后进行详细的解卦分析。"
        
        return result
    
    async def terminate(self):
        """插件销毁"""
        logger.info("算卦插件已卸载")
