import type { DisciplineItem } from "@/types/analysis";

// 执行纪律 —— 右下角
export const discipline: DisciplineItem[] = [
  { order: 1, text: "先处理持仓：达到卖点或破位止损优先执行，再考虑新买入" },
  { order: 2, text: "只买主板：仅在主板复选池内选股，规避创业板/科创板高波动" },
  { order: 3, text: "分批建仓：单只首仓不超过 1/3，放量确认后再加仓" },
  { order: 4, text: "严守买卖点：不追高、不抄底，按计划价位挂单成交" },
  { order: 5, text: "单票仓位上限 20%，总仓位随大盘评分动态调整" },
];
