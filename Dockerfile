# Hugging Face Spaces（Docker SDK）部署：免信用卡备选方案
# 用法：huggingface.co → New Space → SDK 选 Docker / CPU basic / Public → Create
#       然后把本仓库推到 Space 的 git 地址：
#       git remote add hf https://huggingface.co/spaces/<你的用户名>/<空间名>
#       git push hf main
# 首次构建约 5-10 分钟；免费档闲置 48 小时会休眠，首次唤醒约 1-2 分钟。
FROM python:3.13-slim

WORKDIR /app

# 先装依赖再拷代码：requirements 不变时复用缓存层，改代码重建更快
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# 代码 + 演示数据（poke.db ~9.7MB） + 前端构建产物（dist ~2.5MB）随镜像走
COPY backend/ ./backend/
COPY frontend/dist ./frontend/dist/

# HF Spaces 约定端口 7860；run.py 已适配 PORT 注入（有 PORT 即监听 0.0.0.0:$PORT）
# SCHEDULER_ENABLED=false：云端绝不自动爬取
ENV PORT=7860 \
    SCHEDULER_ENABLED=false \
    DEBUG=false \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 7860
CMD ["python", "backend/run.py"]
