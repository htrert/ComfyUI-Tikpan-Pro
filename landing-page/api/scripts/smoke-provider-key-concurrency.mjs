const baseUrl = process.env.TIKPAN_API_BASE_URL ?? "http://localhost:8787";
const taskCount = Number(process.env.TIKPAN_SMOKE_TASKS ?? 8);

await postJson("/admin/billing-plans", {
  id: "starter",
  name: "Starter",
  monthly_task_limit: 120,
  monthly_spend_limit: 30,
  rate_limit_per_minute: 60,
  concurrency_limit: taskCount,
  features: ["image", "video", "chat"],
  status: "active",
});

const tasks = await Promise.all(
  Array.from({ length: taskCount }, (_, index) =>
    postJson("/v1/tasks", {
      model: "tikpan.image.gpt-image-2-4k",
      input: {
        prompt: `provider key concurrency smoke ${index + 1}`,
        size: "1024x1024",
        quality: "high",
        n: 1,
      },
      routing: { mode: "quality" },
    })
  )
);

const taskIds = tasks.map((item) => item.data.task_id);
const completed = await waitForTasks(taskIds);
const keys = await getJson("/admin/provider-keys");
const cangyuan = keys.data.find((key) => key.id === "pkey-cangyuan-main");

assert(completed.every((task) => task.data.status === "succeeded"), "All smoke tasks should succeed.");
assert(cangyuan, "Cangyuan provider key should exist.");
assert(cangyuan.runtime.current_concurrency === 0, "Provider key concurrency should be released to 0.");
assert(cangyuan.runtime.today_request_count >= taskCount, "Provider key request count should reflect smoke traffic.");

const adminTasks = await getJson("/admin/tasks?limit=50");
for (const taskId of taskIds) {
  const task = adminTasks.data.find((item) => item.task_id === taskId);
  assert(task?.attempts?.[0]?.provider_key_id, `Task ${taskId} should record provider_key_id in admin attempts.`);
}

const apiKeysStatus = await statusCode("/admin/api-keys");
const webhookStatus = await statusCode("/admin/webhook-endpoints");
assert(apiKeysStatus === 404, "/admin/api-keys should remain disabled.");
assert(webhookStatus === 404, "/admin/webhook-endpoints should remain disabled.");

console.log(
  JSON.stringify(
    {
      task_count: taskCount,
      completed: completed.length,
      provider_key_id: cangyuan.id,
      current_concurrency: cangyuan.runtime.current_concurrency,
      today_request_count: cangyuan.runtime.today_request_count,
      admin_api_keys_status: apiKeysStatus,
      admin_webhook_endpoints_status: webhookStatus,
    },
    null,
    2
  )
);

async function waitForTasks(ids) {
  for (let attempt = 0; attempt < 80; attempt += 1) {
    const tasks = await Promise.all(ids.map((id) => getJson(`/v1/tasks/${id}`)));
    if (tasks.every((task) => ["succeeded", "failed", "canceled", "refunded"].includes(task.data.status))) {
      return tasks;
    }
    await sleep(250);
  }
  throw new Error("Timed out waiting for smoke tasks.");
}

async function getJson(path) {
  const response = await fetch(`${baseUrl}${path}`);
  if (!response.ok) {
    throw new Error(`${path} failed with HTTP ${response.status}: ${await response.text()}`);
  }
  return response.json();
}

async function postJson(path, body) {
  const response = await fetch(`${baseUrl}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw new Error(`${path} failed with HTTP ${response.status}: ${await response.text()}`);
  }
  return response.json();
}

async function statusCode(path) {
  const response = await fetch(`${baseUrl}${path}`);
  return response.status;
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}
