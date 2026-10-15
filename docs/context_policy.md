| Field Pattern        | Priority                           | Reason  |
| -------------------- | ---------------------------------- | ------- |
| learning.current_*   | conversation > continuity > memory | 当前状态可变化 |
| learning.completed_* | memory > conversation              | 历史事实    |
| user.preference.*    | conversation > memory              | 明确修改优先  |


