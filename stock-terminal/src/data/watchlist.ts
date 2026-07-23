import type { WatchItem } from "@/types/analysis";

// 主板复选池 —— 右侧栏 18 只候选（红涨绿跌由 changePct 决定）
export const watchlist: WatchItem[] = [
  { code: "600030", name: "中信证券", price: 26.84, changePct: 2.14, marketCap: "3980亿", score: 100, note: "券商龙头，牛市旗手，成交放量" },
  { code: "002202", name: "金风科技", price: 9.72, changePct: 1.46, marketCap: "410亿", score: 96, note: "风电装机高增，海风订单饱满" },
  { code: "600707", name: "彩虹股份", price: 7.85, changePct: 3.02, marketCap: "285亿", score: 94, note: "面板涨价受益，业绩弹性大" },
  { code: "002600", name: "领益智造", price: 8.16, changePct: -0.73, marketCap: "580亿", score: 91, note: "消费电子回暖，AI 硬件卡位" },
  { code: "600276", name: "新钢股份", price: 5.42, changePct: 1.88, marketCap: "168亿", score: 89, note: "钢价企稳，低估值高股息" },
  { code: "600519", name: "贵州茅台", price: 1685.0, changePct: 0.62, marketCap: "2.1万亿", score: 88, note: "消费复苏，估值修复空间" },
  { code: "601012", name: "隆基绿能", price: 18.34, changePct: 2.55, marketCap: "1390亿", score: 87, note: "光伏一体化，成本领先" },
  { code: "600900", name: "长江电力", price: 27.16, changePct: 0.41, marketCap: "6640亿", score: 86, note: "现金奶牛，防御性配置" },
  { code: "601088", name: "中国神华", price: 39.48, changePct: -0.35, marketCap: "7840亿", score: 85, note: "煤电一体，高分红稳健" },
  { code: "600585", name: "海螺水泥", price: 24.9, changePct: 0.85, marketCap: "1320亿", score: 83, note: "基建预期升温，龙头受益" },
  { code: "601899", name: "紫金矿业", price: 16.72, changePct: 1.94, marketCap: "4420亿", score: 82, note: "金铜价格强势，量增价升" },
  { code: "600438", name: "通威股份", price: 22.08, changePct: -1.12, marketCap: "990亿", score: 80, note: "硅料价格触底，静待反转" },
  { code: "601398", name: "工商银行", price: 6.28, changePct: 0.32, marketCap: "2.2万亿", score: 78, note: "高股息压舱石，估值低位" },
  { code: "600009", name: "上海机场", price: 35.6, changePct: 1.28, marketCap: "886亿", score: 76, note: "出行修复，免税弹性" },
  { code: "601668", name: "中国建筑", price: 5.14, changePct: 0.59, marketCap: "2140亿", score: 74, note: "订单充沛，破净修复" },
  { code: "600050", name: "中国联通", price: 5.36, changePct: -0.19, marketCap: "1700亿", score: 72, note: "算力租赁，国资改革预期" },
  { code: "601857", name: "中国石油", price: 8.62, changePct: 0.7, marketCap: "1.5万亿", score: 70, note: "油价高位，业绩稳定" },
  { code: "600104", name: "上汽集团", price: 15.28, changePct: 1.06, marketCap: "1770亿", score: 68, note: "出口放量，新能源转型" },
];
