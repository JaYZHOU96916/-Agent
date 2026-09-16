# 可复现示例

示例完全由 `generate.py` 合成，不包含用户数据或真实证券行情。生成器不联网，固定种子和日期；CSV 使用 UTF-8 BOM，便于 Excel 打开中文。数据文件受 `.gitignore` 保护，提交的是生成脚本。

```sh
python3 examples/generate.py
# 已有输出时，换一个目录，避免覆盖：
python3 examples/generate.py --output examples/generated/second-run

# Python 3.11+，安装 backend/requirements.txt 后：
.venv/bin/python examples/generate.py --format all --output examples/generated/all-formats
```

默认只生成 CSV，无第三方依赖。`--format all` 同时生成 CSV、XLSX 和 Parquet，依赖 Pandas、openpyxl 和 pyarrow。默认目录下文件已存在时，整次生成在写入前中止；不会覆盖之前的示例。

## sales

288 行，每行是一组“月份 × 地区 × 产品 × 渠道”的月度汇总，不是单笔订单。金额单位为合成的人民币元，无税额、退款或汇率换算。不要把行数当成订单数。

| 字段 | 含义 |
| --- | --- |
| `date` | 月初 ISO 日期字符串，覆盖 2025 年 1–12 月 |
| `region` | 华东、华南、华北、西部 |
| `product` | 基础版、专业版、企业版 |
| `channel` | 线上、合作伙伴 |
| `units` | 当月销量 |
| `unit_price` | 单价，分别为 99、299、899 |
| `revenue` | 销量 × 单价 |
| `cost` | 销售额 × 62%，保留两位小数 |
| `profit` | `revenue - cost`，未扣除营销支出 |
| `marketing_spend` | 合成营销费用，故意留下 17 个缺失值 |

核对值：`sum(revenue) = 7,540,350`；`marketing_spend` 缺失率为 `17 / 288 ≈ 5.90%`。缺失营销费用表示未知，不应无说明地填成零，也不应使用它得出精确营销 ROI。

可直接提问：

- 按月汇总 revenue，画折线图，并给出全年总销售额。
- 按 region 比较 revenue，画柱状图并解释各地区贡献。
- 检查缺失值，说明 marketing_spend 缺失对营销费用分析的影响。

## financial_timeseries

522 行，2025 年所有周一至周五各有 `SYNTH_A` 和 `SYNTH_B` 两条记录，每个标的 261 条。不是交易日历：不排除节假日，不含真实价格或投资信号。

| 字段 | 含义 |
| --- | --- |
| `date` | ISO 日期字符串；分析前需要显式转换并排序 |
| `symbol` | 虚构标的 `SYNTH_A`、`SYNTH_B` |
| `close` | 合成收盘价，保留两位小数 |
| `volume` | 合成成交量 |
| `currency` | 固定为 `SYNTH`，不代表真实货币 |

可直接提问：

- 分别计算两个 symbol 的月末 close，使用最后一条有效记录，绘制折线图。
- 按 symbol 分组并按日期排序，计算每日收益率并比较波动。

## 演示验收

先上传销售 CSV，核对 288 行、10 列及缺失分布；提出月度销售问题，核对全年合计。展开 Python 代码和日志，切换图表类型，下载 CSV/JSON；点击静态 PNG 验证降级渲染。重复同一问题验证精确缓存。

自修复不是每次分析都会出现。真实模型代码正确时直接完成；固定缺失列名、自修复和最多三次修复的回归覆盖位于 `backend/tests/test_agent.py` 及 `test_full_stack_integration.py`。截图的修复记录来自测试桩，不需要故意破坏演示数据。
