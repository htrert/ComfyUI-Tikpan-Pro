import { Check, Image, PenLine, ShieldCheck, SlidersHorizontal } from "lucide-react";
import { GlassCard } from "../GlassCard";

const presetGroups = [
  { icon: Image, title: "常用比例", items: ["1:1", "4:5", "16:9", "9:16"] },
  { icon: SlidersHorizontal, title: "常用风格", items: ["自然光", "高级简洁", "电商明亮", "社媒吸睛"] },
  { icon: PenLine, title: "常用品牌词", items: ["干净", "可信", "轻盈", "高质感"] },
  { icon: ShieldCheck, title: "水印设置", items: ["保存无水印版本", "导出带品牌角标", "默认归档"] },
];

export function AccountPresets() {
  return (
    <GlassCard className="p-5">
      <p className="text-sm font-black text-teal-700">创作预设</p>
      <h1 className="mt-2 text-3xl font-black tracking-normal text-slate-950">减少重复输入</h1>
      <p className="mt-2 text-sm font-semibold text-slate-500">把常用比例、风格、品牌词和提示词保存下来。</p>

      <div className="mt-6 grid gap-4 md:grid-cols-2">
        {presetGroups.map((group) => {
          const Icon = group.icon;
          return (
            <section key={group.title} className="rounded-2xl border border-slate-200/70 bg-white/78 p-5">
              <div className="flex items-center gap-3">
                <span className="grid h-10 w-10 place-items-center rounded-xl bg-teal-50 text-teal-700">
                  <Icon className="h-4 w-4" />
                </span>
                <p className="font-black text-slate-950">{group.title}</p>
              </div>
              <div className="mt-4 flex flex-wrap gap-2">
                {group.items.map((item) => (
                  <span key={item} className="inline-flex items-center gap-1.5 rounded-full bg-slate-100 px-3 py-2 text-xs font-black text-slate-600">
                    <Check className="h-3.5 w-3.5 text-teal-600" />
                    {item}
                  </span>
                ))}
              </div>
            </section>
          );
        })}
      </div>
    </GlassCard>
  );
}
