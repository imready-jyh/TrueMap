# TrueMap 后端API说明（中文）

## 1. 启动方法

```bash
cd backend
pip install -r requirements.txt
uvicorn api:app --host 0.0.0.0 --port 8000 --reload
```

## 2. API接口

### 2.1 文本检测
- 路径：`/api/text`
- 方法：POST
- 请求体：
```json
{
  "text": "待检测文本内容"
}
```
- 返回：
```json
{
  "label": "正确",
  "reason": "详细理由",
  "confidence": "85%",
  "raw": "AI原始输出"
}
```

### 2.2 单文件检测
- 路径：`/api/file`
- 方法：POST
- form-data字段：`file`（上传txt文件）
- 返回：同上，增加`filename`字段

### 2.3 多文件检测
- 路径：`/api/files`
- 方法：POST
- form-data字段：`files`（可上传多个txt文件）
- 返回：
```json
{
  "results": [
    {
      "filename": "a.txt",
      "label": "正确",
      "reason": "...",
      "confidence": "90%",
      "raw": "..."
    },
    {
      "filename": "b.txt",
      "label": "错误",
      "reason": "...",
      "confidence": "60%",
      "raw": "..."
    }
  ]
}
```

## 3. 远程AI API对接
- 默认调用 http://localhost:5400/api/predict
- 可通过环境变量`AI_API_URL`自定义
- 请确保AI服务已启动并可访问

## 4. 跨域说明
- 已允许所有来源跨域，方便前端本地开发和调试

## 5. 目录结构
```
backend/
  |-- api.py           # 主API服务
  |-- requirements.txt # 依赖
  |-- README.md        # 说明文档
``` 
