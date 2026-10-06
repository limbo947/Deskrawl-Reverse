# BLOCKED — 待裁决清单

## 阻塞项

**无。** 五道任务（T0–T5）全部完成，无未解决阻塞，无需跳过的子项。

## 非阻塞待裁决（已按标注口径执行，不影响交付）

### 1. 完成条件「`git status --porcelain -- tools/deskrawl_calc docs data/so_dump` 输出为空」
与开工前既有改动冲突。

- 实测：`tools/deskrawl_calc` 输出为空（干净）；但 `docs/`（5 个 .md）与 `data/so_dump/`（5 个
  .json）在**本任务开工之前**就已存在上一轮逆向工作的未提交改动。
- 本次采用的口径：**「开工快照逐字节不变」= 一字未动**。
  - 开工基线：`git diff -- docs data/so_dump tools/deskrawl_calc | git hash-object --stdin`
    = `32fa99cc42476263fb9fd8d799aeb11aa1757f6c`
  - 完工重算：同为 `32fa99cc42476263fb9fd8d799aeb11aa1757f6c` → 本次未改动这些路径。
- 若裁决坚持字面口径（git status 必须为空），需先把上一轮的改动提交为 commit；本任务无权提交代码，
  故未执行。

### 2. 仓库根 `.gitignore` 于本任务期间出现（非本人创建）
- 内容：`.trae/`、`.venv-gui/`、`data/so_dump/RuneData.json`。
- 本任务只按 T0 指令创建了 `.venv-gui/`，未创建/修改 `.gitignore`；推断为 IDE/环境在检测到 venv 时自动生成。
- 依「其余一切只读」的界限，**未触碰**该文件，仅在此报备。其忽略 `.venv-gui/` 的效果本身符合预期。

### 3. 任务书写「词条下拉用内核 70 项中文名」，内核实际为 66 项
- 实测：`len(list(StatType)) == len(StatType.__members__) == 66`，无别名、无重复值；
  `STAT_NAMES` 恰好 66 键（0–65），全部有中文名，无 `Stat##` 兜底项。
- 处理：下拉框提供内核**实际存在的全部 66 项**中文名（`--smoke` 交互检查已断言「66 项且无兜底名」）。
- 无法凑到 70：多出的 4 项在内核里不存在，凭空新增必须改内核（死规矩禁止）。
- 结论：任务书/计划文档中的「70 项」应为笔误，实际以 66 项为准。
