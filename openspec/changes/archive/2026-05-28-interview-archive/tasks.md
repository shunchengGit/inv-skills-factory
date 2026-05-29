## 1. 归档命令实现

- [x] 1.1 在 interview.py 中添加 `ARCHIVE_DIR` 常量（`INTERVIEW_DIR / "archived"`）
- [x] 1.2 实现 `archive(name)` 函数：校验候选人存在、已面试、未归档，创建 `archived/<姓名>/` 目录，移动 PDF 和面试题 .md
- [x] 1.3 在 argparse 中注册 `archive` 子命令，接受 `name` 参数

## 2. List 命令扩展

- [x] 2.1 修改 `list_candidates()` 函数，添加 `show_all` 参数，默认只扫描 resume/
- [x] 2.2 实现 archived 候选人扫描：遍历 `archived/` 子目录，提取姓名和文件信息，状态标注"已归档"
- [x] 2.3 在 argparse 中为 `list` 子命令添加 `--all` flag

## 3. SKILL.md 更新

- [x] 3.1 在命令表中添加 archive 命令说明
- [x] 3.2 更新数据目录结构说明，标注 archived/ 按人建子目录
