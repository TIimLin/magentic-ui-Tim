# 使用一個包含 Python 和 Debian 的基礎映像，確保穩定性和所需的套件
FROM python:3.12-slim-bookworm

# 設定容器內的工作目錄
WORKDIR /app

# 安裝系統依賴：
# nodejs 和 npm 用於前端構建 (Gatsby)
# yarn 是前端構建所需的套件管理器
# ffmpeg 用於解決 pydub 的 RuntimeWarning，並可能支援視訊/音訊處理功能
RUN apt-get update && \
    apt-get install -y \
    nodejs \
    npm \
    ffmpeg \
    rsync \ 
    --no-install-recommends && \
    npm install -g yarn && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# 將整個 Magentic-UI 專案目錄複製到容器的 /app 目錄
COPY . /app

# 安裝本專案（含所有 extras）到容器，而非 PyPI 上的舊版
# 這可確保 CLI 旗標如 --novnc-port 等最新功能都能使用
RUN pip install --no-cache-dir -e .[all]

# 構建前端資產 (Gatsby)
WORKDIR /app/frontend
RUN yarn install && \
    yarn build

# 返回到應用程式的根目錄
WORKDIR /app

# 將您的 config.yaml 複製到容器中
# 確保在執行 docker build 的目錄下有 config.yaml 檔案
# COPY config.yaml ./config.yaml

# 暴露 Magentic-UI 應用程式將監聽的連接埠
EXPOSE 8081

# 定義容器啟動時執行的命令
# 直接運行 Magentic-UI 應用程式，因為現在所有依賴都已在全局環境中
# --host 0.0.0.0 讓應用程式監聽容器內所有網路介面。
# CMD ["magentic", "ui", "--host", "0.0.0.0", "--port", "8081", "--config", "./config.yaml"]
CMD ["magentic", "ui", "--host", "0.0.0.0", "--port", "8081"]