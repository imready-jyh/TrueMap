# -*- coding: utf-8 -*-
"""
后端API服务，支持文本检测、单文件检测、多文件检测，返回真假概率等。
"""
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import requests
import os
import logging
import re
import json
import chardet
from docx import Document
import io
import base64

app = FastAPI(
    title="TrueMap后端API",
    description="支持文本、单文件、多文件检测，返回真假概率。",
    version="1.0.0"
)

# 允许跨域，便于前端本地开发
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境请指定域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TextRequest(BaseModel):
    text: str

class PredictResult(BaseModel):
    label: str
    reason: str
    confidence: str
    info_extract: Optional[str] = None  # 改为字符串
    highlighted_text: Optional[str] = None
    raw: str
    filename: Optional[str] = None  # 多文件时用

HISTORY_FILE = 'history_records.json'

def save_history(record):
    try:
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
        else:
            data = []
        data.append(record)
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f'保存历史记录失败: {e}')

def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def clear_history():
    if os.path.exists(HISTORY_FILE):
        os.remove(HISTORY_FILE)

def call_ai_api(text: str):
    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        return "错误", "API Key未配置", "0%", {}, "", "后台配置错误"

    api_base = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    model = "qwen-plus"

    prompt = f"""
你是一名资深的新闻真实性鉴定专家。请你对下面这条新闻内容进行全面、细致、专业的审查，结合事实、常识、逻辑推理和权威信息，判断其内容是否真实、正确。请详细说明你的分析过程和理由，避免主观臆断，尽量引用权威信息或常识进行佐证。

请严格按照如下JSON格式输出，不要输出多余内容：
{{
  "label": "正确/错误/部分正确/部分错误",
  "reason": "详细理由",
  "confidence": "0-100之间的数字并带百分号，如85%。置信度绝不能为NaN、未知、无、空、null等，否则请直接输出50%",
  "info_extract": "请列出你用来判断新闻真伪的关键信息，可以包括推理线索、引用的事实、权威数据、关键句、上下文等。例如：'2008年北京举办奥运会，2005年并无奥运会举办记录。'，多个信息请用分号分隔。如果新闻内容为空或无有效信息，请直接返回'无有效关键信息'或'内容为空'。",
  "highlighted_text": "请只返回你认为最可疑的片段内容，不要返回原文。例如：'1+1=3'"
}}

新闻内容：{text}
"""

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "你是一名资深的新闻真实性鉴定专家。"},
            {"role": "user", "content": prompt}
        ]
    }
    try:
        resp = requests.post(f"{api_base}/chat/completions", headers=headers, json=payload, timeout=20)
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        try:
            json_str_match = re.search(r'\{.*\}', content, re.DOTALL)
            if not json_str_match:
                raise ValueError("未在AI返回内容中找到有效的JSON对象")
            json_str = json_str_match.group(0)
            result = json.loads(json_str)
            label = result.get("label", "无法判断")
            reason = result.get("reason", "无")
            confidence_val = result.get("confidence")
            info_extract = result.get("info_extract", {})
            highlighted_text = result.get("highlighted_text", "")
            if isinstance(confidence_val, str):
                cleaned_confidence = confidence_val.strip()
                if re.fullmatch(r"\d{1,3}(?:\.\d+)?%", cleaned_confidence):
                    confidence = cleaned_confidence
                else:
                    confidence = "50%"
            else:
                confidence = "50%"
        except Exception as e:
            label = "解析错误"
            reason = f"AI返回内容格式错误。原始内容: {content.strip()}"
            confidence = "0%"
            info_extract = {}
            highlighted_text = ""
        return label, reason, confidence, info_extract, highlighted_text, content
    except requests.exceptions.RequestException as e:
        return "错误", "网络请求失败，无法连接到AI服务", "0%", {}, "", str(e)
    except Exception as e:
        return "错误", "调用AI服务时发生未知错误", "0%", {}, "", str(e)

def call_imgtext_ai_api(img_bytes: bytes, text: str, img_filename: str = "image.jpg"):
    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        return "错误", "API Key未配置", "0%", "", "", "后台配置错误"
    api_base = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    model = "qwen-vl-plus"
    ext = img_filename.lower().split('.')[-1]
    mime = 'jpeg' if ext in ['jpg', 'jpeg'] else 'png'
    img_b64 = base64.b64encode(img_bytes).decode('utf-8')
    image_url = f"data:image/{mime};base64,{img_b64}"
    prompt = f"""
你是一名资深的图文一致性鉴定专家。请你对下面的图片和文本内容进行分析，判断图片内容与文本描述是否一致或存在冲突。

请严格只输出如下JSON格式，不要输出任何多余内容，不要输出自然语言分析，不要输出前后缀，不要输出解释说明，只输出JSON对象：
{{
  "label": "一致/不一致/部分一致",
  "reason": "详细理由",
  "confidence": "0-100之间的数字并带百分号，如85%。如果判断为不一致，请根据冲突强度给出60%-99%的置信度，绝不能为50%。置信度绝不能为NaN、未知、无、空、null等，否则请直接输出80%",
  "conflict_info": "只写图片和文本不一致或矛盾的部分，若完全一致请写'无矛盾'，不要输出JSON，不要输出多余内容，只输出一句话"
}}

图片（base64编码）：{img_b64}
文本内容：{text}
"""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": image_url},
                    {"type": "text", "text": prompt}
                ]
            }
        ]
    }
    try:
        resp = requests.post(f"{api_base}/chat/completions", headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        try:
            json_str_match = re.search(r'\{.*\}', content, re.DOTALL)
            if not json_str_match:
                return "无法判断", "AI原文分析：" + content, "0%", "", content, content
            json_str = json_str_match.group(0)
            result = json.loads(json_str)
            label = result.get("label", "无法判断")
            reason = result.get("reason", "无")
            confidence_val = result.get("confidence")
            conflict_info = result.get("conflict_info", "")
            # 保证conflict_info为字符串且无多余JSON
            if not isinstance(conflict_info, str):
                conflict_info = str(conflict_info)
            # 如果conflict_info是JSON字符串，提取主要内容
            try:
                tmp = json.loads(conflict_info)
                if isinstance(tmp, dict):
                    conflict_info = tmp.get("conflict_info", "")
            except Exception:
                pass
            # 去除conflict_info中的JSON片段（如有）
            conflict_info = re.sub(r'\{.*\}', '', conflict_info, flags=re.DOTALL).strip()
            # 只保留第一句话
            if '。' in conflict_info:
                conflict_info = conflict_info.split('。')[0] + '。'
            if isinstance(confidence_val, str):
                cleaned_confidence = confidence_val.strip()
                if re.fullmatch(r"\d{1,3}(?:\.\d+)?%", cleaned_confidence):
                    confidence = cleaned_confidence
                else:
                    confidence = "80%"
            else:
                confidence = "80%"
            # 若label为不一致且confidence为50%，自动提升为80%
            if label == "不一致" and confidence == "50%":
                confidence = "80%"
        except Exception as e:
            return "无法判断", "AI原文分析：" + content, "0%", "", content, content
        return label, reason, confidence, conflict_info, content, content
    except requests.exceptions.RequestException as e:
        return "错误", "网络请求失败，无法连接到AI服务", "0%", "", "", str(e)
    except Exception as e:
        return "错误", "调用AI服务时发生未知错误", "0%", "", "", str(e)

def is_effective_content(content):
    # 去除所有空白字符后是否还有内容
    return bool(re.sub(r'\s+', '', content))

def extract_docx_text(raw_bytes):
    file_stream = io.BytesIO(raw_bytes)
    doc = Document(file_stream)
    full_text = []
    for para in doc.paragraphs:
        full_text.append(para.text)
    return '\n'.join(full_text)

@app.post("/api/text", response_model=PredictResult)
async def text_api(req: TextRequest):
    label, reason, confidence, info_extract, highlighted_text, raw = call_ai_api(req.text)
    # 保证info_extract为字符串
    if isinstance(info_extract, dict):
        info_extract = '; '.join([f"{k}:{v}" for k, v in info_extract.items()])
    elif not isinstance(info_extract, str):
        info_extract = str(info_extract)
    record = {
        "type": "text",
        "content": req.text,
        "label": label,
        "reason": reason,
        "confidence": confidence,
        "info_extract": info_extract,
        "highlighted_text": highlighted_text
    }
    save_history(record)
    return {
        "label": label,
        "reason": reason,
        "confidence": confidence,
        "info_extract": info_extract,
        "highlighted_text": highlighted_text,
        "raw": raw
    }

@app.post("/api/file", response_model=PredictResult)
async def file_api(file: UploadFile = File(...)):
    raw_bytes = await file.read()  # 只读取一次
    filename = file.filename.lower()
    # 处理docx
    if filename.endswith('.docx'):
        try:
            content = extract_docx_text(raw_bytes)
            encoding = 'docx'
        except Exception as e:
            content = ''
            encoding = 'docx-error'
    else:
        try:
            detected = chardet.detect(raw_bytes)
            encoding = detected['encoding'] or 'utf-8'
            content = raw_bytes.decode(encoding, errors="ignore")
        except Exception as e:
            content = raw_bytes.decode("utf-8", errors="ignore")
            encoding = 'utf-8'
    logger.info(f"[文件检测] 文件名: {file.filename}, 检测到编码: {encoding}, 内容长度: {len(content)}")
    logger.info(f"[文件检测] 内容前100字符: {content[:100]}")
    if not is_effective_content(content):
        info_extract = "无有效关键信息"
        record = {
            "type": "file",
            "filename": file.filename,
            "content": "",
            "label": "部分正确",
            "reason": "文件内容为空，无法检测。",
            "confidence": "0%",
            "info_extract": info_extract,
            "highlighted_text": ""
        }
        save_history(record)
        return {
            "label": "部分正确",
            "reason": "文件内容为空，无法检测。",
            "confidence": "0%",
            "info_extract": info_extract,
            "highlighted_text": "",
            "raw": "",
            "filename": file.filename
        }
    label, reason, confidence, info_extract, highlighted_text, raw = call_ai_api(content)
    # 保证info_extract为字符串
    if isinstance(info_extract, dict):
        info_extract = '; '.join([f"{k}:{v}" for k, v in info_extract.items()])
    elif not isinstance(info_extract, str):
        info_extract = str(info_extract)
    record = {
        "type": "file",
        "filename": file.filename,
        "content": content,
        "label": label,
        "reason": reason,
        "confidence": confidence,
        "info_extract": info_extract,
        "highlighted_text": highlighted_text
    }
    save_history(record)
    return {
        "label": label,
        "reason": reason,
        "confidence": confidence,
        "info_extract": info_extract,
        "highlighted_text": highlighted_text,
        "raw": raw,
        "filename": file.filename
    }

@app.post("/api/files")
async def files_api(files: List[UploadFile] = File(...)):
    results = []
    for file in files:
        filename = file.filename.lower()
        raw_bytes = await file.read()
        if filename.endswith('.docx'):
            try:
                content = extract_docx_text(raw_bytes)
                encoding = 'docx'
            except Exception as e:
                content = ''
                encoding = 'docx-error'
        else:
            try:
                detected = chardet.detect(raw_bytes)
                encoding = detected['encoding'] or 'utf-8'
                content = raw_bytes.decode(encoding, errors="ignore")
            except Exception as e:
                content = raw_bytes.decode("utf-8", errors="ignore")
                encoding = 'utf-8'
        if not is_effective_content(content):
            info_extract = "无有效关键信息"
            result = {
                "filename": file.filename,
                "label": "部分正确",
                "reason": "文件内容为空，无法检测。",
                "confidence": "0%",
                "info_extract": info_extract,
                "highlighted_text": "",
                "raw": ""
            }
            record = {
                "type": "file",
                "filename": file.filename,
                "content": "",
                "label": "部分正确",
                "reason": "文件内容为空，无法检测。",
                "confidence": "0%",
                "info_extract": info_extract,
                "highlighted_text": ""
            }
            save_history(record)
            results.append(result)
            continue
        label, reason, confidence, info_extract, highlighted_text, raw = call_ai_api(content)
        # 保证info_extract为字符串
        if isinstance(info_extract, dict):
            info_extract = '; '.join([f"{k}:{v}" for k, v in info_extract.items()])
        elif not isinstance(info_extract, str):
            info_extract = str(info_extract)
        result = {
            "filename": file.filename,
            "label": label,
            "reason": reason,
            "confidence": confidence,
            "info_extract": info_extract,
            "highlighted_text": highlighted_text,
            "raw": raw
        }
        record = {
            "type": "file",
            "filename": file.filename,
            "content": content,
            "label": label,
            "reason": reason,
            "confidence": confidence,
            "info_extract": info_extract,
            "highlighted_text": highlighted_text
        }
        save_history(record)
        results.append(result)
    return {"results": results}

@app.post("/api/imgtext")
async def imgtext_api(file: UploadFile = File(...), text: str = Form(...)):
    filename = file.filename
    img_bytes = await file.read()
    if len(img_bytes) > 0 and text.strip():
        label, reason, confidence, conflict_info, highlighted_text, raw = call_imgtext_ai_api(img_bytes, text, filename)
    else:
        label = "不一致"
        confidence = "50%"
        reason = "图片或文本为空，无法判断一致性。"
        conflict_info = "无有效信息"
        highlighted_text = ""
        raw = ""
    return {
        "label": label,
        "confidence": confidence,
        "reason": reason,
        "conflict_info": conflict_info,
        "highlighted_text": highlighted_text,
        "filename": filename,
        "raw": raw
    }

@app.get("/api/history")
async def get_history():
    return load_history()

@app.post("/api/clear_history")
async def clear_history_api():
    clear_history()
    return {"msg": "历史记录已清空"} 