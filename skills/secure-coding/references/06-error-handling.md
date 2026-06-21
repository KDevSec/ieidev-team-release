# 3.6 错误处理

> 概述：错误处理不当是这类问题最常见的引入方式。

## 规则
- 应合理利用 try/except/finally，避免出错信息输出到前端。
- 禁止忽略异常，否则会导致程序无法发现意外状况和情况。
- 应记录抛出的异常，以便于稍后查询及预知程序对运行造成的影响。
- 禁止异常抛出敏感信息（堆栈、SQL、密钥、内部路径等）。

## 反例
```python
try:
    do_thing()
except Exception:
    pass   # 静默吞异常

try:
    pay(user)
except Exception as e:
    return jsonify({"error": str(e)})   # 把堆栈/内部信息返回给前端
```

## 正例
```python
import logging

try:
    do_thing()
except SpecificError:
    logging.exception("do_thing failed")
    return jsonify({"error": "internal error"}), 500   # 通用提示
finally:
    cleanup()
```

## 适用场景
所有 try/except 代码块；构造 HTTP 错误响应；异常上抛到框架层时。
