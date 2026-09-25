# 数据协议

## 文档 IR

`generate_docx.py` 接受以下 JSON：

```json
{"title":"季度报告","blocks":[{"type":"heading","level":1,"text":"摘要"},{"type":"paragraph","text":"已确认的内容。"},{"type":"table","headers":["姓名","得分"],"rows":[["Ava","95"]]}]}
```

支持的块类型为 `heading`、`paragraph` 和 `table`。样式与布局由 Python 控制，而不是模型。

## 模板数据

`fill_template.py` 接受标量值 JSON 对象，并替换 `{{key}}`。它有意不支持循环和条件块；若确有需要，必须使用经过测试、格式语义明确的渲染器。

## 提取结果

`inspect_docx.py` 输出 `metadata`、`paragraphs` 和 `tables`。为便于分析，段落文本会扁平化；若需保留 run 级格式，必须保留原始 OOXML。
