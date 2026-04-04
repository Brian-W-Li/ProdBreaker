import http from "k6/http";
import { check, sleep } from "k6";
import { Rate } from "k6/metrics";
import { htmlReport } from "https://raw.githubusercontent.com/benc-uk/k6-reporter/main/dist/bundle.js";
import { textSummary } from "https://jslib.k6.io/k6-summary/0.0.1/index.js";

const errorRate = new Rate("error_rate");

export const options = {
  stages: [
    { duration: "15s", target: 100 },
    { duration: "30s", target: 500 },
    { duration: "30s", target: 500 },
    { duration: "15s", target: 0 },
  ],
  thresholds: {
    http_req_failed: ["rate<0.05"],
    http_req_duration: ["p(95)<500"],
    error_rate: ["rate<0.05"],
  },
};

const BASE = __ENV.BASE_URL || "http://localhost:8000";
const JSON_HEADERS = { "Content-Type": "application/json" };

export default function () {
  // Health
  const health = http.get(`${BASE}/health`);
  check(health, { "health 200": (r) => r.status === 200 });
  errorRate.add(health.status !== 200);

  // Products (Redis-cached)
  const products = http.get(`${BASE}/products`);
  check(products, {
    "products 200": (r) => r.status === 200,
    "products cached": (r) => r.headers["X-Cache"] !== undefined,
  });
  errorRate.add(products.status !== 200);

  // Create user
  const username = `user_${__VU}_${__ITER}`;
  const createUser = http.post(
    `${BASE}/users`,
    JSON.stringify({ username, email: `${username}@test.com` }),
    { headers: JSON_HEADERS }
  );
  check(createUser, { "create user 201": (r) => r.status === 201 });
  errorRate.add(createUser.status !== 201);

  if (createUser.status !== 201) {
    sleep(0.1);
    return;
  }

  const user = createUser.json();
  const userId = user.id;

  // Get user by ID
  const getUser = http.get(`${BASE}/users/${userId}`, { tags: { name: "GET /users/:id" } });
  check(getUser, { "get user 200": (r) => r.status === 200 });
  errorRate.add(getUser.status !== 200);

  // List users
  const listUsers = http.get(`${BASE}/users?page=1&per_page=10`);
  check(listUsers, { "list users 200": (r) => r.status === 200 });
  errorRate.add(listUsers.status !== 200);

  // Update user
  const updateUser = http.put(
    `${BASE}/users/${userId}`,
    JSON.stringify({ username: `${username}_updated` }),
    { headers: JSON_HEADERS, tags: { name: "PUT /users/:id" } }
  );
  check(updateUser, { "update user 200": (r) => r.status === 200 });
  errorRate.add(updateUser.status !== 200);

  // Create URL
  const createUrl = http.post(
    `${BASE}/urls`,
    JSON.stringify({
      user_id: userId,
      original_url: "https://example.com",
      title: `Test URL ${__VU}_${__ITER}`,
    }),
    { headers: JSON_HEADERS }
  );
  check(createUrl, { "create url 201": (r) => r.status === 201 });
  errorRate.add(createUrl.status !== 201);

  if (createUrl.status === 201) {
    const url = createUrl.json();
    const urlId = url.id;

    // Get URL by ID
    const getUrl = http.get(`${BASE}/urls/${urlId}`, { tags: { name: "GET /urls/:id" } });
    check(getUrl, { "get url 200": (r) => r.status === 200 });
    errorRate.add(getUrl.status !== 200);

    // List URLs (paginated)
    const listUrls = http.get(`${BASE}/urls?user_id=${userId}&page=1&per_page=10`, { tags: { name: "GET /urls" } });
    check(listUrls, { "list urls 200": (r) => r.status === 200 });
    errorRate.add(listUrls.status !== 200);

    // Update URL
    const updateUrl = http.put(
      `${BASE}/urls/${urlId}`,
      JSON.stringify({ title: "Updated Title", is_active: true }),
      { headers: JSON_HEADERS, tags: { name: "PUT /urls/:id" } }
    );
    check(updateUrl, { "update url 200": (r) => r.status === 200 });
    errorRate.add(updateUrl.status !== 200);
  }

  // Events (paginated)
  const events = http.get(`${BASE}/events?page=1&per_page=10`);
  check(events, { "events 200": (r) => r.status === 200 });
  errorRate.add(events.status !== 200);

  sleep(0.1);
}

export function handleSummary(data) {
  return {
    "load-summary.json": JSON.stringify(data),
    "load-summary.html": htmlReport(data),
    stdout: textSummary(data, { indent: " ", enableColors: true }),
  };
}
