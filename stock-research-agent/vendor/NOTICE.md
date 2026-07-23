# Vendored third-party code

## stocksdk/

- **来源**: https://github.com/YuzuRain/stockInfo_searcher
- **作者**: YuzuRain
- **拷贝的 commit**: `4d487fde42bc47f5f388d638b427c7e231e74b2a` (2026-07-22)
- **拷贝范围**: 仓库根目录下的 `stocksdk/` Python 包（未含 examples/tests/打包元数据）。
- **用途**: 为本项目的 K 线模块（`stock_agent/kline.py`）提供 A 股 OHLCV 免费行情数据源
  （腾讯 / 东方财富 / 新浪，多源自动故障转移），唯一运行期依赖为 `requests`。

### 许可证状态（务必留意）

截至拷贝时，**上游仓库没有任何 LICENSE / COPYING 文件，README 也未声明开源协议**
（git 历史中亦从未出现过许可证文件）。按著作权默认规则，"无许可证" 意味着
"保留所有权利"，严格意义上不授予再分发权利。

因此本处 vendor 仅用于**本地研究与内部使用**。若本项目将来需要公开分发，需先：
1. 联系原作者取得明确授权，或
2. 用标准库自行重写等价的最小行情源（不含他人代码），或
3. 移除本 vendor 目录。

保留本 NOTICE 即为对原作者的署名与出处标注。对 vendor 代码的任何本地改动
请在下方记录，以便与上游区分。

### 本地改动

- 无（原样拷贝）。
