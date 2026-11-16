# samplekit — Facet Proof 样本委托工具

`samplekit` 通过 Facet Proof 的真实 in-process 路由（与 JSON HTTP 服务同一套
校验、封存、租约与分块代码）构建可续做的多件装配样本库。它不开放网络端口，
也不绕过任何服务规则。

## 命令

所有命令都支持隔离模式运行（仅把仓库根加入 `sys.path`，不读取站点包或
调用方环境变量）：

```sh
# 委托并渲染目录样本；已完成的样本自动跳过，中断过的曝光先回收租约再续做
python3 -I tools/run_samplekit.py --root ./sample-work build [--only S01 S02] [--max-steps 20]

# 把所有 state=complete 的样本导出为接收者数据集
python3 -I tools/run_samplekit.py --root ./sample-work export --output ./sample-dataset

# 仅基于磁盘文件与独立读取器复核已导出的数据集
python3 -I tools/run_samplekit.py audit --dataset ./sample-dataset
```

## 跨多次运行扩充

- `--root` 指向持久数据根（SQLite + 内容寻址块）。同一根目录上重复 `build`
  是幂等的：资源索引 `resource-index.json` 记住目录键到服务 id 的映射，
  `commission-journal.json` 记住每个样本的 seal、曝光、图版与核验状态。
- 新增样本：在 `samplekit/catalog.py` 的 `SAMPLES` 中追加定义并再次 `build`，
  已有样本不会被重新渲染或替换。
- 中断：直接重新执行同一条 `build`。工具先调用 `worker/recover` 回收过期
  租约，分块渲染器复用已提交的 64×64 块，仅补做缺失块。
- 目录定义变更：已封存样本的 `spec_hash` 与新定义不一致时进入 `drifted`，
  原 seal 与图版原样保留；需要新几何时请使用新的样本 id，而不是改写旧 id。

## 模块

| 文件 | 职责 |
| --- | --- |
| `catalog.py` | 版本化的纯数据目录：网格、材质、十个样本的部件/镜头/采样定义 |
| `geometry.py` | 过程化封闭曲面网格（盒、圆柱、锥台、球、合并盒），自动校正绕序 |
| `client.py` | 路由层薄封装，含模拟工作器硬崩溃的测试辅助 |
| `store.py` | 持久日志与资源索引、规范哈希 |
| `commissioner.py` | 资源录入、一次性封存、幂等曝光、租约恢复、完整度闸门 |
| `exporter.py` | 导出六通道、bundle、元数据与逐样本/全集清单及独立交叉核对 |
| `__main__.py` | `build` / `export` / `audit` 命令行 |
