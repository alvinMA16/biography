# 回忆录

帮助老年人通过AI对话记录人生故事的产品。

## 快速开始

### 1. 准备工作

**获取通义千问 API Key：**
1. 访问 https://dashscope.console.aliyun.com/
2. 注册/登录阿里云账号
3. 开通 DashScope 服务
4. 在 API-KEY 管理中创建 API Key

### 2. 启动后端

```bash
# 进入后端目录
cd backend

# 创建虚拟环境（推荐）
python -m venv venv
source venv/bin/activate  # Mac/Linux
# 或 venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt

# 复制环境变量配置
cp .env.example .env

# 编辑 .env 文件，填入你的通义千问 API Key
# DASHSCOPE_API_KEY=your_api_key_here

# 启动服务
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

启动成功后，访问 http://localhost:8000 应该看到：
```json
{"message": "回忆录 API 服务正在运行", "version": "0.1.0"}
```

### 3. 启动前端

直接用浏览器打开 `web/index.html` 即可。

或者用 Python 启动一个简单的 HTTP 服务器：
```bash
cd web
python -m http.server 3000
```
然后访问 http://localhost:3000

## 项目结构

```
biography/
├── docs/                    # 文档
│   ├── PRD.md              # 产品需求文档
│   └── 技术方案.md          # 技术方案
├── backend/                 # 后端
│   ├── app/
│   │   ├── main.py         # 入口
│   │   ├── config.py       # 配置
│   │   ├── database.py     # 数据库
│   │   ├── models/         # 数据模型
│   │   ├── api/            # API接口
│   │   ├── services/       # 业务逻辑
│   │   └── prompts/        # AI提示词
│   ├── requirements.txt
│   └── .env.example
├── web/                     # 前端
│   ├── index.html          # 首页
│   ├── chat.html           # 对话页
│   ├── memoir.html         # 回忆录页
│   ├── css/
│   └── js/
└── README.md
```

## API 文档

启动后端后，访问 http://localhost:8000/docs 可以查看完整的 API 文档。

## 后续开发

1. **部署到服务器**：后端代码可直接部署，只需修改 `.env` 中的数据库连接为 PostgreSQL
2. **开发小程序**：使用相同的后端 API，开发微信小程序前端
3. **添加语音功能**：接入语音识别和语音合成
