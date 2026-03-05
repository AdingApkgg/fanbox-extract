# Web UI 测试体系

## 测试分层

- 单元测试
  - 文件：`tests/unit/test_web_ui_core.py`
  - 覆盖：鉴权判定、路径安全、Markdown 链接改写、尺寸格式化
- 集成测试
  - 文件：`tests/integration/test_file_preview_flow.py`
  - 覆盖：文件树节点构建、图标映射、越界链接保护
- 端到端测试
  - 文件：`tests/e2e/test_web_ui_http_smoke.py`
  - 覆盖：鉴权重定向、已登录访问、首页响应时间阈值

## 执行方式

```bash
uv run python -m unittest discover -s tests -p "test_*.py"
```

## 兼容性测试矩阵

- Chrome（Chromium 内核）
- Firefox
- Safari（WebKit）
- Edge（Chromium 内核）

建议在每次 UI 版本发布前完成：

- 首页加载与登录流程
- 下载页表单交互与进度更新
- 管理页文件树展开与预览
- Markdown 图片链接渲染与下载按钮

## 性能验收

- 首页在本地环境中响应时间 < 2 秒
- 大目录情况下文件树刷新可完成且无错误提示
- 降低动画偏好时不应出现强制动效
