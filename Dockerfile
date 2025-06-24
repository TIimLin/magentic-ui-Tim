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

# 翻譯前端英文字串為中文（僅在容器內替換，不修改原始碼）
RUN set -e && \
    # Chat 視圖
    sed -i 's/Enter a message to get started/輸入訊息以開始/g' /app/frontend/src/components/views/chat/chat.tsx && \
    # Sidebar 相關字串
    sed -i -e 's/Current Session/目前會話/g' \
           -e 's/Saved Plans/已保存計劃/g' \
           -e 's/Sessions/會話/g' \
           -e 's/Loading\.{3}/載入中.../g' \
           -e 's/Create new session/建立新會話/g' \
           -e 's/New Session/新增會話/g' \
           -e 's/No recent sessions found/沒有最近會話/g' \
           -e 's/Today/今天/g' \
           -e 's/Yesterday/昨天/g' \
           -e 's/Last 7 Days/最近 7 天/g' \
           -e 's/Last 30 Days/最近 30 天/g' \
           -e 's/Older/更早/g' /app/frontend/src/components/views/sidebar.tsx && \
    # Content Header
    sed -i -e 's/Close Sidebar/關閉側邊欄/g' \
           -e 's/Open Sidebar/開啟側邊欄/g' /app/frontend/src/components/contentheader.tsx && \
    # Settings 相關
    sed -i -e 's/Dark Mode/深色模式/g' \
           -e 's/Light Mode/淺色模式/g' \
           -e 's/Model Configuration/模型設定/g' /app/frontend/src/components/settings.tsx && \
    # Settings 進階翻譯
    sed -i -e 's/General/一般/g' \
           -e 's/Advanced/進階/g' \
           -e 's/Action Approval Policy/操作審批策略/g' \
           -e 's/Never require approval/不需要審批/g' \
           -e 's/AI based judgement/AI判斷/g' \
           -e 's/Always require approval/總是需要審批/g' \
           -e 's/Allowed Websites List/允許網站列表/g' \
           -e 's/Restricted to List/僅限列表/g' \
           -e 's/All Websites Allowed/允許所有網站/g' \
           -e 's/Allow Replans/允許重新規劃/g' \
           -e 's/Retrieve Relevant Plans/取得相關計劃/g' \
           -e 's/No plan retrieval/不取回計劃/g' \
           -e 's/Retrieve plans as hints/以提示方式取回計劃/g' \
           -e 's/Retrieve plans to use directly/直接取回計劃/g' \
           -e 's/Reset to Defaults/重設為預設值/g' \
           -e 's/Add/新增/g' \
           -e 's/Controls when approval is required before taking actions/控制在執行操作前何時需要批准/g' \
           -e 's/When enabled, Magentic-UI will only be able to visit websites/啟用後，AI Search 僅能訪問您加入列表的網站/g' \
           -e 's/Allowed Websites List/允許網站列表/g' \
           -e 's/Restricted to List/僅限列表/g' \
           -e 's/All Websites Allowed/允許所有網站/g' \
           -e 's/When enabled, Magentic-UI will automatically replan if the current plan is not working or you change the original request/啟用後，若當前計劃失效或您變更需求，AI Search 將自動重新規劃/g' \
           -e 's/Controls how Magentic-UI retrieves and uses relevant plans from previous sessions/控制 AI Search 如何從先前會話取得並使用相關計劃/g' \
           -e 's/Select LLM for All Clients/選擇所有客戶端使用的 LLM/g' \
           -e 's/Select model to use for all clients/選擇所有客戶端要使用的模型/g' \
           -e 's/Import YAML/匯入 YAML/g' \
           -e 's/This will update the model configuration for all agent clients (orchestrator, coder, web surfer, and file surfer)/這將更新所有代理客戶端（協調器、程式員、網頁瀏覽器、檔案瀏覽器）的模型設定/g' \
           -e 's/YAML configuration for the underlying LLM of/代理 LLM 的 YAML 設定/g' \
           -e 's/the agents\./代理/g' \
           -e 's/The configuration uses AutoGen/該設定使用 AutoGen/g' \
           -e 's/ChatCompletionClient format\./ChatCompletionClient 格式。/g' \
           -e 's/Must include configurations for:/必須包含以下設定：/g' \
           -e 's/orchestrator_client, coder_client,/orchestrator_client、coder_client、/g' \
           -e 's/web_surfer_client, and file_surfer_client\./web_surfer_client 以及 file_surfer_client。/g' \
           -e 's/Each client should follow the AutoGen/每個客戶端都應遵循 AutoGen/g' \
           -e 's/ChatCompletionClient specification with/ChatCompletionClient 規範，包含/g' \
           -e 's/provider, config (model, etc), and/provider、config（模型等）與/g' \
           -e 's/max_retries\./max_retries。/g' \
           -e 's/Changes require a new session to take effect\./變更需建立新會話才會生效。/g' \
           -e 's/you add to the list below\.s/您新增到下方清單的網站/g' \
           -e 's/Warning: Settings changes will only apply when you create a new session/警告：設定變更僅在建立新會話後生效/g' \
           /app/frontend/src/components/settings.tsx && \
    # PlanList 相關
    sed -i 's/Your Saved Plans/您的已保存計劃/g' /app/frontend/src/components/features/Plans/PlanList.tsx && \
    # ChatInput 與範例任務/簽名等
    sed -i -e 's/Type your message here\.\.\./請在此輸入訊息.../g' \
           -e 's/Type your message here\.{3}/請在此輸入訊息.../g' \
           -e 's/Type your message here/請在此輸入訊息/g' \
           -e 's/or try a sample task from below/或從下方範例任務開始/g' \
           -e 's/Attach File or Plan/附加檔案或計劃/g' \
           -e 's/Attach File/附加檔案/g' \
           -e 's/Attach Plan/附加計劃/g' \
           -e 's/No plans available/沒有可用計劃/g' /app/frontend/src/components/views/chat/chatinput.tsx && \
    sed -i 's/or try a sample task from below/或從下方範例任務開始/g' /app/frontend/src/components/views/chat/sampletasks.tsx && \
    # Footer Disclaimer
    sed -i 's/Magentic-UI can make mistakes\. Please monitor its work and intervene if necessary\./AI Search 可能會出錯，請留意其操作並在必要時介入。/g' /app/frontend/src/components/layout.tsx && \
    # SignIn Modal
    sed -i -e 's/Enter a username\./請輸入使用者名稱。/g' \
           -e 's/A change of username will create a new profile\./變更使用者名稱將建立新檔案。/g' \
           -e 's/placeholder="Enter a username"/placeholder="請輸入使用者名稱"/g' \
           -e 's/Sign In/登入/g' /app/frontend/src/components/signin.tsx && \
    # LearnPlan Button 與 Tooltip
    sed -i -e 's/Learn Plan/學習計劃/g' \
           -e 's/Learn a reusable plan from this conversation and save it to your library/從此對話學習可重用的計劃並保存到您的庫/g' /app/frontend/src/components/features/Plans/LearnPlanButton.tsx && \
    # Plan 相關字串
    sed -i -e 's/Here\x27s a plan\. /以下是計劃。/g' \
           -e 's/You can edit it directly or through the chat\./您可以直接編輯，或透過聊天修改。/g' \
           /app/frontend/src/components/views/chat/plan.tsx && \
    # Status Icon 中文化
    sed -i 's/Waiting for your input/等待您的輸入/g' /app/frontend/src/components/views/statusicon.tsx && \
    # Approval Buttons
    sed -i -e 's/Accept Plan/接受計劃/g' \
           -e 's/Generate New Plan/重新生成計劃/g' /app/frontend/src/components/views/chat/approval_buttons.tsx && \
    # Add Step button
    sed -i 's/Add Step/新增步驟/g' /app/frontend/src/components/views/chat/plan.tsx && \
    # Detail Viewer Tabs
    sed -i -e 's/Screenshots/截圖/g' \
           -e 's/Live View/即時畫面/g' /app/frontend/src/components/views/chat/detail_viewer.tsx && \
    # ChatInput 其他 placeholder
    sed -i 's/Type your response here and let Magentic-UI know of any changes in the browser\./請在此輸入回覆，並告訴 AI Search 瀏覽器中的變更。/g' /app/frontend/src/components/views/chat/chatinput.tsx && \
    # ProgressBar 狀態文字
    sed -i -e 's/Planning\.{3}/規劃中.../g' \
           -e 's/Task Completed/任務完成/g' /app/frontend/src/components/views/chat/progressbar.tsx

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