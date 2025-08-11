<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import axios from 'axios'
import { EditPen, UploadFilled, Search, RefreshLeft, MagicStick, Document, DocumentCopy, ChatRound, Clock, Notification,Share, Loading } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import { ElMessage } from 'element-plus'
const activeMode = ref('text') // 'text' 或 'file' 或 'multi'
const textInput = ref('')
const selectedFile = ref<File|null>(null)
const multiFiles = ref<File[]>([])
const loading = ref(false)
const result = ref(false)
const showMain = ref(true)
const num_txt = ref(0)
const fileList = ref([])
const multiResultPage = ref(false)
const showLoading = ref(false)
const singleProgress = ref(0) // 单文本/文件检测进度
const multiProgress = ref(0) // 多文件检测进度
const multiProcessing = ref(false)
const imgTextProgress = ref(0) // 图文冲突检测进度


interface ResultDataType {
  label: string;
  confidence: string;
  reason: string;
  info_extract?: Record<string, string> | string;
  highlighted_text?: string;
  filename?: string;
  conflict_info?: string;
}

const resultData = ref<ResultDataType | null>(null) // 统一的检测结果

const HISTORY_KEY = 'spotfake_history'
const historyRecords = ref<any[]>([])

function loadHistoryFromLocal() {
  const data = localStorage.getItem(HISTORY_KEY)
  if (data) {
    try {
      historyRecords.value = JSON.parse(data)
    } catch {
      historyRecords.value = []
    }
  } else {
    historyRecords.value = []
  }
}

function saveHistoryToLocal() {
  localStorage.setItem(HISTORY_KEY, JSON.stringify(historyRecords.value))
}

function addHistory(record) {
  historyRecords.value.push(record)
  saveHistoryToLocal()
}

// 检测结果写入历史
const handleSubmit = async () => {
  loading.value = true
  result.value = false
  resultData.value = null
  singleProgress.value = 10

  console.log('activeMode:', activeMode.value, 'activeName:', activeName.value, 'selectedFile:', selectedFile.value)

  if (activeMode.value === 'text' && activeName.value === 'first') {
    // 文本检测
    try {
      singleProgress.value = 40
      const res = await axios.post('http://localhost:8000/api/text', { text: textInput.value })
      singleProgress.value = 80
      resultData.value = res.data
      result.value = true
      showMain.value = false
      // 写入历史
      addHistory({
        type: 'text',
        content: textInput.value,
        label: res.data.label,
        confidence: res.data.confidence,
        reason: res.data.reason,
        info_extract: res.data.info_extract || '',
        highlighted_text: res.data.highlighted_text || '',
        time: new Date().toLocaleString()
      })
      singleProgress.value = 100
    } catch (e) {
      alert('检测失败，请重试')
    } finally {
      loading.value = false
      setTimeout(() => { singleProgress.value = 0 }, 1000)
    }
  } else if (activeMode.value === 'text' && activeName.value === 'second' && selectedFile.value) {
    // 文件检测
    try {
      singleProgress.value = 40
      const formData = new FormData()
      formData.append('file', selectedFile.value)
      const res = await axios.post('http://localhost:8000/api/file', formData, { headers: { 'Content-Type': 'multipart/form-data' } })
      singleProgress.value = 80
      resultData.value = res.data
      result.value = true
      showMain.value = false
      // 写入历史
      addHistory({
        type: 'file',
        filename: selectedFile.value.name,
        label: res.data.label,
        confidence: res.data.confidence,
        reason: res.data.reason,
        info_extract: res.data.info_extract || '',
        highlighted_text: res.data.highlighted_text || '',
        time: new Date().toLocaleString()
      })
      singleProgress.value = 100
    } catch (e) {
      alert('文件检测失败，请重试')
    } finally {
      loading.value = false
      setTimeout(() => { singleProgress.value = 0 }, 1000)
    }
  } else {
    alert('请选择检测内容或文件')
    loading.value = false
    singleProgress.value = 0
    return
  }
}

// 多文件缓冲区与进度条相关
const bufferedFiles = ref<File[]>([])
const processingIndex = ref(0)
const multiResults = ref<any[]>([])


const handleMultiSubmit = async () => {
  if (multiFiles.value.length === 0) {
    ElMessage.warning('请选择要检测的文件')
    return
  }
  bufferedFiles.value = [...multiFiles.value]
  processingIndex.value = 0
  multiResults.value = []
  multiProgress.value = 0
  multiProcessing.value = true
  multiResultPage.value = false
  showLoading.value = true
  await processNextFile()
  showLoading.value = false
}

const processNextFile = async () => {
  if (processingIndex.value >= bufferedFiles.value.length) {
    multiProcessing.value = false
    ElMessage.success('全部检测完成')
    multiResultPage.value = true
    showMain.value = false
    return
  }
  const file = bufferedFiles.value[processingIndex.value]
  const formData = new FormData()
  formData.append('file', file)
  try {
    const res = await axios.post('http://localhost:8000/api/file', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    multiResults.value.push({ filename: file.name, ...res.data })
    // 写入历史
    addHistory({
      type: 'file',
      filename: file.name,
      label: res.data.label,
      confidence: res.data.confidence,
      reason: res.data.reason,
      info_extract: res.data.info_extract || '',
      highlighted_text: res.data.highlighted_text || '',
      time: new Date().toLocaleString()
    })
  } catch (e) {
    multiResults.value.push({ filename: file.name, error: '检测失败' })
  }
  processingIndex.value++
  multiProgress.value = Math.round((processingIndex.value / bufferedFiles.value.length) * 100)
  await processNextFile()
}

// 前端重启时清空历史（调用后端清空+本地清空）
async function clearAllHistory() {
  await axios.post('http://localhost:8000/api/clear_history')
  localStorage.removeItem(HISTORY_KEY)
  historyRecords.value = []
}

// 页面刷新时加载历史
onMounted(() => {
  loadHistoryFromLocal()
})


import { SIZE_INJECTION_KEY, type TabsPaneContext } from 'element-plus'

const activeName = ref('first')
const activeName_res = ref('first')

const handleClick = (tab: TabsPaneContext, event: Event) => {
  console.log(tab, event)
}

const reset = () => {
  textInput.value = ''
  selectedFile.value = null
  fileList.value = []
  multiFiles.value = []
  resultData.value = null
  result.value = false
  alert('已重新输入内容和文件选择')
}

// 修正handleFileChange，确保取fileList[0].raw
const handleFileChange = (file, fileListArr) => {
  if (fileListArr && fileListArr.length > 0) {
    selectedFile.value = fileListArr[0].raw
  } else {
    selectedFile.value = null
  }
}

// 多文件上传on-change
const handleMultiChange = (file, fileList) => {
  multiFiles.value = fileList.map(f => f.raw)
}

// 主区新增图文冲突检测UI
const imgTextInput = ref('')
const imgFileList = ref([])
const imgFile = ref<File|null>(null)
const handleImgFileChange = (file, fileListArr) => {
  if (fileListArr && fileListArr.length > 0) {
    imgFile.value = fileListArr[0].raw
  } else {
    imgFile.value = null
  }
  imgFileList.value = fileListArr
}
const resetImgText = () => {
  imgTextInput.value = ''
  imgFile.value = null
  imgFileList.value = []
  resultData.value = null
  result.value = false
}
const handleImgTextSubmit = async () => {
  loading.value = true
  result.value = false
  resultData.value = null
  imgTextProgress.value = 10
  try {
    if (!imgFile.value) {
      alert('请上传图片')
      return
    }
    imgTextProgress.value = 40
    const formData = new FormData()
    formData.append('file', imgFile.value)
    formData.append('text', imgTextInput.value)
    const res = await axios.post('http://localhost:8000/api/imgtext', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    imgTextProgress.value = 80
    resultData.value = res.data
    result.value = true
    showMain.value = false
    addHistory({
      type: 'imgtext',
      filename: imgFile.value.name,
      text: imgTextInput.value,
      label: res.data.label,
      confidence: res.data.confidence,
      reason: res.data.reason,
      info_extract: res.data.info_extract || '',
      highlighted_text: res.data.highlighted_text || '',
      conflict_info: res.data.conflict_info || '',
      time: new Date().toLocaleString()
    })
    imgTextProgress.value = 100
  } catch (e) {
    alert('图文检测失败，请重试')
  } finally {
    loading.value = false
    setTimeout(() => { imgTextProgress.value = 0 }, 1000)
  }
}


</script>

<template>
  <div class="bg">

    <div class="head">
      <h2>SpotFake</h2>
      <h3>这是一个虚假新闻检测平台</h3>
    </div>

    <div v-if="showLoading" class="loading-page">
      <div class="loading-card">
        <el-icon :size="32"><Loading /></el-icon>
        <h3>正在检测中，请稍候...</h3>
        <el-progress :percentage="multiProgress" status="active" style="margin-top: 16px;" />
      </div>
    </div>
    <div v-else-if="showMain" class="main">
      <div class="left">
        <div class="left-head">
          <el-icon :size="20">
            <MagicStick />
          </el-icon>
          <h3>检测方式</h3>
        </div>
        <div class="card mode-card">
          <div class="mode-select">
            <div
              class="mode-option"
              :class="{ active: activeMode === 'text' }"
              @click="activeMode = 'text'"
            >单文本检测</div>
            <div
              class="mode-option"
              :class="{ active: activeMode === 'multi' }"
              @click="activeMode = 'multi'"
            >多文本检测</div>
            <div
              class="mode-option"
              :class="{ active: activeMode === 'imgtext' }"
              @click="activeMode = 'imgtext'"
            >图文冲突检测</div>
          </div>
        </div>
        <div class="card">
          <div class="platformIntro">
            <el-icon>
              <ChatRound />
            </el-icon>
            <h3>平台介绍</h3>
          </div>
          <el-divider />
          <p>SpotFake是一个基于人工智能的虚假新闻检测平台，旨在帮助用户识别和过滤虚假信息。通过先进的自然语言处理技术，SpotFake能够快速分析文本内容，提供准确的检测结果。</p>
        </div>
      </div>
      <div class="mid">
        <div class="mid-head">
          <el-icon :size="20">
            <edit-pen />
          </el-icon>
          <h3>输入待检测的文本</h3>
        </div>
        <div v-if="activeMode === 'text'">
          <el-tabs v-model="activeName" class="demo-tabs">
            <el-tab-pane label="手动输入" name="first">
              <textarea 
                v-model="textInput"
                placeholder="请输入您的文本内容..."
                class="text-input"
                rows="5"
              ></textarea>
            </el-tab-pane>
            <el-tab-pane label="文件上传（txt/docx）" name="second">
              <el-upload
                class="upload-demo"
                drag
                :auto-upload="false"
                v-model:file-list="fileList"
                :on-change="handleFileChange"
                :accept="'.txt,.docx'"
              >
                <el-icon class="el-icon--upload"><upload-filled /></el-icon>
                <div class="el-upload__text">
                  拖拽或点击上传txt/docx文件
                </div>
              </el-upload>
            </el-tab-pane>
          </el-tabs>
          <div class="card">
            <el-button type="primary" :icon="Search" @click="handleSubmit" round="True" :disabled="loading">开始检测</el-button>
            <el-button type="primary" :icon="RefreshLeft" @click="reset" color="#FFFFFF" round="True" :disabled="loading">重新上传</el-button>
          </div>
           <div v-if="singleProgress > 0" class="progress-area" style="margin-top:1rem">
             <el-progress :percentage="singleProgress" status="success" />
             <p v-if="singleProgress < 100" style="text-align:center; color:#409EFF; margin-top:8px;">正在检测中...</p>
             <p v-else style="text-align:center; color:#67C23A; margin-top:8px;">检测完成！</p>
          </div>
        </div>
        <div v-else-if="activeMode === 'multi'">
          <el-upload
            class="upload-demo"
            drag
            multiple
            :auto-upload="false"
            :on-change="handleMultiChange"
            :accept="'.txt,.docx'"
          >
            <el-icon class="el-icon--upload"><upload-filled /></el-icon>
            <div class="el-upload__text">
              拖拽或点击上传多个txt/docx文件
            </div>
          </el-upload>
          <div class="card">
            <el-button type="primary" :icon="Search" @click="handleMultiSubmit" round="True" :disabled="multiProcessing">开始批量检测</el-button>
            <el-button type="primary" :icon="RefreshLeft" @click="() => { multiFiles = [] }" color="#FFFFFF" round="True" :disabled="multiProcessing">清空文件</el-button>
          </div>
          <div v-if="multiProcessing" class="progress-area" style="margin-top:1rem">
            <el-progress :percentage="multiProgress" status="success" />
            <p style="text-align:center; color:#409EFF; margin-top:8px;">正在处理第{{ processingIndex + 1 }}/{{ bufferedFiles.length }}个文件...</p>
          </div>
        </div>
        <div v-else-if="activeMode === 'imgtext'">
          <div class="imgtext-input">
            <el-upload
              class="upload-demo"
              drag
              :auto-upload="false"
              :show-file-list="true"
              :limit="1"
              :on-change="handleImgFileChange"
              :accept="'image/*'"
            >
              <el-icon class="el-icon--upload"><upload-filled /></el-icon>
              <div class="el-upload__text">拖拽或点击上传图片</div>
            </el-upload>
            <textarea
              v-model="imgTextInput"
              placeholder="请输入与图片相关的文本..."
              class="text-input"
              rows="4"
              style="margin-top: 16px; width: 100%;"
            ></textarea>
            <div class="card">
              <el-button type="primary" :icon="Search" @click="handleImgTextSubmit" round :disabled="loading">开始检测</el-button>
              <el-button type="primary" :icon="RefreshLeft" @click="resetImgText" color="#FFFFFF" round :disabled="loading">重新上传</el-button>
            </div>
            <div v-if="imgTextProgress > 0" class="progress-area" style="margin-top:1rem">
              <el-progress :percentage="imgTextProgress" status="success" />
              <p v-if="imgTextProgress < 100" style="text-align:center; color:#409EFF; margin-top:8px;">正在检测中...</p>
              <p v-else style="text-align:center; color:#67C23A; margin-top:8px;">检测完成！</p>
            </div>
          </div>
        </div>
      </div>
      <div class="right">
        <el-divider direction="vertical" class="divider-vert" />
        <div class="right-right">
          <div class="right-right-head">
            <el-icon><Clock /></el-icon>
            <h3>历史记录</h3>
          </div>
          <div class="history-list-grid scrollable-history">
            <el-button type="danger" size="small" @click="clearAllHistory">清空历史</el-button>
            <div class="history-grid">
              <el-card
                v-for="(item, idx) in historyRecords"
                :key="idx"
                class="history-card"
                shadow="hover"
              >
                <div class="history-info">
                  <span class="history-type">{{ item.type === 'text' ? '文本' : (item.type === 'imgtext' ? '图文' : '文件') }}</span>
                  <span class="history-content">
                    <template v-if="item.type === 'text' || item.type === 'imgtext'">
                      {{ item.content ? item.content.slice(0, 30) : '' }}{{ item.content && item.content.length > 30 ? '...' : '' }}
                    </template>
                    <template v-else>
                      {{ item.filename }}
                    </template>
                  </span>
                </div>
                <div class="history-meta">
                  <span class="history-label">标签：{{ item.label }}</span>
                  <span class="history-confidence">置信度：{{ item.confidence }}</span>
                </div>
                <div class="history-time">{{ item.time }}</div>
              </el-card>
            </div>
          </div>
        </div>
      </div>
    </div>
    <div v-else-if="multiResultPage" class="submit-main">
      <div class="card multi-result-page">
        <h3>批量检测结果</h3>
        <div class="multi-result-list">
          <el-card v-for="(item, idx) in multiResults" :key="item.filename + idx" class="multi-result-card" shadow="hover">
            <div><b>文件名：</b>{{ item.filename }}</div>
            <div v-if="item.error" style="color:red">{{ item.error }}</div>
            <template v-else>
              <div><b>标签：</b>{{ item.label }}</div>
              <div><b>置信度：</b>{{ item.confidence }}</div>
              <div><b>理由：</b>{{ item.reason }}</div>
              <div v-if="item.info_extract && item.info_extract !== ''"><b>关键信息：</b><span v-html="item.info_extract"></span></div>
              <div v-if="item.highlighted_text && item.highlighted_text !== ''"><b>可疑片段：</b><span v-html="item.highlighted_text"></span></div>
            </template>
          </el-card>
        </div>
        <el-button type="primary" @click="() => { showMain = true; multiResultPage.value = false; multiResults.value = [] }">返回主页</el-button>
      </div>
    </div>
    <div v-else class="submit-main">
      <div v-if="loading" class="loading">
        <div class="card">
          <div class="loading-head">
            <el-icon :size="20">
              <Notification />
            </el-icon>
            <h3>正在进行检测分析...</h3>
          </div>
          <div v-if="singleProgress > 0" class="progress-area" style="margin-top:1rem">
             <el-progress :percentage="singleProgress" status="success" />
          </div>
           <div v-if="imgTextProgress > 0" class="progress-area" style="margin-top:1rem">
              <el-progress :percentage="imgTextProgress" status="success" />
            </div>
        </div>
      </div>
      <!-- Text/File Result Display -->
      <div v-if="result && resultData && activeMode === 'text'" class="result">
        <div class="card">
          <h4 v-if="resultData.filename">文件名：{{ resultData.filename }}</h4>
          <h4>检测标签：{{ resultData.label }}</h4>
          <h4>置信度：{{ resultData.confidence }}</h4>
          <h4>理由：{{ resultData.reason }}</h4>
           <div v-if="resultData.info_extract && resultData.info_extract !== ''">
              <h4>关键信息：</h4>
              <div v-html="resultData.info_extract"></div>
            </div>
            <div v-if="resultData.highlighted_text && resultData.highlighted_text !== ''">
              <h4>可疑片段：</h4>
              <div v-html="resultData.highlighted_text"></div>
            </div>
        </div>
        <el-button type="primary" @click="showMain = true; result=false; resultData=null">返回主页</el-button>
      </div>
      <!-- ImgText Result Display -->
      <div v-if="result && resultData && activeMode === 'imgtext'" class="result">
        <div class="card">
          <h4 v-if="resultData.filename">文件名：{{ resultData.filename }}</h4>
          <h4>检测标签：{{ resultData.label }}</h4>
          <h4>置信度：{{ resultData.confidence }}</h4>
          <h4>理由：{{ resultData.reason }}</h4>
          <div v-if="resultData.conflict_info && resultData.conflict_info !== ''">
            <h4>冲突信息：</h4>
            <div>{{ resultData.conflict_info }}</div>
          </div>
           <div v-if="resultData.info_extract && resultData.info_extract !== ''">
              <h4>关键信息：</h4>
              <div v-html="resultData.info_extract"></div>
            </div>
        </div>
        <el-button type="primary" @click="showMain = true; result=false; resultData=null">返回主页</el-button>
      </div>
    </div>
  </div>
</template>

<style scoped lang="less">
* {
  margin: 0;
  padding: 0;

}

.custom-tabs-label {
  display: flex;
  align-items: center;
  gap: 10px;
}

/* .container {
  max-width: 600px;
  margin: 0 auto;
  padding: 20px;
} */
.bg{
  width: 100%;
}
.head {
  /* left: 80px; */
  /* top: 48px; */
  margin: 20px auto;
  width: 90%;
  height: 68px;
  line-height: 20px;
  border-radius: 20px;
  background: linear-gradient(190.3deg, rgba(7,255,255,0) -358.36%,rgba(4,255,249,0.24) -300.35%,rgba(0,178,255,0.58) 96.04%,rgba(0,255,240,0.58) 122.15%);
  color: rgba(16,16,16,1);
  font-size: 14px;
  color:white;
  text-align: center;
  box-shadow: 4px 4px 6px 0px rgba(16,112,255,0.27);
  font-family: PingFangSC-regular;
  display: flex;
  align-items: center;
  h2 {
    margin: 20px;
  }
}

.main {
  display: grid;
  grid-template-columns: 1fr 2fr 1fr;
  .left {
    width: 80%;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    .left-head {
      display: flex;
      align-items: center;
      gap: 20px;
      margin: 20px;
    }
    .card {
      width: 50%;
      margin-bottom: 30px;
      .platformIntro {
        display: flex;
        align-items: center;
        gap: 10px;
        margin: 20px;
      }
    }
  }
  .mid {
    .mid-head {
      display: flex;
      align-items: center;
      gap: 20px;
      margin: 20px;
      // gap: 10px;
      // margin-bottom: 20px;
    }
  }
  .right {
    display: flex;
    justify-content: space-between;
    // margin-right: 5%;
    // margin-left: 5%;
    margin: 0 auto;
    width: 80%;
    .divider-vert {
      height: 90%;
      background-color: #e0e0e0;
      margin-top: 40px;
    }
    .right-right {
      width: 90%;
      .right-right-head {
        display: flex;
        align-items: center;
        gap: 10px;
        margin: 20px;
      }
    }
  }
}

.submit-main {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1rem;
  padding: 2rem;
  .result {
     width: 80%;
  }
}

.card {
  padding: 2rem;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  background: white;
}

.mode-switcher {
  display: flex;
  gap: 10px;
  margin: 20px 0;
  justify-content: center;
}

.mode-btn {
  padding: 10px 20px;
  border: 2px solid #42b883;
  background: white;
  color: #42b883;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.3s ease;
  font-size: 14px;
}

.mode-btn:hover {
  background: #42b883;
  color: white;
}

.mode-btn.active {
  background: #42b883;
  color: white;
}

.input-section {
  margin: 20px 0;
  padding: 20px;
  border: 1px solid #e0e0e0;
  border-radius: 6px;
  background: #f9f9f9;
}

.input-section h3 {
  margin: 0 0 15px 0;
  color: #333;
}

.text-input {
  width: 100%;
  padding: 12px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 14px;
  resize: vertical;
  font-family: inherit;
}

.file-upload {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.file-input {
  position: absolute;
  opacity: 0;
  width: 0;
  height: 0;
}

.file-label {
  display: inline-block;
  padding: 12px 24px;
  background: #42b883;
  color: white;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.3s ease;
  text-align: center;
  min-width: 120px;
}

.file-label:hover {
  background: #369870;
}

.submit-btn {
  margin-top: 20px;
  padding: 12px 24px;
  background: #42b883;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 16px;
  transition: background 0.3s ease;
}

.submit-btn:hover {
  background: #369870;
}

.read-the-docs {
  color: #888;
}
.mode-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
}
.mode-btn {
  width: 120px;
  margin: 10px 0;
}

.history-list-grid {
  margin-top: 10px;
}
.history-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 10px;
}
.history-card {
  width: 220px;
  min-height: 90px;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  font-size: 13px;
}
.history-info {
  font-weight: bold;
  margin-bottom: 4px;
  display: flex;
  gap: 8px;
}
.history-type {
  color: #409EFF;
}
.history-content {
  color: #333;
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.history-meta {
  display: flex;
  gap: 8px;
  margin-bottom: 2px;
}
.history-label {
  color: #67C23A;
}
.history-confidence {
  color: #E6A23C;
}
.history-time {
  color: #aaa;
  font-size: 12px;
  margin-top: 2px;
}
.scrollable-history {
  max-height: 400px;
  overflow-y: auto;
}
.multi-result-page {
  width: 90%;
  margin: 0 auto;
  padding: 2rem;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
  background: white;
}
.multi-result-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin: 20px 0;
  max-height: 500px;
  overflow-y: auto;
}
.multi-result-card {
  width: 100%;
  min-height: 120px;
  border-radius: 8px;
  font-size: 14px;
}
.mode-select {
  display: flex;
  flex-direction: column;
  gap: 18px;
  margin: 20px 0;
}
.mode-option {
  background: #fff;
  border-radius: 14px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
  width: 66%;
  max-width: 240px;
  min-width: 120px;
  height: 48px;
  line-height: 48px;
  text-align: center;
  font-size: 15px;
  font-weight: 500;
  color: #409EFF;
  cursor: pointer;
  border: 2px solid #e0e0e0;
  transition: all 0.2s;
  margin: 0 auto;
  white-space: nowrap;
  padding: 0 18px;
}
.mode-option.active {
  background: #409EFF;
  color: #fff;
  border: 2px solid #409EFF;
  box-shadow: 0 6px 24px rgba(64,158,255,0.18);
}
.mode-option:hover {
  border: 2px solid #409EFF;
}
.loading-page {
  width: 100vw;
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255,255,255,0.95);
  z-index: 9999;
  position: fixed;
  left: 0;
  top: 0;
}
.loading-card {
  background: #fff;
  border-radius: 16px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.10);
  padding: 48px 64px;
  display: flex;
  flex-direction: column;
  align-items: center;
}
.progress-area {
  margin-top: 10px;
  margin-bottom: 10px;
}
</style>
