# Phase 8：错误处理与可观测性

统一记录：

- request_id
- task_id
- agent_id
- delegation_id
- parent_agent_id
- start_time
- elapsed_ms
- status
- error_type
- retry_count
- checkpoint_id

日志必须能够回答：

```text
Supervisor 决定了什么？
→ 调用了哪些 Agent？
→ 哪些并行？
→ 哪些成功/失败/超时？
→ 是否 Replan？
→ Checkpoint 在哪里？
→ 最终用了哪些结果？
```
