# oclaw trace taxonomy

本文档说明 oclaw 运行链路的 trace 字段与阶段含义，便于排障与审计。

主要关注：

- pipeline 阶段划分
- 任务与运行 ID 关联
- 失败码定位与重试判断

如需查看完整细粒度字段定义，请在仓库中搜索：

- `pipeline`
- `openclaw_task_id`
- `openclaw_worker_id`
