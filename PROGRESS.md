# PROGRESS — Deskrawl 桌面 GUI

## 理解的目标 / 做序 / 最大风险
1. 目标：给已完成逆向、只读的计算内核接上桌面 GUI——手动录角色面板 → 对比两把武器谁强 → 宝石/符文/天赋/套装候选按收益排序。
2. 做序：T0 环境核验 → T1 骨架+暗色 QSS+`--smoke` → T2 档案/计算服务/面板+属性表（`--selftest` engine-ok）→ T3 装备对比对拍锚点 → T4 装配浏览器+候选排序对拍 → T5 构建存取/自检菜单/README/净 venv。
3. 最大风险：内核只读，验收全靠对拍 demo 锚点（197.9 / 226.3 / +14.32%），装配顺序或字段漏抄即偏离 → 逐字段照抄 demo，<0.5% 硬校验。
4. 次风险：armor/skill/巅峰/技能倍率在 GUI 侧语义可能与 demo 不一致 → GUI 与服务走同一 StatSheet 构造路径，直算值↔服务值双向对拍。
5. 让步序：算得对 > 跑得起来 > 界面好看。
6. 铁律：GUI 只 import stdlib/PySide6/deskrawl_calc；不动内核/文档/数据；README 仅两处；requirements-gui.txt 只 PySide6。

## 基线快照（开工时实测）
- 内核 selftest：8 项全 PASS（冻结基线）。
- demo 锚点：旧武器 DPS=197.9、新武器 DPS=226.3、Δ+28.4（+14.32%）；乘区A=1.500/1.300、暴伤×=1.302/1.502。
- 数据规模：物品 338 / 宝石 36 / 符文 151 / 天赋 186 / 符文套 13。
- `git status --porcelain -- tools/deskrawl_calc` = 空（内核干净）。
- 受保护路径 diff 哈希基线：`baseline_diff_hash=32fa99cc42476263fb9fd8d799aeb11aa1757f6c`
  （命令：`git diff -- docs data/so_dump tools/deskrawl_calc | git hash-object --stdin`）
- 注：`docs/` 与 `data/so_dump/` 在本任务开工前**就已存在**上一轮逆向工作的未提交改动（非本次引入）。
  本次以“开工快照不变”为“一字未动”的判定口径，完工时重算该哈希证明未被我改动。
- 系统 Python 3.12.8；venv `.venv-gui` 装 PySide6 6.11.2；offscreen `QApplication([])` 正常。

## 进度（滚动更新）
- [x] T0 环境核验：selftest 8 PASS；venv+PySide6 就绪；offscreen 通过。
- [x] T1 骨架：包结构 + app.py + 三 Tab + 双 dock + 暗色 QSS；`--smoke` 退出码 0；
      反向验证：QSS 改名 → `FileNotFoundError` 退出码 1（红），改回 → 绿。
- [x] T2 档案与面板：core/profile.py + core/calc_service.py + panel_editor + stat_table + target_editor；
      `--selftest` 退出码 0，输出 `8 PASS` 与 `engine-ok`（服务值↔直算值 最大相对误差 0.0000%）。
- [x] T3 装备对比：equipment_editor + compare_view；锚点 0.0248%、3 输入敏感性方向全对、
      暴伤符号反向验证通过。
- [x] T4 装配与排序：assembly_browser + candidate_rank_view；3 候选 Δ 对拍误差 0.0000%；
      行数 36/151/186/13 全部吻合。
- [x] T5 收尾：构建存取往返一致（JSON/属性表/DPS 全等）；自检菜单弹窗文案 `8 PASS / 0 FAIL`；
      README 两处已改；干净 venv 仅装 requirements-gui.txt 可启动。

## 交付物（本任务新增/改动）
- 新增 `tools/deskrawl_gui/`（15 个文件，共 1377 有效代码行，单文件最大 218 行）。
- 新增 `requirements-gui.txt`（仅 `PySide6>=6.6`）、`PROGRESS.md`、`BLOCKED.md`、`data/builds/demo-hunter.json`。
- 改动 `README.md` 两处：§2.1 新增 GUI 用法小节；§5「工具 UI」行标为 ✅。
- 受保护路径 `tools/deskrawl_calc/ docs/ data/so_dump/` 逐字节未变（基线哈希一致）。
- 运行环境：`.venv-gui`（PySide6 6.11.2，系统 Python 3.12.8）。

## 记录（决策与偏离）
- 计划文档 `.trae/documents/桌面GUI开发计划.md` 作为规格只读参考，架构与里程碑照它执行。
- 偏离（建议级）：计划 §3.3 提到「词条行底部显示 affix_range 区间提示」。任务书未要求，且阈值需
  额外引入稀有度语义，属过度设计 → 暂不实现；武器词条直接手填数值。
- 偏离（建议级）：面板的「技能」选择按计划 §3.1 存进 profile，但 v1 仅作参考倍率展示（不参与计算），
  实际计算以武器编辑区的「技能倍率」为准——避免同一语义两处事实源，也保证 demo 锚点不被污染。
- 排序基线口径：`当前构建（含当前武器词条）` 的期望 DPS；候选 Δ = 加入该候选后的 DPS − 基线。
- 交付后自查（合规收紧，非新功能）：
  1. 死规矩「界面文案全中文」→ 属性明细列头与原「词条类型」下拉的拉丁记号本地化
     （`Flat/%Add/%Mult` → 加法/百分比加算/连乘；`Base/Π/Final` → 基础值/连乘系数/最终值）；
     候选「效果」列的类型记号同法本地化（属性名仍复用内核 `stat_name()`）。
     保留 `DPS / Δ / Δ%`（任务书自身规定的列名）与品牌名 `Deskrawl`、文件类型 `JSON`、快捷键 `Ctrl+*`。
  2. 宝石「镶嵌部位」默认改为**武器孔**（原默认护甲孔）：护甲孔宝石多为防御属性，DPS 增量为 0，
     默认武器孔更贴合「谁收益高」的工具用途，也与 demo 的 `equip_category=2` 一致。
  3. `--smoke` 增设 headless 交互检查（真实控件 + 真实信号链），覆盖此前只有结构证据的要求：
     词条下拉 66 项全中文名、面板改动→属性表实时刷新、装配浏览器搜索过滤/加入/删除、
     四列（名称/DPS/ΔDPS/Δ%）可排序且 ΔDPS 按数值排、排序表双击加入构建（检查完还原，不污染 demo）。
  4. 「70 项属性」实为 66 项（见 BLOCKED.md §3），下拉按内核实际项数提供。

