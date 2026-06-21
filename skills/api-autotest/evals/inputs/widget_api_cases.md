# Widget 管理 接口测试用例（节选）

接口权威源：openapi_snippet.json（/api/widget）。后端响应壳：`{code, msg, data, success}`。

| 用例编号 | 用例名称 | 用例类型 | 是否API自动化 | 预期结果 |
|---|---|---|---|---|
| TC-API-W-001 | 管理员新增 widget，输入合法名称，保存成功 | 基本流 | 是 | 1. 创建成功 success=true 2. 列表可按名查到 |
| TC-API-W-002 | 管理员新增 widget，名称为空，点击保存 | 异常流 | 是 | 1. 拒绝保存 success=false 2. 不新增任何记录 |
| TC-API-W-003 | 无 widget:list 权限点的用户调用列表接口 | 异常流 | 是 | 1. 后端拒绝 success=false（403 无此接口权限） |
| TC-API-W-004 | 管理员新增 widget，描述字段 1000 字符（合法上界），保存成功 | 基本流 | 是 | 1. 创建成功 2. 描述完整持久化无截断 |
| TC-API-W-005 | 列表筛选框输入超长串（5000 字符） | 异常流 | 否 | 1. 不返回 5xx |
