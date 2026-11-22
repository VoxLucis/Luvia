# Semicon Intelligence | 半導體產業情報站

完整靜態網站＋每週新聞 RSS 同步程式。首頁 `index.html`，資料存放 `data/news.json`。

## 立即試用

在這個資料夾執行 `python -m http.server 8000`，開啟 http://localhost:8000 。不可直接雙擊 HTML：某些瀏覽器禁止 `file://` 讀取 JSON。

## 發布（GitHub Pages）

1. 建立 GitHub repository，將本資料夾所有檔案上傳，包括 `.github/workflows/weekly.yml`。
2. 進入 Settings → Pages → Build and deployment → Deploy from a branch，選 `main` / `/ (root)`。
3. 在 Settings → Actions → General 中允許工作流程讀寫 repository contents（若預設未允許）。
4. 進 Actions 手動執行 `Weekly semiconductor intelligence update` 測試一次。
5. 之後每週日台灣時間 09:00 排程更新；GitHub 排程可能延遲，不保證準時。

## 更新與透明度

初始資料是 2026-11-22 選錄的可追溯新聞；自動新增者均標示「自動蒐集・未查核」，只代表標題候選清單，**不會自動捏造深度分析或確定產業影響**。RSS 源可能臨時失效、變更格式或連結跳轉，需定期檢查 Actions 記錄。初始資料和後續蒐集候選可能有重複。

如需 AI 摘要、可靠度分級、跨週差異報告與直接寄信，需要另接內容解析、模型 API、資料庫與排程服務，現在未啟用。收藏採本機瀏覽器 localStorage，不會跨裝置同步。網站預設不需要使用者帳密，若公開部署則所有資料公開。
