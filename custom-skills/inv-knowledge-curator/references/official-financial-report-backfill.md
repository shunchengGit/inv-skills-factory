# 官方财报缺口审计与补库

用于持仓财报覆盖审计，以及从公司官网或监管申报补齐官方原始材料。

## 覆盖口径

必须区分两层，不能把卖方财报后点评等同于官方财报已入库：

1. **分析覆盖**：存在最新财报后的独立研报分析。
2. **完整入库**：官方原始文件已归档，存在 `Reference` 条目，完成关联、索引重建、lint 与 Git push。

审计时分别报告两层；ETF等无公司财报的资产标注“不适用”。

## 标准闭环

1. 读取持仓主信源，逐只确定最新已披露报告期。
2. 同时检查 `res/index.md` 与 `entries/*.md`，核对官方文件、`Reference` 条目和报告期。
3. 优先从公司投资者关系官网定位；港股可用港交所公告，美股用SEC 10-K/10-Q，外国发行人用SEC 6-K/20-F及Exhibit。
4. 下载后验证文件类型、页数和可提取文本量，避免把Cloudflare HTML、错误页或不完整转换件当PDF。
5. 用 `km_import.py res` 归档，生成25-50行 `Reference` 条目；description含核心数字，关键要点≥3，关联≥2。
6. 执行 `km_lint.py --fix --skip-url-check`，再无修复模式复验。
7. 验证 `okf_errors=0`、`dead_links=0`、`pdf_no_entry=0`、`pdf_resource_missing=0`，Git工作区干净且本地HEAD等于远端分支。

## 可靠降级路径

### 官网PDF被Cloudflare阻断

不要用二手媒体替代。若公司是SEC申报人：

1. 从 `https://data.sec.gov/submissions/CIK##########.json` 查目标报告期申报。
2. 下载EDGAR主申报及官方Exhibit HTML。
3. 必要时用无页眉页脚的Headless Chrome打印成PDF。
4. 条目中注明监管申报及Exhibit来源。

### 官网仅提供DOCX/HTML

优先查SEC原始HTML申报并打印为PDF。若转换DOCX，必须验证页数和文本量；结果明显过短时不得作为完整年报。

### A股搜索召回差或公告聚合接口缺失

优先直接查询交易所公告元数据接口，而不是反复改写中文搜索词。上交所已验证的查询形态：

```text
https://query.sse.com.cn/security/stock/queryCompanyBulletin.do
  ?isPagination=true
  &productId={股票代码}
  &securityType=0101,120100,020100,020200,120200
  &reportType2=DQBG
  &reportType=ALL
  &pageHelp.pageSize=25
  &pageHelp.pageNo=1
  &pageHelp.beginPage=1
  &pageHelp.endPage=5
```

请求带 `Referer: https://www.sse.com.cn/` 和常规浏览器 `User-Agent`。解析 `pageHelp.data` 中的 `SSEDATE`、`TITLE`、`URL`，按报告期选择“完整报告”而非“摘要”；定期报告条目会明确区分“半年度报告”和“半年度报告摘要”。

该接口只负责**权威定位与元数据核验**。只有 `URL` 对应文件实际下载并通过 PDF 魔数、页数和文本量检查后，才能进入 `km_import.py res`。浏览器能打开、接口返回 URL 或结构化财务数据已更新，都不能替代原始 PDF 归档，也不能据此宣称正式入库完成。深交所标的应使用对应交易所或巨潮官方入口，不套用上交所接口。

### 上交所PDF下载命中JavaScript挑战页

上交所公告PDF在浏览器查看器中可能正常打开，但命令行下载只返回带 `acw_sc__v2` JavaScript挑战的HTML。此时不要归档、不要尝试把挑战页当PDF解析，也不要用财经媒体或卖方报告替代官方原件。已验证的官方镜像降级路径：

1. 保留上交所公告接口返回的证券代码、披露日期和完整报告标题，先完成权威元数据核验，并明确排除“报告摘要”。
2. 调用巨潮资讯公告查询接口，按证券代码、报告类别和窄日期窗口定位同一份公告；从结果读取 `announcementTitle` 和 `adjunctUrl`。
3. 从 `https://static.cninfo.com.cn/{adjunctUrl}` 下载完整PDF。巨潮在此仅作为同一监管披露文件的官方镜像，不改变来源属性。
4. 对镜像文件执行 `file`、`pdfinfo`、`pdftotext` 三重检查，并核对首页公司名称、报告期和完整报告页数；任何一项异常都停止归档。
5. 通过后再串行执行 `km_import.py res`，建立 `Reference` 条目，运行 `km_lint.py --fix --skip-url-check` 与无修复复验，确认Git push及本地/远端HEAD一致。

浏览器PDF查看器显示的页数可作为完整性旁证，但不能替代本地PDF魔数、页数和可提取文本量验证。

## 完整性检查

```bash
file report.pdf
pdfinfo report.pdf | grep Pages
pdftotext report.pdf - | wc -c
```

批量结果还要逐个确认文件被Git跟踪，并核验远端提交一致性。仅看到脚本返回成功，不能宣称完整入库。
