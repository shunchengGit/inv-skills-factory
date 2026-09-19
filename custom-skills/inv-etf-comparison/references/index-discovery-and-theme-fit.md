# 官方指数发现与窄主题适配

## 已实际跑通的中证公开接口
基础地址 `https://www.csindex.com.cn/csindex-home/`。来源为官网首页加载的前端JS；若接口变化，从当前首页script链接重新发现，不固定缓存JS文件名。

GET路径：
- `indexInfo/index-fuzzy-search?searchInput=<URL编码关键词>&pageNum=1&pageSize=100`
- `indexInfo/index-basic-info/<已核实指数代码>`
- `index/weight/top10new/<已核实指数代码>`
- `index-list/queryByIndexCode/<已核实指数代码>`

搜索必须传分页参数；用H30590等已知代码作正向控制，核查返回code、success、data、total及页数。关键词“机器人”曾有效返回H30590、932438、932599，证明当时搜索接口可用；“人形”为空不是不存在证明。关联产品空数组也不等于没有ETF，应另查管理人或交易所。

基本信息提供全称、代码、发布日期、调样频率、摘要；前十大提供updateDate、weightList、top10Sum。摘要不能替代完整方法。上市ETF身份仍须管理人产品页或交易所文件闭环。

## 国证目录
从 `https://www.cnindex.com.cn/` 首页“指数列表”“产品列表”取得当次最新下载链接。文件链接带版本时间，禁止将本次路径固定成永久入口。读取所有sheet、保留表头、按全称与简称检索，并记录目录版本日。XLSX可用Excel读取库；标准库替代为zipfile读取sharedStrings.xml及worksheets XML，按单元格t=s解析共享字符串。XLS不是ZIP，不能沿用XLSX解析。

## 官方PDF解析与示例
2025年5月V1.0的932438方法已实际读取：
https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/indices/detail/files/zh_CN/932438_Index_Methodology_cn.pdf

网页提取若返回%PDF二进制，下载原始字节后用pdftotext解析；本次 `pdftotext - -` 通过stdin/stdout成功，勿将乱码当原文或可靠摘要。

该版本：科创板/创业板、通常上市超过6个月、非ST/*ST；成交额前90%；业务相关性筛选后按过去一年日均总市值取40。部组件/通用机器人单股上限10%；关键技术及单一场景产品单股3%、该组合计20%；单板块80%；半年调整。包括扫地机器人、AI芯片和算法，没有量化人形机器人实际收入或研发比例门槛。因此只能说智能机器人相关，不能视作纯人形零部件。

权重因子通常随定期调整设定，市场涨跌可令观察权重超过初始上限；比较权重前先读维护规则。上述仅为已验证方法案例，不是当前方法、持仓或产品存续的永久断言。

## 交付核验
- 名称/代码全部由官方原文产生，不从记忆补齐。
- 前十大标明指数或基金、日期及分母；合计用工具验证。
- 未检出结论列范围、目录日期与正向控制结果。
- 只交付工具真实取得的内容；报告中不凭空加入其他agent任务分工。
- 限时先写实质成果与缺口，最后重读文件确认补丁与结论一致。
