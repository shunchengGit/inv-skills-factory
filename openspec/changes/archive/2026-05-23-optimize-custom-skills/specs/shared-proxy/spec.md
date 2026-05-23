## ADDED Requirements

### Requirement: 统一代理检测函数
系统 SHALL 提供 `detect_proxy()` 函数，按以下优先级检测可用代理：
1. 环境变量 `HTTPS_PROXY` / `HTTP_PROXY` / `https_proxy` / `http_proxy`（按此顺序，首个非空值）
2. 本地 Clash 端口扫描 `7890`、`7891`、`7897`（`socket.create_connection` 超时 0.5s）
3. 均不可用则返回 `None`

#### Scenario: 环境变量已设置
- **WHEN** `HTTPS_PROXY` 环境变量已设为 `http://127.0.0.1:7890`
- **THEN** `detect_proxy()` 返回 `"http://127.0.0.1:7890"`，不进行端口扫描

#### Scenario: 环境变量未设置但 Clash 正在运行
- **WHEN** 无代理环境变量，但 `127.0.0.1:7890` 可连接
- **THEN** `detect_proxy()` 返回 `"http://127.0.0.1:7890"`

#### Scenario: 无任何代理可用
- **WHEN** 无代理环境变量且所有 Clash 端口不可连接
- **THEN** `detect_proxy()` 返回 `None`

### Requirement: 为 yfinance/curl_cffi 设置环境变量代理
系统 SHALL 提供 `setup_proxy_env(override=None)` 函数，将代理地址写入 `os.environ`。

#### Scenario: 自动检测并设置
- **WHEN** 调用 `setup_proxy_env()` 且 `detect_proxy()` 返回有效代理
- **THEN** `os.environ` 中 `HTTPS_PROXY` 和 `HTTP_PROXY` 被设为该代理地址（使用 `setdefault`，不覆盖已有值），函数返回 `True`

#### Scenario: 手动覆盖
- **WHEN** 调用 `setup_proxy_env(override="http://proxy:8080")`
- **THEN** 使用 `override` 值而非自动检测结果

#### Scenario: 无代理可用
- **WHEN** 调用 `setup_proxy_env()` 且 `detect_proxy()` 返回 `None`
- **THEN** 向 stderr 输出警告信息，函数返回 `False`

### Requirement: 为 requests.Session 设置代理
系统 SHALL 提供 `apply_proxy_to_session(session, proxy=None)` 函数，将代理设入 `session.proxies`。

#### Scenario: 自动检测并应用
- **WHEN** 调用 `apply_proxy_to_session(session)` 且 `detect_proxy()` 返回有效代理
- **THEN** `session.proxies["http"]` 和 `session.proxies["https"]` 被设为该代理地址

#### Scenario: 显式指定代理
- **WHEN** 调用 `apply_proxy_to_session(session, proxy="http://proxy:8080")`
- **THEN** 使用显式指定的代理值

#### Scenario: 无代理可用
- **WHEN** 调用 `apply_proxy_to_session(session)` 且 `detect_proxy()` 返回 `None`
- **THEN** session 的 proxies 不被修改

### Requirement: 临时清除与恢复代理环境变量
系统 SHALL 提供 `clear_proxy_env()` 和 `restore_proxy_env()` 函数，用于 akshare 等国内数据源不需要代理的场景。

#### Scenario: 清除后恢复
- **WHEN** 先调用 `clear_proxy_env()`，然后调用 `restore_proxy_env()`
- **THEN** 清除时将 `HTTP_PROXY`/`HTTPS_PROXY`/`http_proxy`/`https_proxy` 从 `os.environ` 中移除并保存；恢复时将保存的值写回 `os.environ`

#### Scenario: 无代理需要清除
- **WHEN** 调用 `clear_proxy_env()` 但环境变量中无代理设置
- **THEN** 不报错，保存的值为空 dict

### Requirement: 模块位置与导入方式
`proxy.py` SHALL 位于 `custom-skills/_shared/proxy.py`。各技能脚本通过 `sys.path.insert(0, Path(__file__).resolve().parents[N] / "_shared")` 引入后 `from proxy import ...`。

#### Scenario: 从 cs-stock 脚本导入
- **WHEN** `cs-stock/scripts/cs_stock_info.py` 需要 `setup_proxy_env` 和 `clear_proxy_env`
- **THEN** 通过 `from proxy import setup_proxy_env, clear_proxy_env, restore_proxy_env` 导入，无需 pip install

#### Scenario: 从 fuyao 脚本导入
- **WHEN** `fuyao-leading-indicators/scripts/eastmoney_fetch.py` 需要 `apply_proxy_to_session`
- **THEN** 通过 `from proxy import detect_proxy, apply_proxy_to_session` 导入
