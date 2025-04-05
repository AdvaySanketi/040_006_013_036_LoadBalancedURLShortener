import "dotenv/config";
import express from "express";
import { createClient } from "redis";
import { nanoid } from "nanoid";
import fetch from "node-fetch";

const app = express();
app.use(express.json());

const PORT = process.env.PORT || 5000;
const server = app.listen(PORT, "0.0.0.0", () => {
  console.log(`Server started and listening on 0.0.0.0:${PORT}`);
  console.log(`Health endpoint available at http://0.0.0.0:${PORT}/health`);
});

app.use((req, res, next) => {
  console.log(`${new Date().toISOString()} - ${req.method} ${req.path}`);
  next();
});

app.get("/health", (req, res) => {
  console.log("Health check called!");
  res.status(200).json({
    status: "healthy",
    redis: isRedisConnected ? "connected" : "not connected yet",
    appVersion: "1.0.0",
    timestamp: new Date().toISOString(),
  });
});

let isRedisConnected = false;

const client = createClient({
  socket: {
    host: process.env.REDIS_HOST || "redis",
    port: parseInt(process.env.REDIS_PORT) || 6379,
    reconnectStrategy: (retries) => {
      const delay = Math.min(retries * 100, 5000);
      console.log(
        `Redis reconnection attempt ${retries}, retrying in ${delay}ms`
      );
      return delay;
    },
  },
  password: process.env.REDIS_PASSWORD || "password",
});

client.on("connect", () => console.log("Redis connecting..."));
client.on("ready", () => console.log("Redis connected and ready"));
client.on("error", (err) => console.error("Redis error:", err));
client.on("reconnecting", () => console.log("Redis reconnecting..."));
client.on("end", () => console.log("Redis connection closed"));

(async () => {
  try {
    console.log("Attempting to connect to Redis...");
    await client.connect();
    isRedisConnected = true;
    console.log("Redis connection established successfully");
  } catch (err) {
    console.error("Failed to connect to Redis:", err);
  }
})();

const BASE_URL = process.env.BASE_URL || "http://localhost:5000";

const checkUrlExists = async (url) => {
  try {
    const response = await fetch(url, { method: "HEAD", timeout: 5000 });
    return response.ok;
  } catch (error) {
    console.error("URL validation failed:", error);
    return false;
  }
};

app.post("/shorten", async (req, res) => {
  if (!isRedisConnected) {
    return res
      .status(503)
      .json({ error: "Service unavailable. Redis not connected." });
  }

  const { url } = req.body;
  if (!url) return res.status(400).json({ error: "URL is required" });

  try {
    const isValid = await checkUrlExists(url);
    if (!isValid) return res.status(400).json({ error: "Invalid URL" });

    const existingShortId = await client.get(`long:${url}`);
    if (existingShortId) {
      return res.json({ shortened_url: `${BASE_URL}/${existingShortId}` });
    }

    const shortId = nanoid(12);
    await client
      .multi()
      .set(`short:${shortId}`, url)
      .set(`long:${url}`, shortId)
      .exec();

    return res.status(201).json({ shortened_url: `${BASE_URL}/${shortId}` });
  } catch (err) {
    console.error("Shortening error:", err);
    return res.status(500).json({ error: "Internal server error" });
  }
});

app.get("/:shortenedId", async (req, res) => {
  if (!isRedisConnected) {
    return res
      .status(503)
      .json({ error: "Service unavailable. Redis not connected." });
  }

  try {
    const longUrl = await client.get(`short:${req.params.shortenedId}`);
    if (!longUrl) return res.status(404).json({ error: "URL not found" });
    return res.redirect(longUrl);
  } catch (err) {
    console.error("Redirection error:", err);
    return res.status(500).json({ error: "Internal server error" });
  }
});

app.use((req, res) => {
  console.log(`404 for path: ${req.path}`);
  res.status(404).json({
    error: "Not found",
    path: req.path,
    method: req.method,
  });
});

process.on("SIGTERM", () => {
  console.log("SIGTERM received, shutting down gracefully");
  server.close(() => {
    console.log("HTTP server closed");
    client
      .quit()
      .then(() => {
        console.log("Redis connection closed");
        process.exit(0);
      })
      .catch((err) => {
        console.error("Error closing Redis connection", err);
        process.exit(1);
      });
  });
});
