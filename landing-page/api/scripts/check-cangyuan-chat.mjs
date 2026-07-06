const apiKey = process.env.CANGYUAN_API_KEY;
const model = process.env.CANGYUAN_MODEL ?? "gpt-5.5";
const baseUrl = (process.env.CANGYUAN_BASE_URL ?? "https://ai.cangyuansuanli.cn").replace(/\/+$/, "");

if (!apiKey) {
  console.error("Missing CANGYUAN_API_KEY. Set it in your shell before running this smoke test.");
  process.exit(1);
}

const response = await fetch(`${baseUrl}/v1/chat/completions`, {
  method: "POST",
  headers: {
    Authorization: `Bearer ${apiKey}`,
    "Content-Type": "application/json",
  },
  body: JSON.stringify({
    model,
    messages: [{ role: "user", content: "用一句话回复：沧元算力 API 已连通。" }],
    stream: false,
  }),
});

const text = await response.text();
let payload = text;
try {
  payload = JSON.parse(text);
} catch {
  // keep raw text
}

if (!response.ok) {
  console.error(`Cangyuan request failed: HTTP ${response.status}`);
  console.error(payload);
  process.exit(1);
}

console.log("Cangyuan chat smoke test succeeded.");
console.log(JSON.stringify(payload, null, 2));
