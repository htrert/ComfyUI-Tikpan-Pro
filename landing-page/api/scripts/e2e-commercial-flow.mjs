const apiBaseUrl = process.env.TIKPAN_API_BASE_URL ?? "http://127.0.0.1:8787";
const adminToken = process.env.TIKPAN_ADMIN_TOKEN ?? "";
const imageModel = "tikpan.image.gpt-image-2-4k";

async function main() {
  const userId = `e2e_${Date.now()}`;
  await request("/health");

  const profile = await request("/v1/auth/register", {
    method: "POST",
    body: {
      user_id: userId,
      display_name: "Commercial E2E User",
      email: `${userId}@tikpan.local`,
      plan_id: "starter",
    },
  });
  const apiKey = profile.api_key?.secret;
  assert(apiKey, "register returns a user API key");

  const project = await userRequest(apiKey, "/v1/projects", {
    method: "POST",
    body: {
      name: "Commercial E2E Campaign",
      type: "image_campaign",
      status: "active",
      description: "Project-space smoke test for generated tasks and assets.",
      tags: ["e2e", "campaign"],
    },
  });
  assert(project.id, "project is created");

  const imageInput = {
    prompt: "Bright premium product image on a clean white background, soft natural light, crisp details.",
    size: "1024x1024",
    n: 1,
    quality: "auto",
    background: "opaque",
    output_format: "png",
  };

  const quoteBeforeTopUp = await userRequest(apiKey, "/v1/tasks/quote", {
    method: "POST",
    body: {
      model: imageModel,
      input: imageInput,
      routing: { mode: "balanced" },
    },
  });
  assertPublicQuoteIsSanitized(quoteBeforeTopUp);

  if (!quoteBeforeTopUp.allowed) {
    const order = await userRequest(apiKey, "/v1/payment-orders", {
      method: "POST",
      body: {
        amount: 20,
        provider: "mock",
        currency: "TOKENS",
      },
    });
    await userRequest(apiKey, `/v1/payment-orders/${encodeURIComponent(order.id)}/confirm`, {
      method: "POST",
      body: {},
    });
  }

  const quote = await userRequest(apiKey, "/v1/tasks/quote", {
    method: "POST",
    body: {
      model: imageModel,
      input: imageInput,
      routing: { mode: "balanced" },
    },
  });
  assert(quote.allowed === true, "quote is allowed after top-up");
  assertPublicQuoteIsSanitized(quote);

  const created = await userRequest(apiKey, "/v1/tasks", {
    method: "POST",
    body: {
      model: imageModel,
      input: imageInput,
      project_id: project.id,
      routing: { mode: "balanced" },
    },
  });
  assert(created.project_id === project.id, "created task is linked to the project");
  assertNoPublicTaskLeak(created, "created task response is user-safe");

  const completed = await pollTask(apiKey, created.task_id);
  assert(completed.status === "succeeded", "task reaches succeeded status");
  assert(completed.project_id === project.id, "polled task preserves project link");
  assertNoPublicTaskLeak(completed, "polled task response is user-safe");

  const projectDetail = await userRequest(apiKey, `/v1/projects/${encodeURIComponent(project.id)}`);
  assert(projectDetail.tasks?.some((task) => task.task_id === completed.task_id), "project detail includes the generated task");
  assert(projectDetail.stats?.tasks_total >= 1, "project stats count generated tasks");

  const walletResult = await userRequest(apiKey, "/v1/wallet");
  const ledgerTypes = new Set((walletResult.ledger ?? []).map((item) => item.type));
  assert(ledgerTypes.has("pre_authorize"), "wallet ledger records pre-authorization");
  assert(ledgerTypes.has("settle"), "wallet ledger records settlement");
  assert(Number(walletResult.wallet.frozen) === 0, "wallet frozen balance is released after completion");
  assert(Number(walletResult.wallet.available) < 20, "wallet available balance reflects settled Tokens");

  const incompatibleQuote = await expectProblem(apiKey, "/v1/tasks/quote", {
    method: "POST",
    body: {
      model: imageModel,
      input: {
        ...imageInput,
        seed: 42,
      },
      routing: { mode: "stable" },
    },
  });
  assert(incompatibleQuote.status === 422, "unsupported advanced parameter returns validation error");
  assert(incompatibleQuote.errors?.some((error) => error.field === "seed"), "validation error identifies unsupported field");

  const routePreview = await adminRequest("/v1/routes/preview", {
    method: "POST",
    body: {
      model: imageModel,
      input: imageInput,
      routing: { mode: "balanced" },
    },
  });
  assert(routePreview.provider?.name, "admin route preview exposes selected provider");
  assert(routePreview.provider_model?.upstream_model_name, "admin route preview exposes upstream model");
  assert(routePreview.mapped_payload?.model, "admin route preview exposes mapped payload");

  console.log(
    JSON.stringify(
      {
        ok: true,
        user_id: userId,
        project_id: project.id,
        task_id: completed.task_id,
        wallet_available: walletResult.wallet.available,
        ledger_types: [...ledgerTypes],
        public_quote_sanitized: true,
        public_task_sanitized: true,
        project_task_link_verified: true,
        admin_route_preview_verified: true,
      },
      null,
      2,
    ),
  );
}

async function pollTask(apiKey, taskId) {
  let task = null;
  for (let attempt = 0; attempt < 10; attempt += 1) {
    task = await userRequest(apiKey, `/v1/tasks/${encodeURIComponent(taskId)}`);
    if (["succeeded", "failed", "canceled", "refunded"].includes(task.status)) {
      return task;
    }
    await sleep(1100);
  }
  throw new Error(`Task ${taskId} did not reach a terminal status. Last status: ${task?.status ?? "unknown"}`);
}

function assertPublicQuoteIsSanitized(quote) {
  assert(!quote.route?.provider, "public quote does not expose provider");
  assert(!quote.route?.provider_model, "public quote does not expose provider model");
  assert(!quote.route?.mapped_payload, "public quote does not expose mapped payload");
}

function assertNoPublicTaskLeak(task, label) {
  for (const key of ["internal", "attempts", "worker"]) {
    assert(!Object.prototype.hasOwnProperty.call(task, key), `${label}: ${key} is not present`);
  }
}

async function userRequest(apiKey, path, options = {}) {
  return request(path, {
    ...options,
    headers: {
      Authorization: `Bearer ${apiKey}`,
      ...(options.headers ?? {}),
    },
  });
}

async function expectProblem(apiKey, path, options = {}) {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    method: options.method ?? "GET",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${apiKey}`,
      ...(options.headers ?? {}),
    },
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
  });
  const payload = await response.json().catch(() => ({}));
  assert(!response.ok, `${path} should fail`);
  return payload;
}

async function adminRequest(path, options = {}) {
  return request(path, {
    ...options,
    headers: {
      ...(adminToken ? { Authorization: `Bearer ${adminToken}` } : {}),
      ...(options.headers ?? {}),
    },
  });
}

async function request(path, options = {}) {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    method: options.method ?? "GET",
    headers: {
      "Content-Type": "application/json",
      ...(options.headers ?? {}),
    },
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(`${response.status} ${path}: ${JSON.stringify(payload)}`);
  }
  return payload.data;
}

function assert(condition, message) {
  if (!condition) {
    throw new Error(`Assertion failed: ${message}`);
  }
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
