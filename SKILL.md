| name | tencentdb-memory |
| description | 指导 Kimi Code 使用 TencentDB Agent Memory 长期记忆系统（L0-L3）进行上下文召回、记忆捕获和搜索。 |
| version | 1.0.0 |

# 目的

当用户需要跨会话保持上下文、回忆过去约定、或主动管理长期记忆时，调用 TencentDB Agent Memory MCP 工具。该记忆系统比内置的简单记忆更强，支持 L0 原始对话、L1 原子记忆、L2 场景块、L3 用户画像的分层存储。

# 触发条件

在以下情况触发：
- 用户提到「记得」「之前说过」「上次」「我的偏好」「像以前一样」等需要上下文的表达
- 开始一个新的任务，且可能与历史项目/偏好相关
- 用户明确说「记住这个」「存到记忆里」「搜一下记忆」
- 会话即将结束或切换主题时

# 可用工具

工具名前缀为 `mcp__tencentdb_memory__`：

1. `tencentdb_memory_recall` — 会话开始时调用，把相关长期记忆注入上下文
2. `tencentdb_memory_capture` — 完成一轮有意义的对话后调用，存入记忆流水线
3. `tencentdb_memory_search` — 搜索结构化记忆（L1-L3）
4. `tencentdb_conversation_search` — 搜索原始对话记录（L0）
5. `tencentdb_session_end` — 会话结束时调用，刷新后台提取任务

# 工作流

## 会话开始时

1. 用 `tencentdb_memory_recall(query=用户第一句话或当前任务, session_key=稳定会话ID)` 拉取相关记忆。
2. 把返回的 context 融入你的理解和回复中。

## 每轮有意义的对话后

1. 用 `tencentdb_memory_capture(user_content=用户消息, assistant_content=你的回复, session_key=同上)` 捕获这一轮。
2. 该调用是后台触发，失败不应阻塞回复。

## 用户要求搜索记忆时

- 如果用户问「我以前怎么说的」「我之前配置了什么」→ 用 `tencentdb_conversation_search`
- 如果用户问「我的偏好是什么」「总结我的习惯」→ 用 `tencentdb_memory_search`

## 会话结束

- 如果明显是收尾（如用户说「先这样」「结束」「拜拜」），调用 `tencentdb_session_end(session_key=同上)`。

# session_key 规则

- 尽量使用稳定、可读的会话标识，例如项目名称 + 日期，或用户 ID。
- 示例：`patrick-main-20260711`、`kimi-code-workspace`。
- 同一主题的多轮对话应复用同一个 session_key。

# 注意事项

- 不要每次回复都调用 capture，只在内容有信息量时调用（避免噪音）。
- recall 返回的记忆要自然融入回答，不要直接整段复制给用户。
- 如果 Gateway 未启动，调用会报错，此时告诉用户「记忆服务未启动，请运行 python start-gateway.py」。
