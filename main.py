"""
AstrBot 算卦插件
用户发送 "算一卦" 触发本插件，生成卦象并输出本地解卦
引用输出内容发送 "ai解卦" 进行AI解卦
支持作为函数工具供 AI 调用
支持变卦功能
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


# 八卦线条映射（顺序：初爻、二爻、三爻）
TRIGRAM_LINES: dict[str, list[str]] = {
    "☰": ["━━━", "━━━", "━━━"],  # 乾 - 三阳爻
    "☷": ["━ ━", "━ ━", "━ ━"],  # 坤 - 三阴爻
    "☳": ["━━━", "━ ━", "━ ━"],  # 震 - 初阳（下阳上阴）
    "☶": ["━ ━", "━ ━", "━━━"],  # 艮 - 上阳（上阳下阴）
    "☲": ["━━━", "━ ━", "━━━"],  # 离 - 中阴（上阳中阴下阳）
    "☵": ["━ ━", "━━━", "━ ━"],  # 坎 - 中阳（上阴中阳下阴）
    "☱": ["━━━", "━━━", "━ ━"],  # 兑 - 上阴（上阴下阳）
    "☴": ["━ ━", "━━━", "━━━"],  # 巽 - 初阴（上阳下阴）
}

# 八卦名称映射
TRIGRAM_NAMES: dict[str, str] = {
    "☰": "乾", "☷": "坤", "☳": "震", "☶": "艮",
    "☲": "离", "☵": "坎", "☱": "兑", "☴": "巽",
}

# 线条到八卦符号的反向映射
LINES_TO_TRIGRAM: dict[str, str] = {
    "━━━━━━━━━": "☰",
    "━ ━━ ━━ ━": "☷",
    "━━━━ ━━ ━": "☳",
    "━ ━━ ━━━━": "☶",
    "━━━━ ━━━━": "☲",
    "━ ━━━━━ ━": "☵",
    "━━━━━━━ ━": "☱",
    "━ ━━━━━━━": "☴",
}

# 爻的名称
YAO_NAMES = ["初爻", "二爻", "三爻", "四爻", "五爻", "上爻"]

# 插件默认配置
DEFAULT_CONFIG = {
    "enable_change": True,  # 默认开启变卦
}


def get_hexagram_display(hexagram_data: dict, compact: bool = False) -> str:
    """将卦象转换为显示格式
    
    Args:
        hexagram_data: 卦象数据
        compact: 是否使用紧凑格式（单字符号）
    
    Returns:
        卦象显示字符串
    """
    gua_xiang = hexagram_data.get("卦象", "")
    
    if not gua_xiang:
        return "卦象缺失"
    
    if compact:
        # 紧凑格式：使用单字符号
        if len(gua_xiang) == 1:
            return f"{gua_xiang}（{TRIGRAM_NAMES.get(gua_xiang, '?')}）"
        elif len(gua_xiang) == 2:
            upper_name = TRIGRAM_NAMES.get(gua_xiang[0], "?")
            lower_name = TRIGRAM_NAMES.get(gua_xiang[1], "?")
            return f"{gua_xiang}（{upper_name}{lower_name}）"
        return gua_xiang
    else:
        # 完整格式：6排显示
        if len(gua_xiang) == 1 and gua_xiang in TRIGRAM_LINES:
            lines = TRIGRAM_LINES[gua_xiang]
            all_lines = lines + lines
            return "\n".join(reversed(all_lines))
        
        if len(gua_xiang) == 2:
            upper_lines = TRIGRAM_LINES.get(gua_xiang[0], ["?", "?", "?"])
            lower_lines = TRIGRAM_LINES.get(gua_xiang[1], ["?", "?", "?"])
            all_lines = lower_lines + upper_lines
            return "\n".join(reversed(all_lines))
        
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


def get_hexagram_lines(hexagram_data: dict) -> list[str]:
    """获取卦象的六爻线条列表
    
    返回顺序：索引0=初爻，索引5=上爻
    """
    gua_xiang = hexagram_data.get("卦象", "")
    
    if len(gua_xiang) == 1 and gua_xiang in TRIGRAM_LINES:
        lines = TRIGRAM_LINES[gua_xiang]
        return lines + lines
    
    if len(gua_xiang) == 2:
        upper_lines = TRIGRAM_LINES.get(gua_xiang[0], ["?", "?", "?"])
        lower_lines = TRIGRAM_LINES.get(gua_xiang[1], ["?", "?", "?"])
        return lower_lines + upper_lines
    
    return ["?"] * 6


def flip_line(line: str) -> str:
    """翻转爻线（阳变阴，阴变阳）"""
    if "━━━" in line and "━ ━" not in line:
        return "━ ━"
    elif "━ ━" in line:
        return "━━━"
    return line


def lines_to_trigram_symbol(lines: list[str]) -> str:
    """将三爻线条转换为八卦符号"""
    joined = "".join(lines)
    return LINES_TO_TRIGRAM.get(joined, "?")


def find_hexagram_by_lines(lines: list[str], hexagrams: dict) -> Optional[tuple[str, dict]]:
    """根据六爻线条查找对应的卦"""
    if len(lines) != 6:
        return None
    
    lower_lines = lines[0:3]
    upper_lines = lines[3:6]
    
    lower_symbol = lines_to_trigram_symbol(lower_lines)
    upper_symbol = lines_to_trigram_symbol(upper_lines)
    
    for name, data in hexagrams.items():
        gua_xiang = data.get("卦象", "")
        if len(gua_xiang) == 1:
            if gua_xiang == upper_symbol == lower_symbol:
                return name, data
        elif len(gua_xiang) == 2:
            if gua_xiang[0] == upper_symbol and gua_xiang[1] == lower_symbol:
                return name, data
    
    return None


class SuanguaPlugin(star.Star):
    """算卦插件"""
    
    def __init__(self, context: Context):
        super().__init__(context)
        self._hexagrams: dict[str, dict] = {}
        self._loaded = False
        self._config: dict = DEFAULT_CONFIG.copy()
    
    def _load_config(self):
        """加载插件配置"""
        try:
            cfg = self.context.get_config()
            if cfg:
                self._config["enable_change"] = cfg.get("enable_change", True)
                logger.info(f"插件配置: 变卦功能={'开启' if self._config['enable_change'] else '关闭'}")
        except Exception as e:
            logger.warning(f"加载插件配置失败，使用默认配置: {e}")
    
    def _load_hexagrams(self) -> bool:
        """加载六十四卦数据"""
        if self._loaded:
            return bool(self._hexagrams)
        
        data_file = Path(__file__).parent / "hexagrams.json"
        try:
            with open(data_file, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
            
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
        self._load_config()
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
    
    def _generate_changing_yaos(self) -> list[int]:
        """生成变爻位置"""
        num_changes = random.choices([0, 1, 2, 3, 4, 5, 6], weights=[10, 30, 25, 20, 10, 4, 1])[0]
        if num_changes == 0:
            return []
        return random.sample(list(range(6)), num_changes)
    
    def _apply_changes(self, original_lines: list[str], changing_positions: list[int]) -> list[str]:
        """应用变爻"""
        new_lines = original_lines.copy()
        for pos in changing_positions:
            new_lines[pos] = flip_line(original_lines[pos])
        return new_lines
    
    def _build_divination_result(
        self, 
        hexagram_name: str, 
        hexagram_data: dict, 
        question: str = "",
        include_change: bool = False,
        compact: bool = False
    ) -> str:
        """构建算卦结果
        
        Args:
            hexagram_name: 卦名
            hexagram_data: 卦象数据
            question: 求卦问题
            include_change: 是否包含变卦
            compact: 是否使用紧凑格式（LLM调用时使用）
        """
        lines = []
        
        # 本卦信息
        hexagram_display = get_hexagram_display(hexagram_data, compact=compact)
        lines.append(f"【{hexagram_name}卦】")
        lines.append(hexagram_display)
        lines.append(f"卦性：{hexagram_data.get('性质', '未知')}")
        lines.append(f"含义：{hexagram_data.get('含义', '未知')}")
        
        # 变卦处理
        changed_hexagram_name = None
        changed_hexagram_data = None
        changing_yaos = []
        
        if include_change:
            original_lines = get_hexagram_lines(hexagram_data)
            changing_yaos = self._generate_changing_yaos()
            
            if changing_yaos:
                new_lines = self._apply_changes(original_lines, changing_yaos)
                result = find_hexagram_by_lines(new_lines, self._hexagrams)
                if result:
                    changed_hexagram_name, changed_hexagram_data = result
        
        # 爻辞
        yao_ci_list = hexagram_data.get('爻辞', [])
        if yao_ci_list:
            if changing_yaos:
                yao_index = changing_yaos[0]
                if yao_index < len(yao_ci_list):
                    yao_ci = yao_ci_list[yao_index]
                    lines.append(f"爻辞（{YAO_NAMES[yao_index]}动）：{yao_ci}")
                else:
                    lines.append(f"爻辞：{random.choice(yao_ci_list)}")
            else:
                lines.append(f"爻辞：{random.choice(yao_ci_list)}")
        
        # 变卦信息
        if changed_hexagram_name and changed_hexagram_data:
            lines.append("")
            if compact:
                lines.append("─── 变卦 ───")
            else:
                lines.append("━━━━━━━━━━━━━━━━━")
            changed_display = get_hexagram_display(changed_hexagram_data, compact=compact)
            lines.append(f"【变卦：{changed_hexagram_name}卦】")
            lines.append(changed_display)
            lines.append(f"卦性：{changed_hexagram_data.get('性质', '未知')}")
            lines.append(f"含义：{changed_hexagram_data.get('含义', '未知')}")
            
            yao_names = [YAO_NAMES[pos] for pos in changing_yaos]
            lines.append(f"变爻：{'、'.join(yao_names)}")
        
        # 运势指引
        interpretations = [
            "当前运势稳中有进，宜保持耐心。",
            "事业方面：脚踏实地，稳扎稳打。",
            "感情方面：真诚待人，缘分自来。",
            "财运方面：量入为出，积少成多。",
            "健康方面：劳逸结合，注意休息。"
        ]
        
        lines.append("")
        lines.append("运势指引：")
        for interp in random.sample(interpretations, min(3, len(interpretations))):
            lines.append(f"  • {interp}")
        
        result = "\n".join(lines)
        
        # 确保换行符正确显示
        result = result.replace("\n", "\r\n")
        
        if question:
            result = f"求卦问题：{question}\r\n\r\n{result}"
        
        return result
    
    def _extract_hexagram_name(self, content: str) -> Optional[str]:
        """从内容中提取卦名"""
        pattern = r"^【(.+?)卦】"
        match = re.search(pattern, content, re.MULTILINE)
        if match:
            name = match.group(1)
            if name in self._hexagrams:
                return name
        return None
    
    async def _get_ai_interpretation(
        self, 
        event: AstrMessageEvent, 
        hexagram_name: str, 
        hexagram_data: dict,
        changed_name: str = None,
        changed_data: dict = None
    ) -> str:
        """调用 AI 进行解卦"""
        try:
            provider = self.context.get_using_provider(umo=event.unified_msg_origin)
        except Exception as e:
            logger.error(f"获取 provider 失败: {e}")
            return "未检测到可用的大语言模型提供商。"
        
        if not provider:
            return "未检测到可用的大语言模型提供商。"
        
        gua_xiang = hexagram_data.get('卦象', '未知')
        gua_display = get_hexagram_display(hexagram_data, compact=True)
        
        user_prompt = f"""请根据以下卦象为求卦者解卦。

本卦：{hexagram_name}卦
卦象：{gua_display}
性质：{hexagram_data.get('性质', '未知')}
基本含义：{hexagram_data.get('含义', '未知')}"""

        if changed_name and changed_data:
            changed_display = get_hexagram_display(changed_data, compact=True)
            user_prompt += f"""

变卦：{changed_name}卦
卦象：{changed_display}
性质：{changed_data.get('性质', '未知')}
基本含义：{changed_data.get('含义', '未知')}

请结合本卦和变卦进行综合解卦，说明事物的发展变化。"""

        user_prompt += """

请提供详细的解卦分析，用通俗易懂的语言，给出积极正面的指引。"""

        system_prompt = "你是一位精通易经的算命大师，擅长用通俗易懂的语言为人们解卦指引。"
        
        try:
            llm_resp = await provider.text_chat(
                prompt=user_prompt,
                context=[],
                system_prompt=system_prompt,
                image_urls=[],
            )
            
            completion_text = getattr(llm_resp, "completion_text", None)
            if completion_text and isinstance(completion_text, str) and completion_text.strip():
                return completion_text.strip()
            
            text = getattr(llm_resp, "text", None)
            if text and isinstance(text, str) and text.strip():
                return text.strip()
            
            logger.warning(f"AI 返回内容为空")
            return "AI未返回有效内容，请稍后重试。"
            
        except Exception as e:
            logger.error(f"AI 解卦失败: {e}")
            return "AI解卦出错，请稍后重试。"
    
    @llm_tool(name="divine_hexagram")
    async def divine_hexagram(self, event: AstrMessageEvent, question: str = "") -> str:
        """易经算卦工具。当用户想要算卦、占卜、预测运势、询问未来时使用此工具。
        
        Args:
            question(string): 用户想要询问的问题或想要了解的方面（可选）
        """
        has_reply, reply_content = self._get_reply_content(event)
        if has_reply and reply_content:
            question = reply_content
        
        if not self._hexagrams:
            if not self._load_hexagrams():
                return "卦象数据加载失败，请联系管理员检查插件配置。"
        
        hexagram_name = random.choice(list(self._hexagrams.keys()))
        hexagram_data = self._hexagrams[hexagram_name]
        
        # LLM调用：使用紧凑格式，根据配置决定是否变卦
        return self._build_divination_result(
            hexagram_name, 
            hexagram_data, 
            question, 
            include_change=self._config["enable_change"],
            compact=True
        )
    
    @filter.command("算一卦")
    async def divine(self, event: AstrMessageEvent):
        """算一卦 - 生成卦象并输出本地解卦"""
        logger.info("收到算卦请求")
        
        if not self._hexagrams:
            if not self._load_hexagrams():
                yield event.plain_result("卦象数据加载失败，请联系管理员检查插件配置。")
                return
        
        hexagram_name = random.choice(list(self._hexagrams.keys()))
        hexagram_data = self._hexagrams[hexagram_name]
        
        # 插件调用：使用完整格式，根据配置决定是否变卦
        result = self._build_divination_result(
            hexagram_name, 
            hexagram_data, 
            include_change=self._config["enable_change"],
            compact=False
        )
        result += "\r\n\r\n引用此消息发送「ai解卦」可获取AI详细解读"
        
        yield event.plain_result(result)
    
    @filter.command("变卦")
    async def divine_with_change(self, event: AstrMessageEvent):
        """变卦 - 强制生成带变卦的算卦结果"""
        logger.info("收到变卦请求")
        
        if not self._hexagrams:
            if not self._load_hexagrams():
                yield event.plain_result("卦象数据加载失败，请联系管理员检查插件配置。")
                return
        
        hexagram_name = random.choice(list(self._hexagrams.keys()))
        hexagram_data = self._hexagrams[hexagram_name]
        
        # 强制开启变卦
        result = self._build_divination_result(
            hexagram_name, 
            hexagram_data, 
            include_change=True,
            compact=False
        )
        result += "\r\n\r\n引用此消息发送「ai解卦」可获取AI详细解读"
        
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
        
        hexagram_name = self._extract_hexagram_name(reply_content)
        
        if not hexagram_name:
            yield event.plain_result("无法识别引用的卦象，请引用正确的算卦结果")
            return
        
        hexagram_data = self._hexagrams[hexagram_name]
        
        changed_name = None
        changed_data = None
        change_match = re.search(r"【变卦：(.+?)卦】", reply_content)
        if change_match:
            changed_name = change_match.group(1)
            if changed_name in self._hexagrams:
                changed_data = self._hexagrams[changed_name]
        
        await event.send(event.plain_result(f"正在为您AI解卦【{hexagram_name}卦】，请稍候..."))
        
        ai_result = await self._get_ai_interpretation(
            event, hexagram_name, hexagram_data, changed_name, changed_data
        )
        
        hexagram_display = get_hexagram_display(hexagram_data, compact=False)
        result = f"【{hexagram_name}卦 · AI解卦】\r\n"
        result += f"{hexagram_display}\r\n"
        result += f"卦性：{hexagram_data.get('性质', '未知')}\r\n"
        
        if changed_name and changed_data:
            result += f"\r\n变卦：{changed_name}卦\r\n"
        
        result += f"\r\n{ai_result}"
        
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
        hexagram_display = get_hexagram_display(hexagram_data, compact=False)
        
        result = f"【{hexagram_name}卦】\r\n"
        result += f"{hexagram_display}\r\n\r\n"
        result += f"性质：{hexagram_data.get('性质', '未知')}\r\n"
        result += f"含义：{hexagram_data.get('含义', '未知')}\r\n\r\n"
        result += "爻辞：\r\n"
        for yao in hexagram_data.get('爻辞', []):
            result += f"  {yao}\r\n"
        
        yield event.plain_result(result)
    
    @filter.command("六十四卦")
    async def list_hexagrams(self, event: AstrMessageEvent):
        """六十四卦列表"""
        if not self._hexagrams:
            yield event.plain_result("卦象数据加载失败，请联系管理员检查插件配置。")
            return
        
        result = "【六十四卦列表】\r\n\r\n"
        
        hexagrams = list(self._hexagrams.keys())
        for i in range(0, len(hexagrams), 8):
            batch = hexagrams[i:i+8]
            result += "、".join(batch) + "\r\n"
        
        result += "\r\n使用「卦象+卦名」查询详细信息"
        
        yield event.plain_result(result)
    
    async def terminate(self):
        """插件销毁"""
        logger.info("算卦插件已卸载")
