# 数据协议

## 文档 IR

`generate_pdf.py` 接受 `title`、可选的 `author`，以及 `blocks`。目前支持 `heading` 与 `paragraph` 两类块。

```json
{"title":"项目摘要","author":"团队","blocks":[{"type":"heading","text":"结论"},{"type":"paragraph","text":"这是经过确认的内容。"}]}
```

文本内容与布局结构必须分离：模型可提供块中的文本，Python 控制页边距、字体、换行与分页。需要表格、图片、页眉页脚或多栏排版时，应扩展 schema 和生成器并增加渲染测试。

## 检查输出

`inspect_pdf.py` 输出页数、文档元数据和按页文本。文本用于内容分析和占位符检查，不能代替 PNG 渲染后的视觉验证。
