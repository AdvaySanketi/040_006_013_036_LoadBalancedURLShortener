import http from "k6/http";
import { check, sleep } from "k6";
import { Rate } from "k6/metrics";

const errorRate = new Rate("errors");

// Test configuration
export const options = {
  stages: [
    { duration: "30s", target: 10 }, // Ramp-up to 10 users
    { duration: "1m", target: 50 }, // Ramp-up to 50 users
    { duration: "2m", target: 50 }, // Stay at 50 users for 2 minutes
    { duration: "1m", target: 100 }, // Ramp-up to 100 users
    { duration: "2m", target: 100 }, // Stay at 100 users for 2 minutes
    { duration: "1m", target: 50 }, // Ramp-down to 50 users
    { duration: "30s", target: 0 }, // Ramp-down to 0 users
  ],
  thresholds: {
    http_req_duration: ["p(95)<500"], // 95% of requests should complete within 500ms
    errors: ["rate<0.1"], // Error rate should be less than 10%
  },
};

const BASE_URL = "http://127.0.0.1";
const TEST_URLS = [
  "https://github.com",
  "https://kubernetes.io",
  "https://nodejs.org",
  "https://redis.io",
  "https://expressjs.com",
];

function getRandomUrl() {
  return TEST_URLS[Math.floor(Math.random() * TEST_URLS.length)];
}

function getRandomShortId() {
  const chars =
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";
  let result = "";
  for (let i = 0; i < 12; i++) {
    result += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  return result;
}

export default function () {
  const createPayload = JSON.stringify({
    url: getRandomUrl(),
  });

  const createParams = {
    headers: {
      "Content-Type": "application/json",
    },
  };

  let createResponse = http.post(
    `${BASE_URL}/shorten`,
    createPayload,
    createParams
  );

  let createSuccess = check(createResponse, {
    "Create status is 201 or 200": (r) => r.status === 201 || r.status === 200,
    "Create response has shortened_url": (r) =>
      JSON.parse(r.body).shortened_url !== undefined,
  });

  if (!createSuccess) {
    errorRate.add(1);
    console.error(`Create request failed: ${createResponse.status}`);
  } else {
    console.log(`Create request succeeded: ${createResponse.body}`);
  }

  let shortenedUrl = "";
  let shortId = "";
  let fake = false;

  if (createSuccess) {
    shortenedUrl = JSON.parse(createResponse.body).shortened_url;
    shortId = shortenedUrl.split("/").pop();
  } else {
    shortId = getRandomShortId();
    fake = true;
  }

  sleep(1);

  let accessResponse = http.get(`${BASE_URL}/${shortId}`);

  let accessSuccess1 = check(accessResponse, {
    "Access status is 302 or 404": (r) =>
      (r.status === 302 || r.status === 404) && fake,
  });

  let accessSuccess2 = check(accessResponse, {
    "Access status is 200 or 201": (r) => r.status === 200 || r.status === 201,
  });

  if (!accessSuccess1 && !accessSuccess2) {
    errorRate.add(1);
    console.error(`Access request failed: ${accessResponse.status}`);
  } else {
    console.log(`Access request succeeded: ${accessResponse.status}`);
  }

  let healthResponse = http.get(`${BASE_URL}/health`);

  let healthSuccess = check(healthResponse, {
    "Health status is 200": (r) => r.status === 200,
    "Health reports as healthy": (r) => JSON.parse(r.body).status === "healthy",
  });

  if (!healthSuccess) {
    errorRate.add(1);
    console.error(`Health request failed: ${healthResponse.status}`);
  } else {
    console.log(`Health request succeeded: ${healthResponse.body}`);
  }

  sleep(Math.random() * 1.5 + 0.5);
}
