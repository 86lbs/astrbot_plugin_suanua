# AstrBot 算卦插件 🔮

一个基于易经六十四卦的 AstrBot 聊天机器人插件，支持 AI 智能解卦。

## 免责声明

插件开发全程由智谱清言agent完成

## 功能特点

- 🎲 **随机起卦**：模拟传统蓍草占卜法，生成随机卦象
- 🤖 **AI 解卦**：调用大语言模型进行智能解卦分析
- 📖 **卦象查询**：支持查询六十四卦详细信息
- 💬 **简单易用**：只需发送"算一卦"即可触发

## 安装方法

### 方法一：通过 AstrBot 插件市场安装

1. 打开 AstrBot 管理面板
2. 进入插件市场
3. 搜索"算卦"或"suanua"
4. 点击安装

### 方法二：通过 URL 安装

1. 打开 AstrBot 管理面板
2. 进入插件管理
3. 点击"安装插件"
4. 输入仓库地址：`https://github.com/86lbs/astrbot_plugin_suanua`
5. 点击安装

### 方法三：手动安装

1. 下载本仓库
```bash
git clone https://github.com/86lbs/astrbot_plugin_suanua.git
```

2. 将 `main.py` 和 `metadata.yaml` 复制到 AstrBot 的 `data/plugins/astrbot_plugin_suanua/` 目录
```bash
mkdir -p /path/to/astrbot/data/plugins/astrbot_plugin_suanua
cp main.py metadata.yaml /path/to/astrbot/data/plugins/astrbot_plugin_suanua/
```

3. 重启 AstrBot

## 使用方法

### 基本命令

| 命令 | 说明 |
|------|------|
| `算一卦` | 随机起卦并获取 AI 解卦结果 |
| `算一卦 我今天运势如何？` | 带问题起卦 |
| `卦象乾` | 查询乾卦的详细信息 |
| `六十四卦` | 列出所有六十四卦名称 |

### 使用示例

```
用户: 算一卦
机器人: 
╔══════════════════════════════════════╗
║           🔮 易经算卦 🔮             ║
╠══════════════════════════════════════╣
║  卦名：乾卦 ☰                       ║
║  性质：纯阳                         ║
╚══════════════════════════════════════╝

[AI 解卦内容...]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 提示：卦象仅供参考，命运掌握在自己手中！
```

## 配置说明

插件会自动使用 AstrBot 配置的 AI 模型进行解卦。如果 AI 不可用，将使用本地预设的解卦模板。

## 六十四卦列表

本插件包含完整的六十四卦数据，每卦包含：
- 卦名与卦象符号
- 卦的性质
- 基本含义
- 六爻爻辞

## 技术实现

- **起卦算法**：模拟传统蓍草占卜法，通过随机数生成六爻
- **AI 解卦**：调用 AstrBot 的 LLM 接口，根据卦象生成个性化解读
- **本地降级**：当 AI 不可用时，使用预设模板进行解卦

## 注意事项

1. 本插件仅供娱乐参考，请勿迷信
2. AI 解卦结果由大语言模型生成，仅供参考
3. 如遇问题，请检查 AstrBot 日志

## 许可证

MIT License

## 贡献

欢迎提交 Issue 和 Pull Request！

## 仓库地址

🔗 https://github.com/86lbs/astrbot_plugin_suanua
